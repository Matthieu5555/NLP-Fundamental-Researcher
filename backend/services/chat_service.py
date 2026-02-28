"""Chat turn orchestration.

Absorbs context building, LLM calls, RAG retrieval, belief extraction,
report editing, and cost tracking into a single process_turn() call.
The router stays thin: SSE formatting and HTTP concerns only.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from backend.core.belief_classifier import (
    extract_beliefs_from_conversation,
    get_badge_for_belief,
)
from backend.core.context_manager import ContextManager
from backend.core.cost_tracker import CostTracker
from backend.core.intent_classifier import classify_intent, UserIntent
from backend.core.rag_engine import RAGEngine
from backend.core.report_builder import Source
from backend.core.report_editor import edit_section, generate_edit_confirmation
from backend.core.report_rag import ReportRAG
from backend.core.session import AnalysisSession, session_manager
from backend.agents.llm_wrapper import (
    call_llm,
    get_llm_response_with_usage,
)

logger = logging.getLogger(__name__)

# Fast, cheap model for background belief extraction (doesn't need high reasoning)
BELIEF_EXTRACTION_MODEL = "moonshotai/kimi-k2.5"


@dataclass(frozen=True)
class ChatTurnResult:
    """Complete result of processing one chat turn."""

    response_text: str
    intent: str
    citations: list[dict] = field(default_factory=list)
    sources_added: list[dict] = field(default_factory=list)
    extracted_beliefs: list[dict] = field(default_factory=list)
    report_updated: bool = False
    turn_cost_usd: float = 0.0
    total_chat_cost_usd: float = 0.0
    tokens_used: int = 0
    report_edited: bool = False
    edit_section: str | None = None
    rag_search_performed: bool = False
    valuation_updated: bool = False
    updated_fair_value: float | None = None


class ChatService:
    """Orchestrates a single chat turn: intent -> context -> LLM -> side effects."""

    def __init__(self, session: AnalysisSession, llm_config: Any) -> None:
        self._session = session
        self._llm_config = llm_config
        self._cost_tracker = CostTracker()

    def process_turn(self, message: str) -> ChatTurnResult:
        """Process one user message through the full chat pipeline.

        Classifies intent, builds context, calls LLM, extracts beliefs,
        and updates session state. Returns everything the router needs
        to format a response (SSE or JSON).
        """
        intent = classify_intent(message, use_llm=False)
        logger.info("Intent: %s", intent.intent.value)

        if intent.intent == UserIntent.REPORT_EDIT:
            return self._handle_report_edit(intent)

        return self._handle_research_turn(message, intent)

    # --- Report editing flow ---

    def _handle_report_edit(self, intent: Any) -> ChatTurnResult:
        api_key = os.getenv("OPENROUTER_API_KEY")
        model = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")

        with session_manager.session_context(self._session.session_id) as sess:
            if not sess:
                return ChatTurnResult(
                    response_text="Session expired.",
                    intent="report_edit",
                )

            if api_key:
                edit_result = edit_section(
                    session=sess,
                    intent=intent,
                    llm_func=call_llm,
                    api_key=api_key,
                    model=model,
                )
                self._cost_tracker.add_llm_call(model, 1500, 800)
                response_text = generate_edit_confirmation(intent, edit_result)
                report_edited = edit_result.success
            else:
                response_text = "API key not configured."
                report_edited = False

            sess.add_message(
                "assistant",
                response_text,
                metadata={
                    "intent": "report_edit",
                    "edit_action": intent.edit_action.value
                    if intent.edit_action
                    else None,
                    "target_section": intent.target_section,
                },
            )

            total_cost = self._accumulate_cost(sess)

        return ChatTurnResult(
            response_text=response_text,
            intent="report_edit",
            turn_cost_usd=self._cost_tracker.get_total_cost(),
            total_chat_cost_usd=total_cost,
            report_edited=report_edited,
            edit_section=intent.target_section,
        )

    # --- Standard research/belief flow ---

    def _handle_research_turn(self, message: str, intent: Any) -> ChatTurnResult:
        session = session_manager.get_session(self._session.session_id)
        if not session:
            return ChatTurnResult(
                response_text="Session expired.",
                intent=intent.intent.value,
            )

        rag_engine = RAGEngine()

        # Build context from report, RAG, and report-internal search
        report_summary = self._build_report_summary(session)
        rag_context = rag_engine.retrieve_context(
            query=message,
            ticker=session.ticker,
            company_name=session.metadata.get("company_name", session.ticker),
        )
        additional_context = rag_engine.format_context_for_llm(rag_context)
        report_rag_context = self._execute_report_rag(message, session)

        system_prompt = (
            f"You are a financial analyst assistant named George, "
            f"analyzing {session.ticker}.\n\n"
            f"Be concise, factual, and cite specific numbers when possible.\n\n"
            f"Analysis overview:\n{report_summary}\n\n"
            f"{report_rag_context}\n\n"
            f"{additional_context}"
        )

        # Conversation history for context window
        model_name_for_context = session.metadata.get("model", "default")
        context_mgr = ContextManager(model=model_name_for_context)
        context = context_mgr.build_context(session, message, system_prompt)
        conversation_context = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in context["messages"]
        )
        full_system_prompt = (
            f"{system_prompt}\n\nPrevious conversation:\n{conversation_context}"
        )

        # LLM call
        logger.info(
            "Calling LLM with model=%s, temp=%s...",
            self._llm_config.model,
            self._llm_config.temperature,
        )
        llm_result = get_llm_response_with_usage(
            prompt=message,
            system_prompt=full_system_prompt,
            llm_config=self._llm_config,
        )
        response_text = (
            llm_result.content if llm_result.success else f"Error: {llm_result.error}"
        )
        logger.info(
            "LLM response received: %d chars, tokens: %d (in: %d, out: %d)",
            len(response_text),
            llm_result.total_tokens,
            llm_result.input_tokens,
            llm_result.output_tokens,
        )

        input_tokens = llm_result.input_tokens
        output_tokens = llm_result.output_tokens
        model_name = self._llm_config.model or os.getenv(
            "OPENROUTER_MODEL", "moonshotai/kimi-k2.5"
        )
        self._cost_tracker.add_llm_call(model_name, input_tokens, output_tokens)

        citations = rag_engine.get_source_citations(rag_context)

        # Thread-safe session updates
        with session_manager.session_context(self._session.session_id) as sess:
            if not sess:
                return ChatTurnResult(
                    response_text="Session expired.",
                    intent=intent.intent.value,
                )

            sess.add_message(
                "assistant",
                response_text,
                metadata={
                    "sources": citations,
                    "rag_search_performed": rag_context.search_performed,
                    "intent": intent.intent.value,
                },
            )

            sources_added = self._add_rag_sources(sess, rag_context.sources)
            extracted_beliefs = self._extract_beliefs(
                sess, message, response_text
            )

            # Trigger valuation repropagation if any belief is a valuation view
            valuation_updated = False
            updated_fair_value = None
            has_valuation_view = any(
                getattr(b, "insight_type", None)
                and b.insight_type.value == "valuation_view"
                for b in extracted_beliefs
            )
            if has_valuation_view:
                valuation_updated, updated_fair_value = self._try_repropagation(sess)

            total_cost = self._accumulate_cost(sess)
            message_count = len(sess.conversation_history)

        formatted_beliefs = _format_beliefs_for_frontend(extracted_beliefs)

        return ChatTurnResult(
            response_text=response_text,
            intent=intent.intent.value,
            citations=citations,
            sources_added=sources_added,
            extracted_beliefs=formatted_beliefs,
            report_updated=bool(extracted_beliefs),
            turn_cost_usd=self._cost_tracker.get_total_cost(),
            total_chat_cost_usd=total_cost,
            tokens_used=input_tokens + output_tokens,
            rag_search_performed=rag_context.search_performed,
            valuation_updated=valuation_updated,
            updated_fair_value=updated_fair_value,
        )

    # --- Helpers ---

    @staticmethod
    def _try_repropagation(sess: AnalysisSession) -> tuple[bool, float | None]:
        """Attempt valuation repropagation if DCF overrides can be parsed from beliefs.

        Returns (valuation_updated, fair_value_per_share). Non-fatal: logs
        warnings and returns (False, None) on any failure.
        """
        if not sess.analyst_sources or not sess.metadata.get("dcf"):
            return False, None

        try:
            from backend.core.belief_overrides import parse_analyst_overrides
            from backend.core.valuation_repropagation import run_valuation_repropagation

            overrides = parse_analyst_overrides(
                beliefs=list(sess.belief_graph.beliefs.values()) if hasattr(sess.belief_graph, "beliefs") else [],
                analyst_sources=sess.analyst_sources,
                llm_func=call_llm,
                api_key=os.getenv("OPENROUTER_API_KEY", ""),
                model=BELIEF_EXTRACTION_MODEL,
            )

            if not overrides.dcf_overrides:
                return False, None

            outcome = run_valuation_repropagation(
                session_metadata=sess.metadata,
                dcf_overrides=overrides.dcf_overrides,
            )

            if outcome:
                sess.metadata.update(outcome.metadata_updates)
                changelog = sess.metadata.setdefault("assumption_changelog", [])
                changelog.extend(outcome.assumption_changes)
                logger.info(
                    "Chat-triggered repropagation: fair_value=%.2f",
                    outcome.fair_value_per_share or 0,
                )
                return True, outcome.fair_value_per_share

        except Exception as e:
            logger.warning("Chat valuation repropagation failed (non-fatal): %s", e)

        return False, None

    def _accumulate_cost(self, sess: AnalysisSession) -> float:
        prev_cost = sess.metadata.get("chat_cost_usd", 0.0)
        turn_cost = self._cost_tracker.get_total_cost()
        sess.metadata["chat_cost_usd"] = prev_cost + turn_cost
        return sess.metadata["chat_cost_usd"]

    @staticmethod
    def _build_report_summary(session: AnalysisSession) -> str:
        if not session.report_state:
            return ""

        summary = f"Analysis for {session.ticker}:\n"
        for _section_id, section in list(session.report_state.sections.items())[:3]:
            summary += f"\n{section.title}:\n{section.content[:200]}...\n"

        if session.metadata.get("contradictions"):
            summary += "\n\nKey Conflicts in Analysis:\n"
            for c in session.metadata["contradictions"]:
                summary += f"- {c.get('disputed_fact', 'Unknown')}: "
                summary += f"Bulls say: {c.get('bull_interpretation', 'N/A')} | "
                summary += f"Bears say: {c.get('bear_interpretation', 'N/A')}\n"

        if session.metadata.get("research_gaps"):
            summary += "\nResearch Gaps:\n"
            for gap in session.metadata["research_gaps"][:5]:
                summary += (
                    f"- {gap.get('question', gap) if isinstance(gap, dict) else gap}\n"
                )

        return summary

    @staticmethod
    def _execute_report_rag(message: str, session: AnalysisSession) -> str:
        if not session.report_state:
            return ""
        try:
            report_rag = ReportRAG()
            if report_rag.build_index(session.report_state):
                relevant_chunks = report_rag.search(message, k=5)
                if relevant_chunks:
                    return report_rag.format_results_for_llm(
                        relevant_chunks, max_chars=2000
                    )
        except Exception as e:
            logger.warning("Report RAG failed: %s", e)
        return ""

    @staticmethod
    def _add_rag_sources(
        session: AnalysisSession, rag_sources: list
    ) -> list[dict]:
        if not rag_sources or not session.report_state:
            return []

        sources_section = session.report_state.sections.get("sources")
        if not sources_section or not hasattr(sources_section, "sources"):
            return []

        existing_urls = set()
        for existing_source in sources_section.sources:
            if hasattr(existing_source, "url"):
                existing_urls.add(_normalize_url(existing_source.url))

        sources_added = []
        current_count = len(sources_section.sources)

        for src in rag_sources:
            src_url = src.url if hasattr(src, "url") else ""
            normalized_url = _normalize_url(src_url)
            if normalized_url and normalized_url in existing_urls:
                continue

            current_count += 1
            new_source = Source(
                id=current_count,
                title=src.title if hasattr(src, "title") else "Research",
                url=src_url,
                source_type=src.source_type
                if hasattr(src, "source_type")
                else "search",
                date=src.date if hasattr(src, "date") else "recent",
            )
            sources_section.sources.append(new_source)
            sources_added.append(new_source.to_dict())
            existing_urls.add(normalized_url)

        return sources_added

    def _extract_beliefs(
        self,
        session: AnalysisSession,
        message: str,
        response_text: str,
    ) -> list[Any]:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return []

        try:
            extracted = extract_beliefs_from_conversation(
                user_message=message,
                ai_response=response_text,
                ticker=session.ticker,
                llm_func=call_llm,
                api_key=api_key,
                model=BELIEF_EXTRACTION_MODEL,
            )
            self._cost_tracker.add_llm_call(BELIEF_EXTRACTION_MODEL, 500, 200)

            for belief in extracted:
                session.belief_graph.add_belief(
                    content=belief.content,
                    confidence=belief.confidence,
                    source=f"chat:{belief.target_section}",
                )
                session.add_analyst_source(
                    belief_content=belief.content,
                    insight_type=belief.insight_type.value,
                    section=belief.target_section,
                )

            return extracted

        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Belief extraction failed: %s", e)
            return []


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    if not url:
        return ""
    url = url.lower().strip()
    for prefix in ["https://", "http://"]:
        if url.startswith(prefix):
            url = url[len(prefix):]
            break
    if url.startswith("www."):
        url = url[4:]
    return url.rstrip("/")


def _format_beliefs_for_frontend(beliefs: list[Any]) -> list[dict]:
    """Format extracted beliefs for frontend display."""
    return [
        {
            "content": b.content,
            "type": b.insight_type.value,
            "section": b.target_section,
            "confidence": b.confidence,
            "badge": get_badge_for_belief(b.insight_type)["label"],
            "badge_color": get_badge_for_belief(b.insight_type)["color"],
            "badge_bg": get_badge_for_belief(b.insight_type)["bg"],
            "has_rationale": b.has_rationale,
            "rationale": b.rationale,
        }
        for b in beliefs
    ]

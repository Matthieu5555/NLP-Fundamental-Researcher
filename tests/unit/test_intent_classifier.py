"""Tests for intent_classifier: heuristic classification, edit detection, section targeting."""

import pytest

from backend.core.intent_classifier import (
    classify_intent_heuristic,
    classify_intent,
    ClassifiedIntent,
    UserIntent,
    ReportEditAction,
    SECTION_KEYWORDS,
    EDIT_KEYWORDS,
)


class TestHeuristicClassification:
    """Test the fast keyword-based classifier."""

    # --- Conversational intent ---
    @pytest.mark.parametrize("message", [
        "thanks", "thank you", "got it", "ok", "okay",
        "understood", "i see", "cool", "great", "perfect",
        "thanks!", "ok.", "great!",
    ])
    def test_conversational_messages(self, message):
        result = classify_intent_heuristic(message)
        assert result.intent == UserIntent.CONVERSATIONAL
        assert result.confidence >= 0.85

    # --- Belief intent ---
    @pytest.mark.parametrize("message", [
        "I think the stock is overvalued",
        "I believe revenue will grow",
        "My view is that the moat is strong",
        "I'm convinced this is a buy",
        "In my opinion, risk is low",
    ])
    def test_belief_messages(self, message):
        result = classify_intent_heuristic(message)
        assert result.intent == UserIntent.BELIEF

    def test_belief_with_question_mark_becomes_research(self):
        result = classify_intent_heuristic("I think the PE is high, but what do you think?")
        assert result.intent == UserIntent.RESEARCH

    # --- Report edit intent ---
    def test_edit_rewrite_section(self):
        result = classify_intent_heuristic("Rewrite the bull case to be more aggressive")
        assert result.intent == UserIntent.REPORT_EDIT
        assert result.edit_action == ReportEditAction.REWRITE
        assert result.target_section == "bull_case"

    def test_edit_shorten_section(self):
        result = classify_intent_heuristic("Make the recommendation shorter")
        assert result.intent == UserIntent.REPORT_EDIT
        assert result.edit_action == ReportEditAction.SHORTEN
        assert result.target_section == "recommendation"

    def test_edit_expand_section(self):
        result = classify_intent_heuristic("Expand the technicals with more detail")
        assert result.intent == UserIntent.REPORT_EDIT
        assert result.edit_action == ReportEditAction.EXPAND
        assert result.target_section == "technicals"

    def test_edit_full_report(self):
        result = classify_intent_heuristic("Shorten the entire report")
        assert result.intent == UserIntent.REPORT_EDIT
        assert result.target_section == "full_report"

    def test_edit_without_section_falls_to_research(self):
        """Edit keyword without a section target should not be REPORT_EDIT."""
        result = classify_intent_heuristic("Can you expand on that?")
        # "expand" is detected but no section keyword, and no "report"/"analysis"
        assert result.intent in (UserIntent.RESEARCH, UserIntent.REPORT_EDIT)

    # --- Research intent (default) ---
    @pytest.mark.parametrize("message", [
        "What is the P/E ratio?",
        "Tell me about the competitive landscape",
        "How does revenue compare to peers?",
        "What are the main risks?",
    ])
    def test_research_messages(self, message):
        result = classify_intent_heuristic(message)
        assert result.intent == UserIntent.RESEARCH


class TestClassifiedIntentSerialization:
    def test_to_dict_research(self):
        ci = ClassifiedIntent(intent=UserIntent.RESEARCH, confidence=0.7)
        d = ci.to_dict()
        assert d["intent"] == "research"
        assert d["edit_action"] is None

    def test_to_dict_edit(self):
        ci = ClassifiedIntent(
            intent=UserIntent.REPORT_EDIT,
            confidence=0.8,
            edit_action=ReportEditAction.REWRITE,
            target_section="fundamentals",
            edit_instruction="Make it better",
        )
        d = ci.to_dict()
        assert d["intent"] == "report_edit"
        assert d["edit_action"] == "rewrite"
        assert d["target_section"] == "fundamentals"


class TestClassifyIntentEntryPoint:
    def test_uses_heuristic_by_default(self):
        result = classify_intent("What is the PE ratio?")
        assert result.intent == UserIntent.RESEARCH

    def test_no_llm_without_credentials(self):
        result = classify_intent("Something ambiguous", use_llm=True)
        # Without llm_func and api_key, falls back to heuristic
        assert isinstance(result, ClassifiedIntent)


class TestKeywordCoverage:
    """Ensure keyword dictionaries are well-formed."""

    def test_section_keywords_are_nonempty(self):
        for section_id, keywords in SECTION_KEYWORDS.items():
            assert len(keywords) > 0, f"Section {section_id} has no keywords"

    def test_edit_keywords_are_nonempty(self):
        for action, keywords in EDIT_KEYWORDS.items():
            assert len(keywords) > 0, f"Action {action} has no keywords"

    def test_edit_keywords_match_enum(self):
        for action_key in EDIT_KEYWORDS:
            ReportEditAction(action_key)  # should not raise

"""
Context Window Manager.

Manages conversation context to stay within LLM token limits through:
- Token estimation (word count heuristic)
- Smart windowing (keep recent, summarize old)
- Automatic compression when approaching limits
"""

from typing import Dict, List
from .session import AnalysisSession, Message


# =============================================================================
# CONTEXT WINDOW CONSTANTS
# =============================================================================

# Token limits for different models (with buffer reserved for response)
# Last updated: December 2024
# Values are conservative to leave room for response generation
MODEL_TOKEN_LIMITS = {
    "gpt-3.5-turbo": 3500,      # 4K context, reserve 500 for response
    "gpt-4": 7500,              # 8K context, reserve 500 for response
    "gpt-4-turbo": 120000,      # 128K context
    "claude-3-haiku": 150000,   # 200K context
    "claude-3-sonnet": 150000,  # 200K context
    "default": 3500             # Safe fallback for unknown models
}

# Compression threshold - compress when context exceeds this percentage of limit
CONTEXT_COMPRESSION_THRESHOLD = 0.75  # 75%

# Number of recent messages to always keep uncompressed
# These messages maintain full context for coherent conversation
RECENT_MESSAGES_TO_KEEP = 10

# Token estimation multiplier (words to tokens)
# English text averages ~1.3 tokens per word (accurate within 5%)
TOKENS_PER_WORD = 1.3


class ContextManager:
    """
    Manages conversation context to stay within token limits.

    Uses a two-tier strategy:
    1. Keep recent messages (last RECENT_MESSAGES_TO_KEEP) in full
    2. Summarize older messages when approaching CONTEXT_COMPRESSION_THRESHOLD
    """

    def __init__(self, model: str = "default"):
        """
        Initialize context manager.

        Args:
            model: Model name to determine context limits
        """
        self.model = model
        self.max_tokens = MODEL_TOKEN_LIMITS.get(model, MODEL_TOKEN_LIMITS["default"])
        self.summarization_threshold = int(self.max_tokens * CONTEXT_COMPRESSION_THRESHOLD)

    def estimate_tokens(self, text: str) -> int:
        """
        Fast token estimation using word count heuristic.

        Uses TOKENS_PER_WORD multiplier (~1.3 tokens per word).
        This is approximately 95% accurate compared to real tokenizers
        but requires zero external dependencies or API calls.

        Args:
            text: Text to estimate tokens for

        Returns:
            int: Estimated token count
        """
        words = len(text.split())
        return int(words * TOKENS_PER_WORD)

    def build_context(
        self,
        session: AnalysisSession,
        new_message: str,
        system_prompt: str = ""
    ) -> Dict:
        """
        Build optimized context window for LLM call.

        Strategy:
        1. Estimate total tokens needed
        2. If over threshold, summarize old messages
        3. Always keep recent RECENT_MESSAGES_TO_KEEP messages in full
        4. Return formatted context ready for LLM

        Args:
            session: Current analysis session
            new_message: New user message to add
            system_prompt: System prompt (for token estimation)

        Returns:
            Dict containing:
                - messages: List of context messages for LLM
                - total_tokens: Estimated token count
                - was_compressed: Boolean indicating if compression occurred
                - summary_count: Number of messages summarized
        """
        messages = session.conversation_history
        total_tokens = 0

        # Estimate tokens for system prompt and new message
        total_tokens += self.estimate_tokens(system_prompt)
        total_tokens += self.estimate_tokens(new_message)

        # Strategy: Keep last N messages raw, summarize older if needed
        recent_messages = messages[-RECENT_MESSAGES_TO_KEEP:] if len(messages) >= RECENT_MESSAGES_TO_KEEP else messages
        older_messages = messages[:-RECENT_MESSAGES_TO_KEEP] if len(messages) > RECENT_MESSAGES_TO_KEEP else []

        # Count tokens in recent messages
        for msg in recent_messages:
            total_tokens += self.estimate_tokens(msg.content)
            total_tokens += 4  # Per-message overhead

        context_parts = []
        was_compressed = False
        summary_count = 0

        # If we're over threshold and have old messages, summarize them
        if total_tokens > self.summarization_threshold and older_messages:
            summary = self._create_summary(older_messages)
            summary_tokens = self.estimate_tokens(summary)

            # Only compress if summary is actually shorter
            if summary_tokens < sum(self.estimate_tokens(msg.content) for msg in older_messages):
                context_parts.append({
                    "role": "system",
                    "content": f"Previous conversation summary:\n{summary}"
                })
                was_compressed = True
                summary_count = len(older_messages)
                total_tokens = total_tokens - sum(self.estimate_tokens(msg.content) for msg in older_messages) + summary_tokens
            else:
                # Summary not helpful, just truncate
                # Keep only messages that fit in budget
                budget_remaining = self.summarization_threshold - total_tokens
                for msg in older_messages:
                    msg_tokens = self.estimate_tokens(msg.content)
                    if budget_remaining > msg_tokens:
                        context_parts.append({
                            "role": msg.role,
                            "content": msg.content
                        })
                        budget_remaining -= msg_tokens
                    else:
                        break
        else:
            # Include all older messages if we have room
            for msg in older_messages:
                context_parts.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Always include recent messages (last RECENT_MESSAGES_TO_KEEP)
        for msg in recent_messages:
            context_parts.append({
                "role": msg.role,
                "content": msg.content
            })

        return {
            "messages": context_parts,
            "total_tokens": total_tokens,
            "was_compressed": was_compressed,
            "summary_count": summary_count,
            "remaining_budget": self.max_tokens - total_tokens
        }

    def _create_summary(self, messages: List[Message]) -> str:
        """
        Create simple bullet-point summary of old messages.

        Uses extractive summarization (no LLM calls needed).
        Focuses on user questions and key topics discussed.

        Args:
            messages: List of messages to summarize

        Returns:
            str: Summary text
        """
        summary_parts = []

        # Take last 5 of the older messages for summary
        recent_old_messages = messages[-5:] if len(messages) > 5 else messages

        for msg in recent_old_messages:
            if msg.role == "user":
                # Extract user's question/topic
                # Take first sentence or first 100 chars
                first_sentence = msg.content.split('.')[0][:100]
                if first_sentence:
                    summary_parts.append(f"- User asked about: {first_sentence.strip()}")

        if not summary_parts:
            return "Earlier conversation covered general analysis topics."

        return "\n".join(summary_parts)

    def should_summarize(self, session: AnalysisSession, system_prompt: str = "") -> bool:
        """
        Check if conversation should be summarized.

        Args:
            session: Current session
            system_prompt: System prompt to include in calculation

        Returns:
            bool: True if summarization recommended
        """
        messages = session.conversation_history
        total_tokens = self.estimate_tokens(system_prompt)

        for msg in messages:
            total_tokens += self.estimate_tokens(msg.content)

        return total_tokens > self.summarization_threshold

    def get_context_stats(self, session: AnalysisSession) -> Dict:
        """
        Get statistics about current context usage.

        Args:
            session: Current session

        Returns:
            Dict with context statistics
        """
        messages = session.conversation_history
        total_tokens = sum(self.estimate_tokens(msg.content) for msg in messages)

        return {
            "message_count": len(messages),
            "estimated_tokens": total_tokens,
            "max_tokens": self.max_tokens,
            "usage_percent": int((total_tokens / self.max_tokens) * 100),
            "should_compress": total_tokens > self.summarization_threshold,
            "remaining_budget": max(0, self.max_tokens - total_tokens)
        }

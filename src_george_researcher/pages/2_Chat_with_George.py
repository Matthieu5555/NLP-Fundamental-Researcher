"""
Chat with George - Interactive discussion about analysis results.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from src_george_researcher.config import load_config, validate_config
from src_george_researcher.llm import call_llm
from src_george_researcher.prompts import get_chat_prompt


st.set_page_config(
    page_title="Chat with George",
    page_icon="G",
    layout="wide",
)


def init_chat_state():
    """Initialize chat session state."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_context" not in st.session_state:
        st.session_state.chat_context = ""
    if "chat_symbol" not in st.session_state:
        st.session_state.chat_symbol = ""


def build_analysis_context() -> str:
    """Build context from the analysis results in session state."""
    if "analysis_result" not in st.session_state or not st.session_state.analysis_result:
        return ""

    result = st.session_state.analysis_result
    context_parts = [f"Analysis for {result.symbol}:"]

    if result.recommendation and result.recommendation.success:
        context_parts.append(f"\nRECOMMENDATION:\n{result.recommendation.content}")

    if result.fundamentals_analysis and result.fundamentals_analysis.success:
        context_parts.append(f"\nFUNDAMENTALS:\n{result.fundamentals_analysis.content}")

    if result.technical_analysis and result.technical_analysis.success:
        context_parts.append(f"\nTECHNICALS:\n{result.technical_analysis.content}")

    if result.moat_analysis and result.moat_analysis.success:
        context_parts.append(f"\nMOAT:\n{result.moat_analysis.content}")

    if result.bull_thesis and result.bull_thesis.success:
        context_parts.append(f"\nBULL CASE:\n{result.bull_thesis.content}")

    if result.bear_thesis and result.bear_thesis.success:
        context_parts.append(f"\nBEAR CASE:\n{result.bear_thesis.content}")

    if hasattr(result, 'swot_analysis') and result.swot_analysis and result.swot_analysis.success:
        context_parts.append(f"\nSWOT:\n{result.swot_analysis.content}")

    if result.sentiment_report:
        context_parts.append(f"\nSENTIMENT:\n{result.sentiment_report[:1000]}")

    return "\n".join(context_parts)


def chat_with_george(user_message: str, context: str, ticker: str, config) -> str:
    """Send a message to George and get a response."""
    system_prompt = get_chat_prompt(ticker=ticker, context=context)

    response = call_llm(
        config.openrouter_api_key,
        config.openrouter_model,
        system_prompt,
        user_message,
        temperature=0.7,
    )

    if response.success:
        return response.content
    else:
        return f"Sorry, I encountered an error: {response.error}"


def main():
    init_chat_state()

    st.title("Chat with George")
    st.caption("Discuss your analysis results or ask follow-up questions")

    config = load_config()
    is_valid, errors = validate_config(config)

    if not is_valid:
        st.error("API not configured. Set OPENROUTER_API_KEY in .env file.")
        return

    # Check if we have analysis results to discuss
    has_analysis = "analysis_result" in st.session_state and st.session_state.analysis_result
    current_symbol = st.session_state.get("current_symbol", "")

    if has_analysis:
        st.info(f"Discussing analysis for: **{current_symbol}**")

        # Check if symbol changed, reset chat if so
        if st.session_state.chat_symbol != current_symbol:
            st.session_state.chat_messages = []
            st.session_state.chat_symbol = current_symbol
            st.session_state.chat_context = build_analysis_context()
    else:
        st.warning("No analysis loaded. Run an analysis from the main page first, then come back to chat.")
        st.info("Go to the main page, enter a stock symbol, and click 'Run Analysis'")
        return

    # Suggested questions
    st.markdown("**Suggested questions:**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Why did you give this recommendation?"):
            st.session_state.pending_question = "Why did you give this recommendation? What were the key factors?"
        if st.button("What are the biggest risks?"):
            st.session_state.pending_question = "What are the biggest risks I should be aware of with this stock?"
    with col2:
        if st.button("Defend the bull case"):
            st.session_state.pending_question = "Play devil's advocate - why might the bull case be wrong?"
        if st.button("What would change your view?"):
            st.session_state.pending_question = "What new information would make you change your recommendation?"

    st.divider()

    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle pending question from buttons
    if "pending_question" in st.session_state:
        user_input = st.session_state.pending_question
        del st.session_state.pending_question
    else:
        user_input = st.chat_input("Ask George about the analysis...")

    if user_input:
        # Add user message
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Get George's response
        with st.chat_message("assistant"):
            with st.spinner("George is thinking..."):
                response = chat_with_george(
                    user_input,
                    st.session_state.chat_context,
                    st.session_state.chat_symbol,
                    config,
                )
                st.markdown(response)

        # Save response
        st.session_state.chat_messages.append({"role": "assistant", "content": response})
        st.rerun()

    # Clear chat button
    if st.session_state.chat_messages:
        if st.button("Clear Chat"):
            st.session_state.chat_messages = []
            st.rerun()


if __name__ == "__main__":
    main()

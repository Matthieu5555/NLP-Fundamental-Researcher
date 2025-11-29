"""
Chat API endpoints.

Handles conversational interactions with the financial analyst.
"""

from flask import Blueprint, request, jsonify, Response
from core.session import session_manager
from core.belief_extraction import update_report_from_conversation
import time
import json
import sys
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import via wrapper to handle relative imports
from agents.llm_wrapper import get_llm_response

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/stream', methods=['GET'])
def stream_chat():
    """
    Stream chat responses using Server-Sent Events.

    Query parameters:
        session_id: Analysis session ID
        message: User message

    Returns:
        SSE stream of AI response tokens
    """
    session_id = request.args.get('session_id')
    message = request.args.get('message')

    if not session_id:
        return jsonify({'error': 'session_id required'}), 400

    if not message:
        return jsonify({'error': 'message required'}), 400

    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    # Add user message to conversation history
    session.add_message('user', message)

    def generate():
        """Stream AI response tokens."""
        try:
            logger.info(f"Chat request for session {session_id}, ticker {session.ticker}, message: {message[:100]}")

            # Get report summary for context
            report_summary = ""
            if session.report_state:
                report_summary = f"Analysis for {session.ticker}:\n"
                for section_id, section in list(session.report_state.sections.items())[:3]:
                    # Include first 200 chars of each section
                    report_summary += f"\n{section.title}:\n{section.content[:200]}...\n"

            # Build system prompt
            system_prompt = f"""You are a financial analyst assistant analyzing {session.ticker}.
Answer questions based on the analysis report and your knowledge.
Be concise, factual, and cite specific numbers when possible.

Recent analysis:
{report_summary}"""

            # Use ContextManager to build optimized context window
            from core.context_manager import ContextManager

            model = session.metadata.get('model', 'default')
            context_mgr = ContextManager(model=model)
            context = context_mgr.build_context(session, message, system_prompt)

            logger.info(f"Context built: {context['total_tokens']} tokens, compressed: {context['was_compressed']}")

            # Build conversation context from managed messages
            conversation_context = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in context['messages']
            ])

            # Update system prompt with conversation context
            full_system_prompt = f"{system_prompt}\n\nPrevious conversation:\n{conversation_context}"

            logger.info("Calling LLM...")

            # Get LLM response
            response_text = get_llm_response(
                prompt=message,
                system_prompt=full_system_prompt,
                temperature=0.7
            )

            logger.info(f"LLM response received, length: {len(response_text)}")

            # Stream the response word by word
            words = response_text.split()
            for word in words:
                chunk = word + " "
                chunk_escaped = chunk.replace("\n", "<br>")
                yield f"data: {chunk_escaped}\n\n"
                time.sleep(0.02)

            yield "data: [DONE]\n\n"

            # Add assistant response to conversation history
            session.add_message('assistant', response_text, metadata={
                'token_count': len(response_text.split()),
                'model': 'openrouter',
                'context_compressed': context['was_compressed'],
                'context_tokens': context['total_tokens']
            })

            # Update report based on conversation
            report_updated = update_report_from_conversation(
                message,
                response_text,
                session
            )

            # Save session to disk after each conversation turn
            session_manager.update_session(session_id)

            if report_updated:
                logger.info("Report updated from conversation")
                # Send event to frontend to refresh report
                yield f"data: {json.dumps({'event': 'report_updated'})}\n\n"

            logger.info("Chat response completed successfully")

        except Exception as e:
            import traceback
            error_msg = f"Chat error: {str(e)}"
            logger.error(f"ERROR in chat: {traceback.format_exc()}")
            yield f"data: {error_msg}\n\n"
            yield "data: [DONE]\n\n"

    return Response(generate(), content_type='text/event-stream')


@chat_bp.route('/message', methods=['POST'])
def send_message():
    """
    Send a message and get complete response (non-streaming).

    Request body:
        {
            "session_id": "uuid",
            "message": "What is the P/E ratio?"
        }

    Returns:
        {
            "response": "...",
            "session_id": "uuid",
            "metadata": {...}
        }
    """
    data = request.get_json()

    if not data or 'session_id' not in data or 'message' not in data:
        return jsonify({'error': 'session_id and message required'}), 400

    session_id = data['session_id']
    message = data['message']

    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    # Add user message
    session.add_message('user', message)

    # TODO: Get LLM response
    response_text = f"Mock response to: {message}"

    # Add assistant message
    session.add_message('assistant', response_text)

    return jsonify({
        'response': response_text,
        'session_id': session_id,
        'metadata': {
            'message_count': len(session.conversation_history)
        }
    })


@chat_bp.route('/<session_id>/history', methods=['GET'])
def get_history(session_id: str):
    """
    Get conversation history for a session.

    Query parameters:
        limit: Number of recent messages to return (default: all)

    Returns:
        {
            "session_id": "uuid",
            "messages": [...]
        }
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    limit = request.args.get('limit', type=int)

    if limit:
        messages = session.get_recent_history(limit)
    else:
        messages = session.conversation_history

    return jsonify({
        'session_id': session_id,
        'messages': [
            {
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'metadata': msg.metadata
            }
            for msg in messages
        ]
    })


@chat_bp.route('/<session_id>/beliefs', methods=['GET'])
def get_beliefs(session_id: str):
    """
    Get all beliefs tracked for this session.

    Returns:
        {
            "session_id": "uuid",
            "beliefs": [...],
            "stats": {...}
        }
    """
    session = session_manager.get_session(session_id)

    if not session:
        return jsonify({'error': 'Session not found'}), 404

    beliefs = session.belief_graph.get_all_beliefs()
    stats = session.belief_graph.get_stats()

    return jsonify({
        'session_id': session_id,
        'beliefs': [belief.to_dict() for belief in beliefs],
        'stats': stats
    })

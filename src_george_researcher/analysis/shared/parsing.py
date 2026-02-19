"""
Shared parsing utilities for LLM response processing.

Handles common patterns like markdown code block extraction and JSON parsing
from LLM responses that may contain formatting artifacts.
"""

import json
from typing import Any, Optional


def extract_json_from_llm_response(content: str) -> Any:
    """
    Extract and parse JSON from an LLM response.

    LLMs often wrap JSON in markdown code blocks (```json ... ```).
    This function strips the formatting and parses the JSON.

    Args:
        content: Raw LLM response text that may contain JSON

    Returns:
        Parsed JSON as Python object (dict, list, etc.)

    Raises:
        json.JSONDecodeError: If content is not valid JSON after extraction

    Examples:
        >>> extract_json_from_llm_response('{"key": "value"}')
        {'key': 'value'}

        >>> extract_json_from_llm_response('```json\\n{"key": "value"}\\n```')
        {'key': 'value'}
    """
    cleaned = strip_markdown_code_block(content)
    return json.loads(cleaned)


def strip_markdown_code_block(content: str) -> str:
    """
    Remove markdown code block formatting from a string.

    Handles patterns like:
        ```json
        {"key": "value"}
        ```

    And:
        ```
        {"key": "value"}
        ```

    Args:
        content: Text that may be wrapped in markdown code blocks

    Returns:
        Text with code block formatting removed
    """
    content = content.strip()

    if not content.startswith("```"):
        return content

    parts = content.split("```")
    if len(parts) < 2:
        return content

    # Take the content between the first pair of ```
    inner = parts[1]

    # Remove language identifier if present (e.g., "json", "python")
    if inner.startswith("json"):
        inner = inner[4:]
    elif inner.startswith("python"):
        inner = inner[6:]

    return inner.strip()


def safe_extract_json(content: str, default: Optional[Any] = None) -> Optional[Any]:
    """
    Safely extract JSON from LLM response, returning default on failure.

    Unlike extract_json_from_llm_response, this does not raise on invalid JSON.

    Args:
        content: Raw LLM response text
        default: Value to return if parsing fails (default: None)

    Returns:
        Parsed JSON or default value
    """
    try:
        return extract_json_from_llm_response(content)
    except (json.JSONDecodeError, ValueError):
        return default

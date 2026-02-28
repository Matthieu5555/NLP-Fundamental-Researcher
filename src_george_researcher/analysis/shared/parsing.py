"""
Shared parsing utilities for LLM response processing.

Handles common patterns like markdown code block extraction and JSON parsing
from LLM responses that may contain formatting artifacts.
"""

import json
import re
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
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # strip_markdown_code_block requires fences at the start of the string.
        # If that failed, try finding fences anywhere (LLMs often add preamble).
        fenced = _extract_fenced_content(content)
        if fenced is not None:
            return json.loads(fenced)
        raise


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
    Falls back to repair_truncated_json when standard parsing fails, because
    LLMs frequently truncate responses mid-string or mid-object.

    Args:
        content: Raw LLM response text
        default: Value to return if parsing fails (default: None)

    Returns:
        Parsed JSON or default value
    """
    try:
        return extract_json_from_llm_response(content)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting from code fences anywhere in text (prose before fence)
    fenced = _extract_fenced_content(content)
    if fenced is not None:
        try:
            return json.loads(fenced)
        except (json.JSONDecodeError, ValueError):
            pass

    # Try to find a complete JSON object/array embedded in prose without fences
    parsed = _extract_first_json_value(content)
    if parsed is not None:
        return parsed

    # Last resort: repair the whole stripped content
    try:
        cleaned = strip_markdown_code_block(content)
        repaired = repair_truncated_json(cleaned)
        return json.loads(repaired)
    except (json.JSONDecodeError, ValueError):
        return default


def _extract_fenced_content(text: str) -> Optional[str]:
    """
    Extract content from markdown code fences anywhere in the text.

    Unlike strip_markdown_code_block (which requires fences at the start),
    this finds fences preceded by arbitrary prose, which is common when
    LLMs write "Here is the analysis:" before the JSON block.

    Returns:
        The content between the fences, or None if no fences found.
    """
    match = re.search(r'```(?:json|python)?\s*\n?(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_first_json_value(text: str) -> Optional[Any]:
    """
    Parse the first complete JSON object or array from a string.

    LLMs sometimes prefix JSON with prose ("Here is the analysis:") or
    append commentary after it. This finds the first { or [ and uses
    raw_decode to parse exactly one JSON value, ignoring trailing text.

    Returns:
        Parsed JSON value, or None if no valid JSON found.
    """
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            try:
                obj, _ = decoder.raw_decode(text, i)
                return obj
            except json.JSONDecodeError:
                # This opening brace wasn't the start of valid JSON;
                # keep scanning in case there's another one.
                continue
    return None


def repair_truncated_json(text: str) -> str:
    """
    Attempt to close unterminated strings, arrays, and objects in truncated JSON.

    LLMs hit token limits and produce output like:
        {"key": "value", "other": "trunc
    or:
        {"categories": [{"name": "Val

    This function walks the string tracking open delimiters and appends
    the necessary closing characters. It is intentionally conservative:
    it only appends closers, never removes or rearranges content.

    Args:
        text: Potentially truncated JSON string

    Returns:
        The input with closing delimiters appended (may still be invalid
        if the truncation is too severe)
    """
    text = text.rstrip()
    if not text:
        return text

    # Track nesting: each entry is '{' or '['
    stack: list[str] = []
    in_string = False
    escape_next = False

    for ch in text:
        if escape_next:
            escape_next = False
            continue

        if ch == '\\' and in_string:
            escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == '{':
            stack.append('{')
        elif ch == '[':
            stack.append('[')
        elif ch == '}' and stack and stack[-1] == '{':
            stack.pop()
        elif ch == ']' and stack and stack[-1] == '[':
            stack.pop()

    # If we ended inside a string, close it
    if in_string:
        text += '"'

    # Remove any trailing comma before we close brackets (invalid JSON)
    text = re.sub(r',\s*$', '', text)

    # Close open delimiters in reverse order
    closers = {'{': '}', '[': ']'}
    for opener in reversed(stack):
        text += closers[opener]

    return text

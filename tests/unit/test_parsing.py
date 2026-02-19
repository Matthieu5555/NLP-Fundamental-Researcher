"""Tests for the shared parsing utilities."""

import pytest
import json

from src_george_researcher.analysis.shared.parsing import (
    extract_json_from_llm_response,
    strip_markdown_code_block,
    safe_extract_json,
)


class TestStripMarkdownCodeBlock:
    """Tests for strip_markdown_code_block function."""

    def test_plain_json_unchanged(self):
        """Plain JSON string passes through unchanged."""
        content = '{"key": "value"}'
        assert strip_markdown_code_block(content) == '{"key": "value"}'

    def test_strips_json_code_block(self):
        """Removes ```json ... ``` wrapper."""
        content = '```json\n{"key": "value"}\n```'
        assert strip_markdown_code_block(content) == '{"key": "value"}'

    def test_strips_plain_code_block(self):
        """Removes ``` ... ``` wrapper without language."""
        content = '```\n{"key": "value"}\n```'
        assert strip_markdown_code_block(content) == '{"key": "value"}'

    def test_handles_whitespace(self):
        """Handles leading/trailing whitespace."""
        content = '  ```json\n  {"key": "value"}  \n```  '
        result = strip_markdown_code_block(content)
        assert '"key"' in result
        assert '"value"' in result

    def test_no_closing_backticks(self):
        """Extracts content even without closing backticks."""
        content = '```json\n{"key": "value"}'
        # Split by ``` gives ['', 'json\n{"key": "value"}'] so it extracts the JSON
        result = strip_markdown_code_block(content)
        assert result == '{"key": "value"}'


class TestExtractJsonFromLlmResponse:
    """Tests for extract_json_from_llm_response function."""

    def test_plain_json(self):
        """Parses plain JSON."""
        result = extract_json_from_llm_response('{"name": "test"}')
        assert result == {"name": "test"}

    def test_json_in_code_block(self):
        """Parses JSON wrapped in code block."""
        content = '```json\n{"name": "test"}\n```'
        result = extract_json_from_llm_response(content)
        assert result == {"name": "test"}

    def test_json_array(self):
        """Parses JSON arrays."""
        content = '```json\n[1, 2, 3]\n```'
        result = extract_json_from_llm_response(content)
        assert result == [1, 2, 3]

    def test_invalid_json_raises(self):
        """Raises JSONDecodeError for invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            extract_json_from_llm_response('not valid json')

    def test_nested_json(self):
        """Handles nested JSON objects."""
        content = '{"outer": {"inner": [1, 2, 3]}}'
        result = extract_json_from_llm_response(content)
        assert result["outer"]["inner"] == [1, 2, 3]


class TestSafeExtractJson:
    """Tests for safe_extract_json function."""

    def test_valid_json_returns_parsed(self):
        """Returns parsed JSON for valid input."""
        result = safe_extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json_returns_default(self):
        """Returns default for invalid JSON."""
        result = safe_extract_json('not json', default=[])
        assert result == []

    def test_invalid_json_returns_none_by_default(self):
        """Returns None for invalid JSON when no default specified."""
        result = safe_extract_json('not json')
        assert result is None

    def test_code_block_json_works(self):
        """Handles code blocks in safe mode."""
        content = '```json\n{"key": "value"}\n```'
        result = safe_extract_json(content)
        assert result == {"key": "value"}

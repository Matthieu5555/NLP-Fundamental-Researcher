"""Tests for the shared parsing utilities."""

import pytest
import json

import importlib.util, pathlib, sys
_spec = importlib.util.spec_from_file_location(
    "parsing",
    pathlib.Path(__file__).resolve().parents[2] / "src_george_researcher" / "analysis" / "shared" / "parsing.py",
)
_parsing = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _parsing
_spec.loader.exec_module(_parsing)
extract_json_from_llm_response = _parsing.extract_json_from_llm_response
strip_markdown_code_block = _parsing.strip_markdown_code_block
safe_extract_json = _parsing.safe_extract_json
repair_truncated_json = _parsing.repair_truncated_json


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

    def test_truncated_string_repaired(self):
        """Recovers JSON truncated mid-string (the actual JNJ failure mode)."""
        content = '{"overall_score": 65, "summary": "Attractive risk-reward given the'
        result = safe_extract_json(content)
        assert result is not None
        assert result["overall_score"] == 65

    def test_truncated_nested_object(self):
        """Recovers JSON truncated inside a nested object."""
        content = '{"categories": [{"name": "Valuation", "score": 70'
        result = safe_extract_json(content)
        assert result is not None
        assert result["categories"][0]["name"] == "Valuation"

    def test_markdown_preamble_before_json(self):
        """Extracts JSON preceded by LLM prose."""
        content = 'Here is the analysis:\n```json\n{"key": "value"}\n```'
        result = safe_extract_json(content)
        assert result == {"key": "value"}

    def test_prose_wrapping_json_no_fences(self):
        """Extracts JSON embedded in prose without code fences."""
        content = 'Here is the result:\n{"score": 42, "label": "test"}\nHope that helps!'
        result = safe_extract_json(content)
        assert result is not None
        assert result["score"] == 42

    def test_empty_string_returns_default(self):
        """Empty LLM response returns default."""
        assert safe_extract_json("", default={"fallback": True}) == {"fallback": True}

    def test_error_prefix_returns_default(self):
        """Response starting with 'Error:' is not JSON."""
        result = safe_extract_json("Error: rate limit exceeded")
        assert result is None

    def test_valid_json_in_explanation(self):
        """Valid JSON wrapped in explanation text is extracted."""
        content = 'I analyzed the data.\n{"contradictions": []}\nLet me know if you need more.'
        result = safe_extract_json(content)
        assert result == {"contradictions": []}


class TestRepairTruncatedJson:
    """Tests for repair_truncated_json function."""

    def test_unterminated_string(self):
        """Closes an open string and its containing object."""
        result = repair_truncated_json('{"key": "val')
        parsed = json.loads(result)
        assert parsed["key"] == "val"

    def test_missing_closing_brace(self):
        """Adds missing closing brace."""
        result = repair_truncated_json('{"a": 1, "b": 2')
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_missing_closing_bracket(self):
        """Adds missing closing bracket."""
        result = repair_truncated_json('[1, 2, 3')
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_nested_truncation(self):
        """Closes multiple nesting levels."""
        result = repair_truncated_json('{"a": [{"b": 1')
        parsed = json.loads(result)
        assert parsed["a"][0]["b"] == 1

    def test_trailing_comma_removed(self):
        """Strips trailing comma before closing."""
        result = repair_truncated_json('{"a": 1,')
        parsed = json.loads(result)
        assert parsed == {"a": 1}

    def test_already_valid_json_unchanged(self):
        """Valid JSON passes through without modification."""
        original = '{"key": "value"}'
        result = repair_truncated_json(original)
        assert json.loads(result) == {"key": "value"}

    def test_empty_string(self):
        """Empty input returns empty string."""
        assert repair_truncated_json("") == ""

    def test_escaped_quotes_handled(self):
        """Escaped quotes inside strings don't confuse the tracker."""
        result = repair_truncated_json('{"msg": "he said \\"hello')
        parsed = json.loads(result)
        assert "hello" in parsed["msg"]

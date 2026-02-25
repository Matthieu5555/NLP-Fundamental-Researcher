"""Tests for the LLM client module."""

import pytest
from unittest.mock import patch, Mock
import httpx

from src_george_researcher.llm import call_llm, LLMResponse, check_connection


class TestCallLLM:
    """Tests for the call_llm function."""

    def test_successful_call(self):
        """Test a successful LLM API call."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello, world!"}}],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
            }
        }

        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = call_llm(
                api_key="test-key",
                model="moonshotai/kimi-k2.5",
                system_prompt="You are helpful.",
                user_prompt="Say hello",
            )

        assert result.success is True
        assert result.content == "Hello, world!"
        assert result.tokens_used == 60
        assert result.input_tokens == 50
        assert result.output_tokens == 10
        assert result.cost_usd > 0

    def test_http_error(self):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = call_llm(
                api_key="test-key",
                model="moonshotai/kimi-k2.5",
                system_prompt="",
                user_prompt="test",
            )

        assert result.success is False
        assert "429" in result.error
        assert result.tokens_used == 0

    def test_timeout(self):
        """Test handling of timeout errors."""
        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("timeout")

            result = call_llm(
                api_key="test-key",
                model="moonshotai/kimi-k2.5",
                system_prompt="",
                user_prompt="test",
            )

        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_master_prompt_injection(self):
        """Test that master_prompt is prepended to system prompt."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OK"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        captured_payload = None

        def capture_post(url, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get('json', {})
            return mock_response

        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = capture_post

            call_llm(
                api_key="test-key",
                model="moonshotai/kimi-k2.5",
                system_prompt="Base instructions",
                user_prompt="test",
                master_prompt="Always be concise.",
            )

        # Verify master_prompt was injected
        system_content = captured_payload["messages"][0]["content"]
        assert "Always be concise" in system_content
        assert "Base instructions" in system_content

    def test_cost_calculation(self):
        """Test that cost is calculated correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "total_tokens": 1500,
            }
        }

        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = call_llm(
                api_key="test-key",
                model="moonshotai/kimi-k2.5",
                system_prompt="",
                user_prompt="test",
            )

        # Haiku pricing: $0.25/1M input, $1.25/1M output
        # (1000/1M) * 0.25 + (500/1M) * 1.25 = 0.00025 + 0.000625 = 0.000875
        expected_cost = 0.000875
        assert abs(result.cost_usd - expected_cost) < 0.0000001


class TestLLMResponse:
    """Tests for the LLMResponse dataclass."""

    def test_immutability(self):
        """Test that LLMResponse is frozen (immutable)."""
        response = LLMResponse(
            content="test",
            model="test-model",
            tokens_used=10,
            success=True,
        )

        with pytest.raises(AttributeError):
            response.content = "modified"

    def test_default_values(self):
        """Test that optional fields have correct defaults."""
        response = LLMResponse(
            content="test",
            model="test-model",
            tokens_used=10,
            success=True,
        )

        assert response.error is None
        assert response.input_tokens == 0
        assert response.output_tokens == 0
        assert response.cost_usd == 0.0


class TestCheckConnection:
    """Tests for the check_connection function."""

    def test_successful_connection(self):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OK"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
        }

        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            success, message = check_connection("test-key", "test-model")

        assert success is True
        assert "successful" in message.lower()

    def test_failed_connection(self):
        """Test failed connection test."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            success, message = check_connection("bad-key", "test-model")

        assert success is False
        assert "failed" in message.lower()

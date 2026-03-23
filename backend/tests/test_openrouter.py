#!/usr/bin/env python3
"""
Tests for OpenRouter integration.

Tests the OpenRouterClient (llm_clients.py) and verifies
provider registration in the client registry.
"""

import pytest
import os
from unittest.mock import patch

from backend.shared.llm_clients import (
    OpenRouterClient,
    get_llm_client,
)


class TestOpenRouterClient:
    """Tests for OpenRouterClient."""

    def test_instantiation(self):
        """Should instantiate with explicit API key."""
        client = OpenRouterClient(api_key="test-key-123")
        assert client.api_key == "test-key-123"

    def test_env_var_lookup(self):
        """Should read API key from OPENROUTER_API_KEY env var."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-key-456"}):
            client = OpenRouterClient()
            assert client.api_key == "env-key-456"

    def test_env_var_empty_string(self):
        """Should treat empty env var as None."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            client = OpenRouterClient()
            assert client.api_key is None

    def test_env_var_missing(self):
        """Should return None when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            client = OpenRouterClient()
            assert client.api_key is None

    def test_calculate_cost_known_model(self):
        """Should calculate cost for known models."""
        client = OpenRouterClient(api_key="test")
        cost = client.calculate_cost("openai/gpt-4o", tokens_used=1000)
        assert cost > 0

    def test_calculate_cost_unknown_model(self):
        """Should use default pricing for unknown models."""
        client = OpenRouterClient(api_key="test")
        cost = client.calculate_cost("some-unknown/model", tokens_used=1000)
        # Default is $1/1M tokens = $0.001/1K tokens
        assert cost == (1000 / 1000) * 0.001

    def test_calculate_cost_llama_model(self):
        """Should calculate cost for Llama models."""
        client = OpenRouterClient(api_key="test")
        cost = client.calculate_cost("meta-llama/llama-3.1-70b-instruct", tokens_used=1000)
        assert cost > 0


class TestOpenRouterRegistry:
    """Tests for OpenRouter in provider registry."""

    def test_get_llm_client_openrouter(self):
        """Should return OpenRouterClient from registry."""
        client = get_llm_client("openrouter", api_key="test-key")
        assert isinstance(client, OpenRouterClient)

    def test_get_llm_client_case_insensitive(self):
        """Should handle case-insensitive provider name."""
        client = get_llm_client("OpenRouter", api_key="test-key")
        assert isinstance(client, OpenRouterClient)

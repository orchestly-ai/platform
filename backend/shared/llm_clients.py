"""
LLM Provider Clients

Unified interface for calling different LLM providers (OpenAI, Anthropic, Google, DeepSeek).
Supports measuring latency, tracking costs, and handling provider-specific formats.
"""

import time
import logging
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
import os

# Load environment variables from .env file
try:
    from pathlib import Path
    from dotenv import load_dotenv
    # Get the path to .env file relative to this file
    # llm_clients.py is in backend/shared/, .env is in agent-orchestration/
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, rely on system env vars

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized LLM response"""
    content: str
    model: str
    provider: str
    latency_ms: float
    tokens_used: int
    cost: float
    finish_reason: str
    raw_response: Optional[Dict] = None


class BaseLLMClient(ABC):
    """Base class for LLM provider clients"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._get_default_api_key()

    @abstractmethod
    def _get_default_api_key(self) -> Optional[str]:
        """Get API key from environment variables"""
        pass

    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Send completion request to LLM provider"""
        pass

    @abstractmethod
    def calculate_cost(self, model: str, tokens_used: int) -> float:
        """Calculate cost based on model and token usage"""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI API client"""

    def _get_default_api_key(self) -> Optional[str]:
        key = os.getenv("OPENAI_API_KEY")
        return key if key else None  # Treat empty string as None

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Call OpenAI API"""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.api_key)

            start_time = time.time()
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            latency_ms = (time.time() - start_time) * 1000

            choice = response.choices[0]
            tokens_used = response.usage.total_tokens if response.usage else 0
            cost = self.calculate_cost(model, tokens_used)

            return LLMResponse(
                content=choice.message.content,
                model=model,
                provider="openai",
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                cost=cost,
                finish_reason=choice.finish_reason,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None
            )

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def calculate_cost(self, model: str, tokens_used: int) -> float:
        """Calculate OpenAI cost per 1K tokens"""
        # Pricing as of 2024 (input + output average)
        pricing = {
            "gpt-4": 0.045,  # ($0.03 input + $0.06 output) / 2
            "gpt-4-turbo": 0.015,  # ($0.01 input + $0.02 output) / 2
            "gpt-4o": 0.0075,  # ($0.005 input + $0.01 output) / 2
            "gpt-4o-mini": 0.00025,  # ($0.00015 input + $0.00035 output) / 2
            "gpt-3.5-turbo": 0.001,  # ($0.0005 input + $0.0015 output) / 2
            "gpt-3.5-turbo-16k": 0.002,
        }

        # Default to gpt-4o-mini pricing if model not found
        cost_per_1k = pricing.get(model, 0.00025)
        return (tokens_used / 1000) * cost_per_1k


class AnthropicClient(BaseLLMClient):
    """Anthropic (Claude) API client"""

    def _get_default_api_key(self) -> Optional[str]:
        key = os.getenv("ANTHROPIC_API_KEY")
        return key if key else None  # Treat empty string as None

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Call Anthropic API"""
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=self.api_key)

            start_time = time.time()
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                **kwargs
            )
            latency_ms = (time.time() - start_time) * 1000

            content = response.content[0].text if response.content else ""
            tokens_used = response.usage.input_tokens + response.usage.output_tokens if response.usage else 0
            cost = self.calculate_cost(model, tokens_used)

            return LLMResponse(
                content=content,
                model=model,
                provider="anthropic",
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                cost=cost,
                finish_reason=response.stop_reason,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None
            )

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def calculate_cost(self, model: str, tokens_used: int) -> float:
        """Calculate Anthropic cost per 1K tokens"""
        # Pricing as of 2024 (input + output average)
        pricing = {
            "claude-3-opus-20240229": 0.0375,  # ($0.015 input + $0.075 output) / 2
            "claude-3-sonnet-20240229": 0.006,  # ($0.003 input + $0.015 output) / 2
            "claude-3-haiku-20240307": 0.00075,  # ($0.00025 input + $0.00125 output) / 2
            "claude-3-5-sonnet-20240620": 0.006,  # Same as sonnet
            "claude-2.1": 0.012,  # ($0.008 input + $0.024 output) / 2
            "claude-2": 0.012,
        }

        # Shortened model names
        if "opus" in model.lower():
            cost_per_1k = 0.0375
        elif "sonnet" in model.lower():
            cost_per_1k = 0.006
        elif "haiku" in model.lower():
            cost_per_1k = 0.00075
        else:
            cost_per_1k = pricing.get(model, 0.006)  # Default to sonnet pricing

        return (tokens_used / 1000) * cost_per_1k


class GoogleClient(BaseLLMClient):
    """Google (Gemini) API client"""

    def _get_default_api_key(self) -> Optional[str]:
        key = os.getenv("GOOGLE_API_KEY")
        return key if key else None  # Treat empty string as None

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Call Google Gemini API"""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)

            # Convert messages to Gemini format (simple concatenation for now)
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

            start_time = time.time()
            model_instance = genai.GenerativeModel(model)
            response = await model_instance.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
            )
            latency_ms = (time.time() - start_time) * 1000

            content = response.text if hasattr(response, 'text') else ""
            tokens_used = getattr(response, 'usage_metadata', {}).get('total_token_count', 0) if hasattr(response, 'usage_metadata') else 0
            cost = self.calculate_cost(model, tokens_used)

            return LLMResponse(
                content=content,
                model=model,
                provider="google",
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                cost=cost,
                finish_reason="stop",
                raw_response=None
            )

        except Exception as e:
            logger.error(f"Google API error: {e}")
            raise

    def calculate_cost(self, model: str, tokens_used: int) -> float:
        """Calculate Google Gemini cost per 1K tokens"""
        # Pricing as of 2024 (input + output average)
        pricing = {
            "gemini-1.5-pro": 0.00175,  # ($0.00125 input + $0.005 output) / 2
            "gemini-1.5-flash": 0.000125,  # ($0.000075 input + $0.0003 output) / 2
            "gemini-pro": 0.000375,  # ($0.00025 input + $0.0005 output) / 2
        }

        cost_per_1k = pricing.get(model, 0.000375)  # Default to gemini-pro pricing
        return (tokens_used / 1000) * cost_per_1k


class DeepSeekClient(BaseLLMClient):
    """DeepSeek API client (OpenAI-compatible)"""

    def _get_default_api_key(self) -> Optional[str]:
        key = os.getenv("DEEPSEEK_API_KEY")
        return key if key else None  # Treat empty string as None

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Call DeepSeek API (OpenAI-compatible endpoint)"""
        try:
            from openai import AsyncOpenAI

            # DeepSeek uses OpenAI-compatible API
            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1"
            )

            start_time = time.time()
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            latency_ms = (time.time() - start_time) * 1000

            choice = response.choices[0]
            tokens_used = response.usage.total_tokens if response.usage else 0
            cost = self.calculate_cost(model, tokens_used)

            return LLMResponse(
                content=choice.message.content,
                model=model,
                provider="deepseek",
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                cost=cost,
                finish_reason=choice.finish_reason,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None
            )

        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise

    def calculate_cost(self, model: str, tokens_used: int) -> float:
        """Calculate DeepSeek cost per 1K tokens"""
        # DeepSeek pricing is very competitive
        pricing = {
            "deepseek-chat": 0.0001,  # Very cheap
            "deepseek-coder": 0.0001,
        }

        cost_per_1k = pricing.get(model, 0.0001)
        return (tokens_used / 1000) * cost_per_1k


class GroqClient(BaseLLMClient):
    """Groq API client (OpenAI-compatible)"""

    def _get_default_api_key(self) -> Optional[str]:
        key = os.getenv("GROQ_API_KEY")
        return key if key else None  # Treat empty string as None

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Call Groq API (OpenAI-compatible endpoint)"""
        try:
            from openai import AsyncOpenAI

            # Groq uses OpenAI-compatible API
            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1"
            )

            start_time = time.time()
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            latency_ms = (time.time() - start_time) * 1000

            choice = response.choices[0]
            tokens_used = response.usage.total_tokens if response.usage else 0
            cost = self.calculate_cost(model, tokens_used)

            return LLMResponse(
                content=choice.message.content,
                model=model,
                provider="groq",
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                cost=cost,
                finish_reason=choice.finish_reason,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None
            )

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def calculate_cost(self, model: str, tokens_used: int) -> float:
        """Calculate Groq cost per 1K tokens"""
        # Groq pricing (very competitive, inference optimized)
        pricing = {
            "llama-3.3-70b-versatile": 0.00059,  # $0.59 per 1M tokens
            "llama-3.1-70b-versatile": 0.00059,
            "llama-3.1-8b-instant": 0.00005,  # $0.05 per 1M tokens
            "llama3-70b-8192": 0.00059,
            "llama3-8b-8192": 0.00005,
            "mixtral-8x7b-32768": 0.00024,  # $0.24 per 1M tokens
            "gemma-7b-it": 0.00007,
            "gemma2-9b-it": 0.0002,
        }

        cost_per_1k = pricing.get(model, 0.00059)  # Default to llama-70b pricing
        return (tokens_used / 1000) * cost_per_1k


# Provider registry
_provider_clients = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "google": GoogleClient,
    "deepseek": DeepSeekClient,
    "groq": GroqClient,
}


def get_llm_client(provider: str, api_key: Optional[str] = None) -> BaseLLMClient:
    """Get LLM client for provider"""
    client_class = _provider_clients.get(provider.lower())
    if not client_class:
        raise ValueError(f"Unknown provider: {provider}")

    return client_class(api_key=api_key)


async def call_llm(
    provider: str,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int = 1000,
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    **kwargs
) -> LLMResponse:
    """
    Convenience function to call any LLM provider

    Args:
        provider: Provider name (openai, anthropic, google, deepseek)
        model: Model name
        messages: List of message dicts with 'role' and 'content'
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        api_key: Optional API key (uses env vars if not provided)
        **kwargs: Additional provider-specific arguments

    Returns:
        LLMResponse with content, latency, cost, etc.
    """
    client = get_llm_client(provider, api_key)
    return await client.complete(
        messages=messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs
    )

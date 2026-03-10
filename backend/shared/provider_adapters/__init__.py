"""
Provider Adapters for Universal Schema

Each adapter handles translation between UniversalRequest/Response
and provider-specific formats.
"""

from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .deepseek_adapter import DeepSeekAdapter

__all__ = [
    "OpenAIAdapter",
    "AnthropicAdapter",
    "DeepSeekAdapter",
]


def get_adapter(provider: str):
    """Get the appropriate adapter for a provider."""
    adapters = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "deepseek": DeepSeekAdapter,
    }

    adapter_class = adapters.get(provider.lower())
    if not adapter_class:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(adapters.keys())}")

    return adapter_class()

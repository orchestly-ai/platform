"""
Pre-configured LLM Provider Catalog

Default configurations for popular LLM providers and models.
Customers can use these as starting points.
"""

from backend.shared.llm_models import LLMProvider, ModelCapability


# Provider configurations
PROVIDER_CONFIGS = {
    LLMProvider.OPENAI: {
        "name": "OpenAI",
        "description": "Industry-leading models including GPT-4 and GPT-3.5",
        "api_endpoint": "https://api.openai.com/v1",
        "models": [
            {
                "model_name": "gpt-4-turbo",
                "display_name": "GPT-4 Turbo",
                "description": "Most capable model, best for complex tasks",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.FUNCTION_CALLING,
                    ModelCapability.JSON_MODE,
                    ModelCapability.VISION,
                    ModelCapability.LONG_CONTEXT,
                ],
                "max_tokens": 128000,
                "input_cost_per_1m_tokens": 10.00,
                "output_cost_per_1m_tokens": 30.00,
                "supports_streaming": True,
                "supports_function_calling": True,
            },
            {
                "model_name": "gpt-4",
                "display_name": "GPT-4",
                "description": "High intelligence model",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.FUNCTION_CALLING,
                    ModelCapability.REASONING,
                ],
                "max_tokens": 8192,
                "input_cost_per_1m_tokens": 30.00,
                "output_cost_per_1m_tokens": 60.00,
                "supports_streaming": True,
                "supports_function_calling": True,
            },
            {
                "model_name": "gpt-3.5-turbo",
                "display_name": "GPT-3.5 Turbo",
                "description": "Fast and cost-effective for simple tasks",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.FUNCTION_CALLING,
                ],
                "max_tokens": 16385,
                "input_cost_per_1m_tokens": 0.50,
                "output_cost_per_1m_tokens": 1.50,
                "supports_streaming": True,
                "supports_function_calling": True,
            },
        ]
    },

    LLMProvider.ANTHROPIC: {
        "name": "Anthropic (Claude)",
        "description": "Claude models with strong reasoning and safety",
        "api_endpoint": "https://api.anthropic.com/v1",
        "models": [
            {
                "model_name": "claude-3-opus-20240229",
                "display_name": "Claude 3 Opus",
                "description": "Most powerful model for complex tasks",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.VISION,
                ],
                "max_tokens": 200000,
                "input_cost_per_1m_tokens": 15.00,
                "output_cost_per_1m_tokens": 75.00,
                "supports_streaming": True,
                "supports_function_calling": False,
            },
            {
                "model_name": "claude-3-sonnet-20240229",
                "display_name": "Claude 3 Sonnet",
                "description": "Balanced performance and cost",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.VISION,
                ],
                "max_tokens": 200000,
                "input_cost_per_1m_tokens": 3.00,
                "output_cost_per_1m_tokens": 15.00,
                "supports_streaming": True,
                "supports_function_calling": False,
            },
            {
                "model_name": "claude-3-haiku-20240307",
                "display_name": "Claude 3 Haiku",
                "description": "Fastest and most cost-effective",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_GENERATION,
                ],
                "max_tokens": 200000,
                "input_cost_per_1m_tokens": 0.25,
                "output_cost_per_1m_tokens": 1.25,
                "supports_streaming": True,
                "supports_function_calling": False,
            },
        ]
    },

    LLMProvider.GOOGLE: {
        "name": "Google (Gemini)",
        "description": "Google's multimodal AI models",
        "api_endpoint": "https://generativelanguage.googleapis.com/v1",
        "models": [
            {
                "model_name": "gemini-pro",
                "display_name": "Gemini Pro",
                "description": "Best for text-based tasks",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.MULTILINGUAL,
                ],
                "max_tokens": 32768,
                "input_cost_per_1m_tokens": 0.50,
                "output_cost_per_1m_tokens": 1.50,
                "supports_streaming": True,
                "supports_function_calling": True,
            },
            {
                "model_name": "gemini-pro-vision",
                "display_name": "Gemini Pro Vision",
                "description": "Multimodal understanding",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.VISION,
                    ModelCapability.MULTILINGUAL,
                ],
                "max_tokens": 16384,
                "input_cost_per_1m_tokens": 0.50,
                "output_cost_per_1m_tokens": 1.50,
                "supports_streaming": True,
                "supports_function_calling": False,
            },
        ]
    },

    LLMProvider.LOCAL_OLLAMA: {
        "name": "Ollama (Local)",
        "description": "Run LLMs locally for privacy and cost savings",
        "api_endpoint": "http://localhost:11434",
        "models": [
            {
                "model_name": "llama2",
                "display_name": "Llama 2 (7B)",
                "description": "Open-source model for general tasks",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_GENERATION,
                ],
                "max_tokens": 4096,
                "input_cost_per_1m_tokens": 0.00,  # Free (local)
                "output_cost_per_1m_tokens": 0.00,
                "supports_streaming": True,
                "supports_function_calling": False,
            },
            {
                "model_name": "mistral",
                "display_name": "Mistral 7B",
                "description": "Fast and capable open model",
                "capabilities": [
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_GENERATION,
                ],
                "max_tokens": 8192,
                "input_cost_per_1m_tokens": 0.00,
                "output_cost_per_1m_tokens": 0.00,
                "supports_streaming": True,
                "supports_function_calling": False,
            },
        ]
    },
}


# Recommended routing strategies by use case
ROUTING_RECOMMENDATIONS = {
    "customer_support": {
        "strategy": "balanced",
        "reasoning": "Balance cost and quality for customer interactions",
        "recommended_models": ["claude-3-sonnet", "gpt-3.5-turbo"],
    },
    "code_generation": {
        "strategy": "highest_quality",
        "reasoning": "Code quality is critical",
        "recommended_models": ["gpt-4-turbo", "claude-3-opus"],
    },
    "data_analysis": {
        "strategy": "capability_match",
        "reasoning": "Need strong reasoning capabilities",
        "recommended_models": ["claude-3-opus", "gpt-4"],
    },
    "content_creation": {
        "strategy": "lowest_cost",
        "reasoning": "High volume, lower stakes",
        "recommended_models": ["gpt-3.5-turbo", "claude-3-haiku"],
    },
    "vision_tasks": {
        "strategy": "capability_match",
        "reasoning": "Require vision capabilities",
        "recommended_models": ["gpt-4-turbo", "gemini-pro-vision"],
    },
    "internal_tools": {
        "strategy": "lowest_cost",
        "reasoning": "Privacy-first, no API costs",
        "recommended_models": ["llama2", "mistral"],
    },
}

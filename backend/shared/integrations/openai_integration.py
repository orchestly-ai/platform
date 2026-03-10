"""
OpenAI Integration

Provides integration with OpenAI's GPT models for chat completion,
text generation, and embeddings.
"""

import logging
import httpx
from typing import Any, Dict, List, Optional

from .base import APIKeyIntegration, IntegrationResult

logger = logging.getLogger(__name__)


class OpenAIIntegration(APIKeyIntegration):
    """OpenAI GPT integration for chat completion and embeddings."""

    name = "openai"
    display_name = "OpenAI"
    description = "GPT-4, GPT-3.5 and other OpenAI models"
    icon_url = "https://cdn.worldvectorlogo.com/logos/openai-2.svg"
    documentation_url = "https://platform.openai.com/docs"

    BASE_URL = "https://api.openai.com/v1"

    def get_available_actions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "chat_completion",
                "description": "Generate text using chat completion API",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "description": "Array of messages in the conversation",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                    "content": {"type": "string"}
                                }
                            }
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Simple prompt (converted to user message)"
                        },
                        "system_prompt": {
                            "type": "string",
                            "description": "System prompt for context"
                        },
                        "model": {
                            "type": "string",
                            "description": "Model to use",
                            "default": "gpt-4o"
                        },
                        "temperature": {
                            "type": "number",
                            "description": "Sampling temperature (0-2)",
                            "default": 0.7
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Maximum tokens in response",
                            "default": 1000
                        }
                    }
                }
            },
            {
                "name": "embeddings",
                "description": "Generate text embeddings",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "Text to embed"
                        },
                        "model": {
                            "type": "string",
                            "default": "text-embedding-3-small"
                        }
                    },
                    "required": ["input"]
                }
            }
        ]

    async def validate_credentials(self) -> bool:
        """Validate OpenAI API key by listing models."""
        api_key = self.get_api_key()
        if not api_key:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"OpenAI credential validation failed: {e}")
            return False

    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute an OpenAI action."""
        api_key = self.get_api_key()
        if not api_key:
            return IntegrationResult(
                success=False,
                error_message="OpenAI API key not configured"
            )

        try:
            if action_name == "chat_completion":
                return await self._chat_completion(api_key, parameters)
            elif action_name == "embeddings":
                return await self._embeddings(api_key, parameters)
            else:
                return IntegrationResult(
                    success=False,
                    error_message=f"Unknown action: {action_name}"
                )
        except Exception as e:
            logger.exception(f"OpenAI action {action_name} failed: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e)
            )

    async def _chat_completion(self, api_key: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute chat completion."""
        # Build messages array
        messages = parameters.get("messages", [])

        # If simple prompt provided, convert to messages format
        if not messages:
            if parameters.get("system_prompt"):
                messages.append({"role": "system", "content": parameters["system_prompt"]})
            if parameters.get("prompt"):
                messages.append({"role": "user", "content": parameters["prompt"]})

        if not messages:
            return IntegrationResult(
                success=False,
                error_message="No prompt or messages provided"
            )

        model = parameters.get("model", self.configuration.get("default_model", "gpt-4o"))
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=60.0
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("error", {}).get("message", f"API error: {response.status_code}"),
                    error_code=str(response.status_code),
                    raw_response=error_data
                )

            data = response.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})

            return IntegrationResult(
                success=True,
                data={
                    "text": choice["message"]["content"],
                    "model": data["model"],
                    "finish_reason": choice.get("finish_reason"),
                    "tokens": {
                        "input": usage.get("prompt_tokens", 0),
                        "output": usage.get("completion_tokens", 0),
                        "total": usage.get("total_tokens", 0)
                    }
                },
                raw_response=data
            )

    async def _embeddings(self, api_key: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Generate embeddings."""
        input_text = parameters.get("input")
        if not input_text:
            return IntegrationResult(
                success=False,
                error_message="No input text provided"
            )

        model = parameters.get("model", "text-embedding-3-small")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "input": input_text
                },
                timeout=30.0
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("error", {}).get("message", f"API error: {response.status_code}"),
                    raw_response=error_data
                )

            data = response.json()
            return IntegrationResult(
                success=True,
                data={
                    "embedding": data["data"][0]["embedding"],
                    "model": data["model"],
                    "dimensions": len(data["data"][0]["embedding"])
                },
                raw_response=data
            )

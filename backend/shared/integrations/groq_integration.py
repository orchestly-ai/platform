"""
Groq Integration

Provides integration with Groq's ultra-fast inference API for
Llama, Mixtral, and other open models.
"""

import logging
import httpx
from typing import Any, Dict, List, Optional

from .base import APIKeyIntegration, IntegrationResult

logger = logging.getLogger(__name__)


class GroqIntegration(APIKeyIntegration):
    """Groq integration for Llama, Mixtral and other models."""

    name = "groq"
    display_name = "Groq (Llama, Mixtral)"
    description = "Ultra-fast inference for Llama 3, Mixtral, and other open models"
    icon_url = "https://groq.com/favicon.ico"
    documentation_url = "https://console.groq.com/docs"

    BASE_URL = "https://api.groq.com/openai/v1"

    def get_available_actions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "chat_completion",
                "description": "Generate text using Llama/Mixtral on Groq",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "description": "Array of messages in the conversation"
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
                            "default": "llama-3.1-70b-versatile"
                        },
                        "temperature": {
                            "type": "number",
                            "description": "Sampling temperature",
                            "default": 0.7
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Maximum tokens in response",
                            "default": 1000
                        }
                    }
                }
            }
        ]

    async def validate_credentials(self) -> bool:
        """Validate Groq API key."""
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
            logger.error(f"Groq credential validation failed: {e}")
            return False

    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute a Groq action."""
        api_key = self.get_api_key()
        if not api_key:
            return IntegrationResult(
                success=False,
                error_message="Groq API key not configured"
            )

        try:
            if action_name == "chat_completion":
                return await self._chat_completion(api_key, parameters)
            else:
                return IntegrationResult(
                    success=False,
                    error_message=f"Unknown action: {action_name}"
                )
        except Exception as e:
            logger.exception(f"Groq action {action_name} failed: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e)
            )

    async def _chat_completion(self, api_key: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute chat completion (OpenAI-compatible API)."""
        messages = parameters.get("messages", [])

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

        model = parameters.get("model", self.configuration.get("default_model", "llama-3.1-70b-versatile"))
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

"""
Anthropic Integration

Provides integration with Anthropic's Claude models for chat completion
and analysis tasks.
"""

import logging
import httpx
from typing import Any, Dict, List, Optional

from .base import APIKeyIntegration, IntegrationResult

logger = logging.getLogger(__name__)


class AnthropicIntegration(APIKeyIntegration):
    """Anthropic Claude integration for chat completion."""

    name = "anthropic"
    display_name = "Anthropic (Claude)"
    description = "Claude 3.5 Sonnet, Claude 3 Opus, and other Anthropic models"
    icon_url = "https://cdn.worldvectorlogo.com/logos/anthropic-1.svg"
    documentation_url = "https://docs.anthropic.com"

    BASE_URL = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

    def get_available_actions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "chat_completion",
                "description": "Generate text using Claude models",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "description": "Array of messages in the conversation",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["user", "assistant"]},
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
                            "default": "claude-3-5-sonnet-20241022"
                        },
                        "temperature": {
                            "type": "number",
                            "description": "Sampling temperature (0-1)",
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
        """Validate Anthropic API key."""
        api_key = self.get_api_key()
        if not api_key:
            return False

        try:
            # Anthropic doesn't have a simple validation endpoint,
            # so we make a minimal request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": self.API_VERSION,
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "Hi"}]
                    },
                    timeout=10.0
                )
                # 200 = success, 401 = invalid key
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Anthropic credential validation failed: {e}")
            return False

    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute an Anthropic action."""
        api_key = self.get_api_key()
        if not api_key:
            return IntegrationResult(
                success=False,
                error_message="Anthropic API key not configured"
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
            logger.exception(f"Anthropic action {action_name} failed: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e)
            )

    async def _chat_completion(self, api_key: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute chat completion with Claude."""
        # Build messages array
        messages = parameters.get("messages", [])

        # If simple prompt provided, convert to messages format
        if not messages:
            if parameters.get("prompt"):
                messages.append({"role": "user", "content": parameters["prompt"]})

        if not messages:
            return IntegrationResult(
                success=False,
                error_message="No prompt or messages provided"
            )

        model = parameters.get("model", self.configuration.get("default_model", "claude-3-5-sonnet-20241022"))
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)
        system_prompt = parameters.get("system_prompt", "")

        request_body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        if system_prompt:
            request_body["system"] = system_prompt

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": self.API_VERSION,
                    "Content-Type": "application/json"
                },
                json=request_body,
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
            content = data["content"][0]["text"] if data.get("content") else ""
            usage = data.get("usage", {})

            return IntegrationResult(
                success=True,
                data={
                    "text": content,
                    "model": data["model"],
                    "stop_reason": data.get("stop_reason"),
                    "tokens": {
                        "input": usage.get("input_tokens", 0),
                        "output": usage.get("output_tokens", 0),
                        "total": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    }
                },
                raw_response=data
            )

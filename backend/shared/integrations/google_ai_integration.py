"""
Google AI (Gemini) Integration

Provides integration with Google's Gemini models for chat completion
and multimodal tasks.
"""

import logging
import httpx
from typing import Any, Dict, List, Optional

from .base import APIKeyIntegration, IntegrationResult

logger = logging.getLogger(__name__)


class GoogleAIIntegration(APIKeyIntegration):
    """Google AI Gemini integration for chat completion."""

    name = "google-ai"
    display_name = "Google AI (Gemini)"
    description = "Gemini Pro, Gemini Flash and other Google AI models"
    icon_url = "https://cdn.worldvectorlogo.com/logos/google-gemini-icon.svg"
    documentation_url = "https://ai.google.dev/docs"

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def get_available_actions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "chat_completion",
                "description": "Generate text using Gemini models",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The prompt to send to Gemini"
                        },
                        "system_prompt": {
                            "type": "string",
                            "description": "System instruction for context"
                        },
                        "model": {
                            "type": "string",
                            "description": "Model to use",
                            "default": "gemini-1.5-flash"
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
                    },
                    "required": ["prompt"]
                }
            }
        ]

    async def validate_credentials(self) -> bool:
        """Validate Google AI API key."""
        api_key = self.get_api_key()
        if not api_key:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/models?key={api_key}",
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Google AI credential validation failed: {e}")
            return False

    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute a Google AI action."""
        api_key = self.get_api_key()
        if not api_key:
            return IntegrationResult(
                success=False,
                error_message="Google AI API key not configured"
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
            logger.exception(f"Google AI action {action_name} failed: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e)
            )

    async def _chat_completion(self, api_key: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute chat completion with Gemini."""
        prompt = parameters.get("prompt")
        if not prompt:
            return IntegrationResult(
                success=False,
                error_message="No prompt provided"
            )

        model = parameters.get("model", self.configuration.get("default_model", "gemini-1.5-flash"))
        temperature = parameters.get("temperature", 0.7)
        max_tokens = parameters.get("max_tokens", 1000)
        system_prompt = parameters.get("system_prompt", "")

        # Build request body
        contents = [{"parts": [{"text": prompt}]}]

        request_body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        if system_prompt:
            request_body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/models/{model}:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
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
            candidates = data.get("candidates", [])
            if not candidates:
                return IntegrationResult(
                    success=False,
                    error_message="No response generated",
                    raw_response=data
                )

            content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            usage = data.get("usageMetadata", {})

            return IntegrationResult(
                success=True,
                data={
                    "text": content,
                    "model": model,
                    "finish_reason": candidates[0].get("finishReason"),
                    "tokens": {
                        "input": usage.get("promptTokenCount", 0),
                        "output": usage.get("candidatesTokenCount", 0),
                        "total": usage.get("totalTokenCount", 0)
                    }
                },
                raw_response=data
            )

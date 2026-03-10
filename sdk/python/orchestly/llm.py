"""LLM client that routes through the Orchestly platform gateway."""

import os
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx


class LLMClient:
    """
    LLM client that proxies requests through the Orchestly platform.

    This ensures:
    - Cost tracking per agent
    - Cost limit enforcement
    - Centralized observability
    - Rate limiting
    """

    def __init__(
        self,
        agent_id: Optional[UUID] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
    ):
        """
        Initialize LLM client.

        Args:
            agent_id: Agent ID (for cost attribution)
            api_url: Platform API URL
            api_key: API key
            provider: LLM provider (openai, anthropic)
            model: Model name
            temperature: Sampling temperature
        """
        self.agent_id = agent_id
        self.api_url = api_url or os.getenv(
            "ORCHESTLY_API_URL",
            "http://localhost:8000"
        )
        self.api_key = api_key or os.getenv("ORCHESTLY_API_KEY", "")

        self.provider = provider
        self.model = model
        self.temperature = temperature

        self.client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={"X-API-Key": self.api_key} if self.api_key else {},
            timeout=60.0,
        )

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate text using LLM.

        Args:
            prompt: User prompt
            system: System message (optional)
            max_tokens: Max tokens to generate
            temperature: Override default temperature
            model: Override default model

        Returns:
            Generated text

        Raises:
            RuntimeError: If generation fails
        """
        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        return await self.chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Chat completion using LLM.

        Args:
            messages: Chat messages [{"role": "user", "content": "..."}]
            max_tokens: Max tokens to generate
            temperature: Override default temperature
            model: Override default model

        Returns:
            Generated text

        Raises:
            RuntimeError: If generation fails
        """
        try:
            response = await self.client.post(
                "/api/v1/llm/completions",
                json={
                    "agent_id": str(self.agent_id) if self.agent_id else None,
                    "provider": self.provider,
                    "model": model or self.model,
                    "messages": messages,
                    "temperature": temperature or self.temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()

            data = response.json()
            return data["content"]

        except httpx.HTTPError as e:
            raise RuntimeError(f"LLM generation failed: {e}") from e

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

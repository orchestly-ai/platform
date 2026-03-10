"""Orchestly client for communicating with the platform."""

import asyncio
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from pydantic import BaseModel


class AgentConfig(BaseModel):
    """Agent configuration."""
    name: str
    description: Optional[str] = None
    capabilities: List[str] = []
    cost_limit_daily: float = 100.0
    cost_limit_monthly: float = 3000.0
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    framework: str = "custom"
    version: str = "1.0.0"
    tags: List[str] = []
    metadata: Dict[str, Any] = {}


class TaskResult(BaseModel):
    """Task execution result."""
    task_id: UUID
    status: str
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    cost: Optional[float] = None


class OrchestlyClient:
    """
    Client for interacting with the Orchestly Platform.

    Handles:
    - Agent registration
    - Task polling and execution
    - Result submission
    - Health checks
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Orchestly client.

        Args:
            api_url: Platform API URL (default: env ORCHESTLY_API_URL or localhost)
            api_key: API key for authentication (default: env ORCHESTLY_API_KEY)
        """
        self.api_url = api_url or os.getenv(
            "ORCHESTLY_API_URL",
            "http://localhost:8000"
        )
        self.api_key = api_key or os.getenv("ORCHESTLY_API_KEY", "")

        self.client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={"X-API-Key": self.api_key} if self.api_key else {},
            timeout=30.0,
        )

        self.agent_id: Optional[UUID] = None
        self.agent_config: Optional[AgentConfig] = None

    async def register_agent(self, config: AgentConfig) -> UUID:
        """
        Register agent with the platform.

        Args:
            config: Agent configuration

        Returns:
            Agent ID

        Raises:
            RuntimeError: If registration fails
        """
        try:
            response = await self.client.post(
                "/api/v1/agents",
                json=config.model_dump(),
            )
            response.raise_for_status()

            data = response.json()
            self.agent_id = UUID(data["agent_id"])
            self.agent_config = config

            # Store API key if provided
            if "api_key" in data:
                self.api_key = data["api_key"]
                self.client.headers["X-API-Key"] = self.api_key

            return self.agent_id

        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to register agent: {e}") from e

    async def get_next_task(self, capabilities: List[str]) -> Optional[Dict[str, Any]]:
        """
        Poll for next available task matching agent capabilities.

        Args:
            capabilities: List of capabilities this agent can handle

        Returns:
            Task data or None if no tasks available
        """
        if not self.agent_id:
            raise RuntimeError("Agent not registered. Call register_agent() first.")

        try:
            response = await self.client.get(
                f"/api/v1/agents/{self.agent_id}/tasks/next",
                params={"capabilities": ",".join(capabilities)},
            )

            if response.status_code == 204:  # No tasks available
                return None

            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            # Log error but don't crash - just return None
            print(f"Error polling for tasks: {e}")
            return None

    async def submit_result(
        self,
        task_id: UUID,
        output: Dict[str, Any],
        cost: Optional[float] = None,
    ) -> None:
        """
        Submit task result.

        Args:
            task_id: Task ID
            output: Task output data
            cost: Estimated cost (USD)
        """
        try:
            response = await self.client.post(
                f"/api/v1/tasks/{task_id}/result",
                json={
                    "output": output,
                    "cost": cost,
                    "status": "completed",
                },
            )
            response.raise_for_status()

        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to submit result: {e}") from e

    async def submit_error(
        self,
        task_id: UUID,
        error: str,
    ) -> None:
        """
        Submit task error.

        Args:
            task_id: Task ID
            error: Error message
        """
        try:
            response = await self.client.post(
                f"/api/v1/tasks/{task_id}/result",
                json={
                    "status": "failed",
                    "error": error,
                },
            )
            response.raise_for_status()

        except httpx.HTTPError as e:
            print(f"Failed to submit error: {e}")

    async def send_heartbeat(self) -> None:
        """Send heartbeat to platform to indicate agent is alive."""
        if not self.agent_id:
            return

        try:
            response = await self.client.post(
                f"/api/v1/agents/{self.agent_id}/heartbeat"
            )
            response.raise_for_status()

        except httpx.HTTPError as e:
            print(f"Heartbeat failed: {e}")

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status and metrics."""
        if not self.agent_id:
            raise RuntimeError("Agent not registered")

        response = await self.client.get(f"/api/v1/agents/{self.agent_id}")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

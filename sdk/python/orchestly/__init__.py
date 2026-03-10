"""
Orchestly Python SDK

Simple Python SDK for integrating agents with the Orchestly platform.

Usage:
    from orchestly import register_agent, task

    @register_agent(
        name="email_classifier",
        capabilities=["email_triage", "sentiment_analysis"],
        cost_limit_daily=100.0
    )
    class EmailAgent:
        @task(timeout=30)
        async def classify(self, email: dict) -> dict:
            # Your agent logic here
            pass
"""

__version__ = "0.1.0"

from .client import OrchestlyClient
from .decorators import register_agent, task
from .llm import LLMClient

__all__ = [
    "OrchestlyClient",
    "register_agent",
    "task",
    "LLMClient",
]

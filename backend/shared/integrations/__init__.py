"""
Real Integration Implementations

This package contains actual SDK implementations for external services.
Each integration supports OAuth 2.0 or API key authentication.
"""

from backend.shared.integrations.base import BaseIntegration, IntegrationResult
from backend.shared.integrations.slack_integration import SlackIntegration
from backend.shared.integrations.gmail_integration import GmailIntegration
from backend.shared.integrations.discord_integration import DiscordIntegration
from backend.shared.integrations.github_integration import GitHubIntegration
from backend.shared.integrations.docusign_integration import DocuSignIntegration

# LLM Integrations
from backend.shared.integrations.openai_integration import OpenAIIntegration
from backend.shared.integrations.anthropic_integration import AnthropicIntegration
from backend.shared.integrations.google_ai_integration import GoogleAIIntegration
from backend.shared.integrations.deepseek_integration import DeepSeekIntegration
from backend.shared.integrations.groq_integration import GroqIntegration

# Registry of available integrations
INTEGRATION_REGISTRY = {
    # Communication
    "slack": SlackIntegration,
    "gmail": GmailIntegration,
    "discord": DiscordIntegration,
    "github": GitHubIntegration,
    # E-Signature
    "docusign": DocuSignIntegration,
    # LLM Providers
    "openai": OpenAIIntegration,
    "anthropic": AnthropicIntegration,
    "google-ai": GoogleAIIntegration,
    "deepseek": DeepSeekIntegration,
    "groq": GroqIntegration,
}

__all__ = [
    "BaseIntegration",
    "IntegrationResult",
    "SlackIntegration",
    "GmailIntegration",
    "DiscordIntegration",
    "GitHubIntegration",
    "DocuSignIntegration",
    "OpenAIIntegration",
    "AnthropicIntegration",
    "GoogleAIIntegration",
    "DeepSeekIntegration",
    "GroqIntegration",
    "INTEGRATION_REGISTRY",
]

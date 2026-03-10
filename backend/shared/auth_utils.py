"""
Authentication Utilities

Provides helper functions for authentication and authorization.
"""

from typing import Optional


def get_current_organization(api_key: str = None) -> str:
    """
    Get the current organization ID from the API key or context.

    For now, returns a default organization ID.
    In production, this would extract the org from the JWT or API key.
    """
    return "default"


def get_current_user_id(api_key: str = None) -> str:
    """
    Get the current user ID from the API key or context.

    For now, returns a default user ID.
    """
    return "system"

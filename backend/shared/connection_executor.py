"""
Connection Executor

Enhanced integration executor that uses the ConnectionProvider abstraction.
This provides a future-proof way to execute integrations with credentials
from multiple sources (Nango, database, custom providers).
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Type
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.integrations.base import BaseIntegration, IntegrationResult
from backend.shared.integrations import INTEGRATION_REGISTRY
from backend.shared.connection_provider import (
    ConnectionManager,
    Credentials,
    get_connection_manager,
    AuthType,
)

logger = logging.getLogger(__name__)


class ConnectionExecutor:
    """
    Execute integration actions using the ConnectionProvider abstraction.

    This executor:
    1. Uses ConnectionManager to get credentials from any configured provider
    2. Handles credential refresh automatically
    3. Falls back gracefully if providers aren't configured

    Usage:
        executor = ConnectionExecutor(db)

        # Execute using integration slug and user/org ID
        result = await executor.execute(
            integration_id="discord",
            user_id="org_123",
            action_name="send_message",
            parameters={"channel_id": "...", "content": "Hello!"}
        )
    """

    def __init__(
        self,
        db: AsyncSession,
        connection_manager: Optional[ConnectionManager] = None
    ):
        self.db = db
        self.connection_manager = connection_manager or get_connection_manager(db)

    async def execute(
        self,
        integration_id: str,
        user_id: str,
        action_name: str,
        parameters: Dict[str, Any],
    ) -> IntegrationResult:
        """
        Execute an integration action using credentials from ConnectionProvider.

        Args:
            integration_id: Integration slug (e.g., "discord", "openai")
            user_id: User or organization ID
            action_name: Name of the action to execute
            parameters: Action parameters

        Returns:
            IntegrationResult with success status and data
        """
        start_time = datetime.utcnow()

        try:
            # Get credentials via ConnectionManager
            credentials = await self.connection_manager.get_credentials(
                integration_id,
                user_id,
                auto_refresh=True  # Automatically refresh if needed
            )

            if not credentials:
                return IntegrationResult(
                    success=False,
                    error_message=f"No credentials found for {integration_id}. Please connect the integration first.",
                    error_code="NO_CREDENTIALS",
                )

            # Get integration class from registry
            integration_class = INTEGRATION_REGISTRY.get(integration_id)
            if not integration_class:
                return IntegrationResult(
                    success=False,
                    error_message=f"Integration {integration_id} not supported",
                    error_code="INTEGRATION_NOT_FOUND",
                )

            # Convert Credentials to dict for integration class
            creds_dict = self._credentials_to_dict(credentials)

            # Instantiate integration
            integration_instance = integration_class(
                credentials=creds_dict,
                configuration={},
            )

            # Execute action
            if action_name == "test_connection":
                result = await integration_instance.test_connection()
            else:
                result = await integration_instance.execute_action(action_name, parameters)

            return result

        except Exception as e:
            logger.exception(f"Connection executor failed: {e}")
            end_time = datetime.utcnow()
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                duration_ms=(end_time - start_time).total_seconds() * 1000,
            )

    def _credentials_to_dict(self, credentials: Credentials) -> Dict[str, Any]:
        """Convert Credentials object to dict for integration classes."""
        result = {}

        if credentials.auth_type == AuthType.API_KEY:
            result["api_key"] = credentials.api_key
            # Some integrations use bot_token
            if credentials.api_key and "bot_token" not in result:
                result["bot_token"] = credentials.api_key

        if credentials.access_token:
            result["access_token"] = credentials.access_token

        if credentials.refresh_token:
            result["refresh_token"] = credentials.refresh_token

        if credentials.expires_at:
            result["expires_at"] = credentials.expires_at.isoformat()

        # Include raw data for any extra fields
        result.update(credentials.raw_data)

        return result

    async def get_connection_status(
        self,
        integration_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get the connection status for an integration.

        Returns:
            Dict with connection status information
        """
        status = await self.connection_manager.get_connection_status(
            integration_id,
            user_id
        )

        return {
            "connected": status.connected,
            "integration_id": status.integration_id,
            "provider": status.provider,
            "error": status.error,
            "last_used": status.last_used.isoformat() if status.last_used else None,
        }

    async def list_user_connections(
        self,
        user_id: str
    ) -> list:
        """
        List all connections for a user.

        Returns:
            List of connection status objects
        """
        statuses = await self.connection_manager.list_connections(user_id)

        return [
            {
                "connected": s.connected,
                "integration_id": s.integration_id,
                "provider": s.provider,
                "error": s.error,
            }
            for s in statuses
        ]


# API endpoints for connection management
"""
Example FastAPI endpoints to add to your routes:

from fastapi import APIRouter, Depends, HTTPException
from backend.shared.connection_executor import ConnectionExecutor
from backend.shared.connection_provider import get_connection_manager

router = APIRouter(prefix="/connections", tags=["Connections"])

@router.post("/{integration_id}/connect")
async def initiate_connection(
    integration_id: str,
    user_id: str,  # From auth
    redirect_url: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    '''Start OAuth flow for an integration.'''
    manager = get_connection_manager(db)

    try:
        auth_url = await manager.initiate_connection(
            integration_id=integration_id,
            user_id=user_id,
            redirect_url=redirect_url
        )

        if auth_url:
            return {"auth_url": auth_url, "provider": "oauth"}
        else:
            # Direct auth (API key), no redirect needed
            return {"auth_url": None, "provider": "direct"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{integration_id}/complete")
async def complete_connection(
    integration_id: str,
    user_id: str,
    auth_data: Dict[str, Any],  # OAuth callback params or API key
    db: AsyncSession = Depends(get_db)
):
    '''Complete connection after OAuth or direct auth.'''
    manager = get_connection_manager(db)

    try:
        credentials = await manager.complete_connection(
            integration_id=integration_id,
            user_id=user_id,
            auth_data=auth_data
        )

        return {
            "success": True,
            "connected": True,
            "provider": credentials.provider_id
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{integration_id}/status")
async def get_connection_status(
    integration_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    '''Get connection status.'''
    executor = ConnectionExecutor(db)
    return await executor.get_connection_status(integration_id, user_id)


@router.delete("/{integration_id}")
async def revoke_connection(
    integration_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    '''Revoke/disconnect an integration.'''
    manager = get_connection_manager(db)
    success = await manager.revoke_connection(integration_id, user_id)

    if success:
        return {"success": True, "message": "Connection revoked"}
    else:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.get("/")
async def list_connections(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    '''List all connections for a user.'''
    executor = ConnectionExecutor(db)
    return await executor.list_user_connections(user_id)
"""

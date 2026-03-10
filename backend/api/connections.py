"""
Connection Management API

REST API endpoints for customer integration connections.
Handles both direct auth (API keys) and OAuth flows (via Nango).

Key Endpoints:
- GET /connections - List user's connections
- GET /connections/{integration_id}/config - Get auth requirements
- POST /connections/{integration_id}/connect - Connect with credentials
- POST /connections/{integration_id}/oauth/callback - OAuth callback
- GET /connections/{integration_id}/status - Check connection status
- DELETE /connections/{integration_id} - Disconnect integration
- POST /connections/{integration_id}/test - Test connection
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.database.session import get_db
from backend.shared.integration_models import (
    IntegrationModel,
    IntegrationInstallationModel,
)
from backend.shared.credential_manager import encrypt_credentials, decrypt_credentials
from backend.shared.connection_provider import (
    ConnectionManager,
    Credentials,
    AuthType as ConnectionAuthType,
    get_connection_manager,
)
from backend.integrations import (
    get_integration_registry,
    get_action_executor,
    IntegrationCredentials,
    AuthType,
)
from backend.integrations.oauth import (
    get_oauth_handler,
    get_token_storage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connections", tags=["connections"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AuthFieldSchema(BaseModel):
    """Schema for an auth field."""
    name: str
    label: str
    type: str
    required: bool
    help: Optional[str] = None
    placeholder: Optional[str] = None


class IntegrationAuthConfig(BaseModel):
    """Auth configuration for an integration."""
    integration_id: str
    integration_name: str
    auth_type: str
    requires_oauth: bool
    fields: List[AuthFieldSchema]
    oauth_provider: Optional[str] = None
    nango_public_key: Optional[str] = None


class ConnectRequest(BaseModel):
    """Request to connect an integration with credentials."""
    credentials: Dict[str, Any] = Field(..., description="Auth credentials (api_key, bot_token, etc.)")
    organization_id: Optional[str] = Field(None, description="Organization ID for multi-tenant")


class ConnectResponse(BaseModel):
    """Response after connecting."""
    success: bool
    connected: bool
    integration_id: str
    message: str
    installation_id: Optional[str] = None


class OAuthInitResponse(BaseModel):
    """Response for initiating OAuth."""
    auth_url: str
    provider: str
    state: str


class ConnectionStatus(BaseModel):
    """Status of a connection."""
    integration_id: str
    integration_name: str
    connected: bool
    auth_type: str
    last_used: Optional[datetime] = None
    installation_id: Optional[str] = None
    error: Optional[str] = None


class TestConnectionResponse(BaseModel):
    """Response from testing a connection."""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class IntegrationPaletteItem(BaseModel):
    """Integration item for workflow designer palette."""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    category: str
    icon_url: Optional[str] = None
    actions: List[str] = []
    connected: bool = False


class IntegrationPaletteResponse(BaseModel):
    """Response with all available integrations for palette."""
    integrations: List[IntegrationPaletteItem]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=List[ConnectionStatus])
async def list_connections(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all connections for the user/organization.

    Returns status of each available integration.
    """
    registry = get_integration_registry()
    connections = []

    for integration in registry.get_enabled():
        # Check if installed
        query = select(IntegrationInstallationModel).join(
            IntegrationModel,
            IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
        ).where(
            IntegrationModel.slug == integration.id
        )

        if organization_id:
            query = query.where(
                IntegrationInstallationModel.organization_id == organization_id
            )

        result = await db.execute(query)
        installation = result.scalar_one_or_none()

        connections.append(ConnectionStatus(
            integration_id=integration.id,
            integration_name=integration.display_name or integration.name,
            connected=installation is not None and installation.status == "active",
            auth_type=integration.auth.type.value,
            last_used=installation.last_execution_at if installation else None,
            installation_id=str(installation.installation_id) if installation else None,
        ))

    return connections


@router.get("/palette", response_model=IntegrationPaletteResponse)
async def get_integration_palette(
    organization_id: Optional[str] = Query(None, description="Filter by organization"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all available integrations for the workflow designer palette.

    Returns integration metadata, available actions, and connection status.
    Used by frontend to dynamically render the integration palette.
    """
    registry = get_integration_registry()
    integrations = []

    for integration in registry.get_enabled():
        # Check if connected
        query = select(IntegrationInstallationModel).join(
            IntegrationModel,
            IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
        ).where(
            IntegrationModel.slug == integration.id
        )

        if organization_id:
            query = query.where(
                IntegrationInstallationModel.organization_id == organization_id
            )

        result = await db.execute(query)
        installation = result.scalar_one_or_none()
        connected = installation is not None and installation.status == "active"

        # Get action names
        action_names = list(integration.actions.keys())

        integrations.append(IntegrationPaletteItem(
            id=integration.id,
            name=integration.name,
            display_name=integration.display_name or integration.name,
            description=integration.description,
            category=integration.category.value,
            icon_url=integration.icon_url,
            actions=action_names,
            connected=connected,
        ))

    # Sort by category and name
    integrations.sort(key=lambda x: (x.category, x.display_name))

    return IntegrationPaletteResponse(integrations=integrations)


@router.get("/{integration_id}/config", response_model=IntegrationAuthConfig)
async def get_auth_config(
    integration_id: str,
):
    """
    Get authentication configuration for an integration.

    Returns the required auth fields and OAuth config if applicable.
    Used by frontend to render the correct auth form.
    """
    registry = get_integration_registry()
    integration = registry.get(integration_id)

    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration_id}")

    auth = integration.auth

    return IntegrationAuthConfig(
        integration_id=integration.id,
        integration_name=integration.display_name or integration.name,
        auth_type=auth.type.value,
        requires_oauth=integration.requires_oauth,
        fields=[
            AuthFieldSchema(
                name=f.name,
                label=f.label,
                type=f.type.value,
                required=f.required,
                help=f.help,
                placeholder=f.placeholder,
            )
            for f in auth.fields
        ],
        oauth_provider=auth.oauth.provider if auth.oauth else None,
        nango_public_key=os.environ.get("NANGO_PUBLIC_KEY"),
    )


@router.post("/{integration_id}/connect", response_model=ConnectResponse)
async def connect_integration(
    integration_id: str,
    request: ConnectRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Connect an integration with provided credentials.

    For API key/bot token auth:
    - Validates credentials format
    - Tests connection if possible
    - Stores encrypted credentials

    For OAuth:
    - Use /oauth/init and /oauth/callback instead
    """
    registry = get_integration_registry()
    integration = registry.get(integration_id)

    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration_id}")

    # Validate required fields
    for field in integration.auth.fields:
        if field.required and field.name not in request.credentials:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field: {field.name}"
            )

    # Find or create the integration record
    result = await db.execute(
        select(IntegrationModel).where(IntegrationModel.slug == integration_id)
    )
    integration_record = result.scalar_one_or_none()

    if not integration_record:
        # Create integration record from config
        integration_record = IntegrationModel(
            name=integration.name,
            slug=integration.id,
            display_name=integration.display_name or integration.name,
            description=integration.description or f"{integration.name} integration",
            category=integration.category.value,
            integration_type="api",
            auth_type=integration.auth.type.value,
            configuration_schema={},
            supported_actions=list(integration.actions.keys()),
            version=integration.version or "1.0.0",
            provider_name=integration.name,
            status="approved",
        )
        db.add(integration_record)
        await db.flush()

    # Check for existing installation
    org_id = request.organization_id or "default-org"

    query = select(IntegrationInstallationModel).where(
        IntegrationInstallationModel.integration_id == integration_record.integration_id
    )
    query = query.where(IntegrationInstallationModel.organization_id == org_id)

    result = await db.execute(query)
    installation = result.scalar_one_or_none()

    # Encrypt credentials
    encrypted_creds = encrypt_credentials(request.credentials)

    if installation:
        # Update existing
        installation.auth_credentials = encrypted_creds
        installation.status = "active"
    else:
        # Create new installation
        installation = IntegrationInstallationModel(
            integration_id=integration_record.integration_id,
            organization_id=org_id,
            installed_version="1.0.0",
            status="active",
            auth_credentials=encrypted_creds,
            configuration={},
            installed_by="admin@example.com",
        )
        db.add(installation)

    await db.commit()
    await db.refresh(installation)

    # Test the connection
    executor = get_action_executor()
    creds = IntegrationCredentials(
        integration_id=integration_id,
        auth_type=integration.auth.type,
        data=request.credentials
    )

    test_result = await executor.test_connection(integration_id, creds)

    if not test_result.success:
        # Mark as pending if test failed
        installation.status = "pending"
        await db.commit()

        return ConnectResponse(
            success=False,
            connected=False,
            integration_id=integration_id,
            message=f"Connection test failed: {test_result.error}",
            installation_id=str(installation.installation_id),
        )

    return ConnectResponse(
        success=True,
        connected=True,
        integration_id=integration_id,
        message="Successfully connected",
        installation_id=str(installation.installation_id),
    )


@router.post("/{integration_id}/oauth/init", response_model=OAuthInitResponse)
async def init_oauth(
    integration_id: str,
    redirect_url: Optional[str] = Query(None, description="URL to redirect after OAuth"),
    organization_id: Optional[str] = Query(None),
):
    """
    Initialize OAuth flow for an integration.

    Returns the authorization URL to redirect the user to.
    Uses our custom OAuth handler (with optional Nango fallback).
    """
    registry = get_integration_registry()
    integration = registry.get(integration_id)

    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration_id}")

    if not integration.requires_oauth:
        raise HTTPException(
            status_code=400,
            detail=f"Integration {integration_id} does not use OAuth"
        )

    org_id = organization_id or "default-org"

    # Determine the OAuth provider (may differ from integration_id)
    provider = integration.auth.oauth.provider if integration.auth.oauth else integration_id

    # Build redirect URI for OAuth callback
    # In production, this should come from config
    base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    callback_uri = redirect_url or f"{base_url}/api/connections/{integration_id}/oauth/callback"

    # Use our custom OAuth handler
    oauth_handler = get_oauth_handler()

    try:
        auth_url = await oauth_handler.get_authorization_url(
            provider=provider,
            organization_id=org_id,
            redirect_uri=callback_uri,
        )

        # Extract state from URL
        import urllib.parse
        parsed = urllib.parse.urlparse(auth_url)
        params = urllib.parse.parse_qs(parsed.query)
        state = params.get("state", [""])[0]

        return OAuthInitResponse(
            auth_url=auth_url,
            provider=provider,
            state=state,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{integration_id}/oauth/callback", response_model=ConnectResponse)
async def oauth_callback(
    integration_id: str,
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(..., description="State for CSRF validation"),
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle OAuth callback after user authorization.

    Exchanges the authorization code for tokens using our custom OAuth handler.
    """
    registry = get_integration_registry()
    integration = registry.get(integration_id)

    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration_id}")

    # Determine the OAuth provider
    provider = integration.auth.oauth.provider if integration.auth.oauth else integration_id

    # Use our custom OAuth handler to exchange code for tokens
    oauth_handler = get_oauth_handler()

    try:
        token = await oauth_handler.handle_callback(
            provider=provider,
            code=code,
            state=state,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get org_id from the token (it was stored in the OAuth state)
    org_id = token.organization_id

    # Find or create integration record
    result = await db.execute(
        select(IntegrationModel).where(IntegrationModel.slug == integration_id)
    )
    integration_record = result.scalar_one_or_none()

    if not integration_record:
        integration_record = IntegrationModel(
            name=integration.name,
            slug=integration.id,
            display_name=integration.display_name,
            description=integration.description,
            category=integration.category.value,
            auth_type="oauth2",
            status="active",
        )
        db.add(integration_record)
        await db.flush()

    # Create/update installation
    query = select(IntegrationInstallationModel).where(
        IntegrationInstallationModel.integration_id == integration_record.integration_id
    )
    if org_id:
        query = query.where(IntegrationInstallationModel.organization_id == org_id)

    result = await db.execute(query)
    installation = result.scalar_one_or_none()

    # Store reference to OAuth connection (tokens are in OAuth token storage)
    oauth_data = {
        "provider": provider,
        "connected_via": "custom_oauth",
        "connected_at": datetime.utcnow().isoformat(),
        "user_info": token.user_info,
    }
    encrypted_creds = encrypt_credentials(oauth_data)

    if installation:
        installation.auth_credentials = encrypted_creds
        installation.status = "active"
        installation.updated_at = datetime.utcnow()
    else:
        installation = IntegrationInstallationModel(
            integration_id=integration_record.integration_id,
            organization_id=org_id,
            status="active",
            auth_credentials=encrypted_creds,
            configuration={},
            installed_at=datetime.utcnow(),
        )
        db.add(installation)

    await db.commit()
    await db.refresh(installation)

    return ConnectResponse(
        success=True,
        connected=True,
        integration_id=integration_id,
        message="Successfully connected via OAuth",
        installation_id=str(installation.installation_id),
    )


# Also support GET for OAuth callback (some providers redirect with GET)
@router.get("/{integration_id}/oauth/callback")
async def oauth_callback_get(
    integration_id: str,
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(..., description="State for CSRF validation"),
    error: Optional[str] = Query(None, description="Error from provider"),
    error_description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle OAuth callback via GET (browser redirect).

    Redirects to success or error page.
    """
    from fastapi.responses import RedirectResponse

    if error:
        return RedirectResponse(
            url=f"/oauth/error?provider={integration_id}&error={error_description or error}"
        )

    registry = get_integration_registry()
    integration = registry.get(integration_id)

    if not integration:
        return RedirectResponse(
            url=f"/oauth/error?provider={integration_id}&error=Integration not found"
        )

    provider = integration.auth.oauth.provider if integration.auth.oauth else integration_id
    oauth_handler = get_oauth_handler()

    try:
        token = await oauth_handler.handle_callback(
            provider=provider,
            code=code,
            state=state,
        )

        org_id = token.organization_id

        # Find or create integration record
        result = await db.execute(
            select(IntegrationModel).where(IntegrationModel.slug == integration_id)
        )
        integration_record = result.scalar_one_or_none()

        if not integration_record:
            integration_record = IntegrationModel(
                name=integration.name,
                slug=integration.id,
                display_name=integration.display_name,
                description=integration.description,
                category=integration.category.value,
                auth_type="oauth2",
                status="active",
            )
            db.add(integration_record)
            await db.flush()

        # Create/update installation
        query = select(IntegrationInstallationModel).where(
            IntegrationInstallationModel.integration_id == integration_record.integration_id
        )
        if org_id:
            query = query.where(IntegrationInstallationModel.organization_id == org_id)

        result = await db.execute(query)
        installation = result.scalar_one_or_none()

        oauth_data = {
            "provider": provider,
            "connected_via": "custom_oauth",
            "connected_at": datetime.utcnow().isoformat(),
            "user_info": token.user_info,
        }
        encrypted_creds = encrypt_credentials(oauth_data)

        if installation:
            installation.auth_credentials = encrypted_creds
            installation.status = "active"
            installation.updated_at = datetime.utcnow()
        else:
            installation = IntegrationInstallationModel(
                integration_id=integration_record.integration_id,
                organization_id=org_id,
                status="active",
                auth_credentials=encrypted_creds,
                configuration={},
            )
            db.add(installation)

        await db.commit()

        return RedirectResponse(url=f"/oauth/success?provider={integration_id}")

    except ValueError as e:
        return RedirectResponse(
            url=f"/oauth/error?provider={integration_id}&error={str(e)}"
        )


@router.get("/{integration_id}/status", response_model=ConnectionStatus)
async def get_connection_status(
    integration_id: str,
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the connection status for an integration.
    """
    registry = get_integration_registry()
    integration = registry.get(integration_id)

    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration_id}")

    # Find installation
    query = select(IntegrationInstallationModel).join(
        IntegrationModel,
        IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
    ).where(
        IntegrationModel.slug == integration_id
    )

    if organization_id:
        query = query.where(
            IntegrationInstallationModel.organization_id == organization_id
        )

    result = await db.execute(query)
    installation = result.scalar_one_or_none()

    return ConnectionStatus(
        integration_id=integration_id,
        integration_name=integration.display_name or integration.name,
        connected=installation is not None and installation.status == "active",
        auth_type=integration.auth.type.value,
        last_used=installation.last_execution_at if installation else None,
        installation_id=str(installation.installation_id) if installation else None,
        error=installation.health_check_message if installation and not installation.is_healthy else None,
    )


@router.delete("/{integration_id}", response_model=ConnectResponse)
async def disconnect_integration(
    integration_id: str,
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect an integration.

    Removes stored credentials and marks as inactive.
    """
    # Find installation
    query = select(IntegrationInstallationModel).join(
        IntegrationModel,
        IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
    ).where(
        IntegrationModel.slug == integration_id
    )

    if organization_id:
        query = query.where(
            IntegrationInstallationModel.organization_id == organization_id
        )

    result = await db.execute(query)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Clear credentials and mark inactive
    installation.auth_credentials = None
    installation.status = "inactive"
    installation.updated_at = datetime.utcnow()

    await db.commit()

    # Also revoke from Nango if OAuth
    # connection_manager = get_connection_manager()
    # await connection_manager.revoke_connection(integration_id, organization_id or "default")

    return ConnectResponse(
        success=True,
        connected=False,
        integration_id=integration_id,
        message="Successfully disconnected",
    )


@router.post("/{integration_id}/test", response_model=TestConnectionResponse)
async def test_connection(
    integration_id: str,
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Test an existing connection.

    Verifies credentials are still valid.
    """
    registry = get_integration_registry()
    integration = registry.get(integration_id)

    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration_id}")

    # Find installation
    query = select(IntegrationInstallationModel).join(
        IntegrationModel,
        IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
    ).where(
        IntegrationModel.slug == integration_id
    )

    if organization_id:
        query = query.where(
            IntegrationInstallationModel.organization_id == organization_id
        )

    result = await db.execute(query)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Decrypt credentials
    creds_data = decrypt_credentials(installation.auth_credentials) if installation.auth_credentials else {}

    creds = IntegrationCredentials(
        integration_id=integration_id,
        auth_type=integration.auth.type,
        data=creds_data
    )

    # Test connection
    executor = get_action_executor()
    test_result = await executor.test_connection(integration_id, creds)

    # Update health status
    installation.is_healthy = test_result.success
    installation.last_health_check_at = datetime.utcnow()
    installation.health_check_message = test_result.error if not test_result.success else None
    await db.commit()

    return TestConnectionResponse(
        success=test_result.success,
        message="Connection is valid" if test_result.success else f"Connection failed: {test_result.error}",
        details=test_result.data,
    )


@router.get("/{integration_id}/actions")
async def get_available_actions(
    integration_id: str,
):
    """
    Get available actions for an integration.

    Returns list of actions with their parameters.
    """
    executor = get_action_executor()
    actions = executor.get_available_actions(integration_id)

    if not actions:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration_id}")

    return {"integration_id": integration_id, "actions": actions}


class ExecuteActionRequest(BaseModel):
    """Request to execute an integration action."""
    action_name: str = Field(..., description="Name of the action to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    organization_id: Optional[str] = Field(default="default-org", description="Organization ID")


class ExecuteActionResponse(BaseModel):
    """Response from executing an integration action."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


@router.post("/{integration_id}/execute", response_model=ExecuteActionResponse)
async def execute_action(
    integration_id: str,
    request: ExecuteActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute an action on a connected integration.

    Uses the customer's stored credentials to execute the action.

    Example:
        POST /api/connections/stripe/execute
        {
            "action_name": "list_customers",
            "parameters": {"limit": 5},
            "organization_id": "default-org"
        }
    """
    registry = get_integration_registry()
    integration = registry.get(integration_id)

    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration_id}")

    # Get the installation and credentials
    query = select(IntegrationInstallationModel).join(
        IntegrationModel,
        IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
    ).where(
        IntegrationModel.slug == integration_id
    )

    if request.organization_id:
        query = query.where(
            IntegrationInstallationModel.organization_id == request.organization_id
        )

    result = await db.execute(query)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(
            status_code=404,
            detail=f"Integration not connected. Please connect {integration_id} first."
        )

    if installation.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Integration is not active. Current status: {installation.status}"
        )

    # Get credentials based on auth type
    credentials_data = {}

    if integration.auth.type == AuthType.OAUTH2:
        # For OAuth2, get token from our OAuth token storage
        provider = integration.auth.oauth.provider if integration.auth.oauth else integration_id
        oauth_handler = get_oauth_handler()

        try:
            access_token = await oauth_handler.get_access_token(
                provider=provider,
                organization_id=request.organization_id or "default-org",
                auto_refresh=True
            )

            if not access_token:
                raise HTTPException(
                    status_code=401,
                    detail=f"OAuth token not found or expired. Please reconnect {integration_id}."
                )

            # Put access token in credentials data
            credentials_data = {
                "access_token": access_token,
                "token_type": "Bearer",
            }
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Failed to get OAuth token: {str(e)}")
    else:
        # For API key/bot token, decrypt stored credentials
        try:
            credentials_data = decrypt_credentials(installation.auth_credentials)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to decrypt credentials: {str(e)}")

    # Execute the action
    executor = get_action_executor()
    creds = IntegrationCredentials(
        integration_id=integration_id,
        auth_type=integration.auth.type,
        data=credentials_data
    )

    try:
        action_result = await executor.execute(
            integration_id=integration_id,
            action_name=request.action_name,
            credentials=creds,
            parameters=request.parameters
        )

        # Update usage statistics
        installation.total_executions = (installation.total_executions or 0) + 1
        if action_result.success:
            installation.successful_executions = (installation.successful_executions or 0) + 1
        else:
            installation.failed_executions = (installation.failed_executions or 0) + 1
        installation.last_execution_at = datetime.utcnow()
        await db.commit()

        return ExecuteActionResponse(
            success=action_result.success,
            data=action_result.data,
            error=action_result.error,
            duration_ms=int(action_result.duration_ms) if action_result.duration_ms else None
        )

    except Exception as e:
        logger.error(f"Failed to execute action {request.action_name} on {integration_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

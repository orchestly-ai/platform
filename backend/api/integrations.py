"""
Integration Marketplace API

REST API endpoints for browsing, installing, and managing integrations.

Key Endpoints:
- GET /integrations - Browse marketplace with filters
- GET /integrations/{id} - Get integration details
- POST /integrations/{id}/install - One-click install
- POST /integrations/{id}/configure - Configure auth and settings
- DELETE /integrations/{id}/uninstall - Uninstall integration
- POST /integrations/{id}/execute - Execute integration action
- POST /integrations/{id}/rate - Rate and review integration

Business Impact:
- Reduces integration time from weeks to minutes (90% reduction)
- 400+ pre-built integrations to match n8n
- Network effects: more integrations = more customers
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.shared.integration_models import (
    IntegrationCategory,
    IntegrationType,
    AuthType,
    InstallationStatus,
    IntegrationDefinition,
    IntegrationDetail,
    MarketplaceFilters,
    IntegrationInstallationModel,
    IntegrationModel,
)
from backend.shared.integration_service import (
    IntegrationRegistryService,
    IntegrationInstallationService,
    IntegrationRatingService,
)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# ============================================================================
# Request/Response Models
# ============================================================================

class BrowseMarketplaceRequest(BaseModel):
    """Request for browsing marketplace."""
    category: Optional[IntegrationCategory] = None
    search_query: Optional[str] = None
    tags: Optional[List[str]] = None
    is_verified: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_free: Optional[bool] = None
    min_rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    sort_by: str = Field("popularity", pattern="^(popularity|rating|newest|name)$")
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


class BrowseMarketplaceResponse(BaseModel):
    """Response for browsing marketplace."""
    integrations: List[IntegrationDefinition]
    total_count: int
    limit: int
    offset: int
    has_more: bool


class InstallIntegrationRequest(BaseModel):
    """Request for installing an integration."""
    organization_id: str
    configuration: Optional[Dict[str, Any]] = None
    auth_credentials: Optional[Dict[str, Any]] = None


class InstallIntegrationResponse(BaseModel):
    """Response for installing an integration."""
    installation_id: UUID
    integration_id: UUID
    organization_id: str
    status: InstallationStatus
    message: str


class ConfigureIntegrationRequest(BaseModel):
    """Request for configuring an integration."""
    configuration: Dict[str, Any]
    auth_credentials: Optional[Dict[str, Any]] = None


class ConfigureIntegrationResponse(BaseModel):
    """Response for configuring an integration."""
    installation_id: UUID
    status: InstallationStatus
    message: str


class UninstallIntegrationRequest(BaseModel):
    """Request for uninstalling an integration."""
    organization_id: str


class UninstallIntegrationResponse(BaseModel):
    """Response for uninstalling an integration."""
    success: bool
    message: str


class ExecuteIntegrationActionRequest(BaseModel):
    """Request for executing an integration action."""
    installation_id: UUID
    action_name: str
    input_parameters: Dict[str, Any]
    workflow_execution_id: Optional[UUID] = None
    task_id: Optional[UUID] = None


class ExecuteIntegrationActionResponse(BaseModel):
    """Response for executing an integration action."""
    success: bool
    output_result: Optional[Any] = None
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None


class RateIntegrationRequest(BaseModel):
    """Request for rating an integration."""
    organization_id: str
    user_id: str
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None


class RateIntegrationResponse(BaseModel):
    """Response for rating an integration."""
    rating_id: UUID
    integration_id: UUID
    rating: int
    message: str


class InstallationHealthResponse(BaseModel):
    """Response for installation health check."""
    healthy: bool
    status: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    last_execution_at: Optional[datetime] = None
    last_health_check_at: Optional[datetime] = None
    health_check_message: Optional[str] = None


# ============================================================================
# Marketplace Browsing Endpoints
# ============================================================================

@router.post("/browse", response_model=BrowseMarketplaceResponse)
async def browse_marketplace(
    request: BrowseMarketplaceRequest,
    db: Session = Depends(get_db),
):
    """
    Browse integration marketplace with filters and pagination.

    This is the main discovery endpoint that powers the marketplace UI.
    Supports filtering by category, search, tags, verification status, etc.

    Example usage:
    ```
    POST /api/v1/integrations/browse
    {
        "category": "communication",
        "search_query": "slack",
        "is_verified": true,
        "sort_by": "popularity",
        "limit": 20
    }
    ```
    """
    service = IntegrationRegistryService(db)

    filters = MarketplaceFilters(
        category=request.category,
        search_query=request.search_query,
        tags=request.tags,
        is_verified=request.is_verified,
        is_featured=request.is_featured,
        is_free=request.is_free,
        min_rating=request.min_rating,
        sort_by=request.sort_by,
        limit=request.limit,
        offset=request.offset,
    )

    integrations, total_count = await service.browse_marketplace(filters)

    return BrowseMarketplaceResponse(
        integrations=integrations,
        total_count=total_count,
        limit=request.limit,
        offset=request.offset,
        has_more=(request.offset + request.limit) < total_count,
    )


@router.get("/{integration_id}", response_model=IntegrationDetail)
async def get_integration_detail(
    integration_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific integration.

    Returns complete integration metadata, configuration schemas,
    supported actions/triggers, and marketplace statistics.
    """
    service = IntegrationRegistryService(db)
    integration = await service.get_integration_detail(integration_id)

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    return integration


@router.get("/featured", response_model=List[IntegrationDefinition])
async def get_featured_integrations(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Get featured integrations for homepage/dashboard.

    Returns the most popular and verified integrations.
    """
    service = IntegrationRegistryService(db)
    return await service.get_featured_integrations(limit=limit)


@router.get("/popular", response_model=List[IntegrationDefinition])
async def get_popular_integrations(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get most popular integrations by installation count."""
    service = IntegrationRegistryService(db)
    return await service.get_popular_integrations(limit=limit)


@router.get("/category/{category}", response_model=List[IntegrationDefinition])
async def get_integrations_by_category(
    category: IntegrationCategory,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get integrations in a specific category (CRM, Communication, etc.)."""
    service = IntegrationRegistryService(db)
    return await service.get_integrations_by_category(category, limit=limit)


# ============================================================================
# Installation Management Endpoints
# ============================================================================

@router.post("/{integration_id}/install", response_model=InstallIntegrationResponse)
async def install_integration(
    integration_id: UUID,
    request: InstallIntegrationRequest,
    user_id: str = Query(..., description="User ID performing installation"),
    db: Session = Depends(get_db),
):
    """
    Install an integration for an organization (one-click install).

    This is the key endpoint that reduces integration time from weeks to minutes.
    After installation, the integration needs to be configured with auth credentials.

    Workflow:
    1. Click "Install" in marketplace
    2. POST to this endpoint
    3. Integration is installed with status=CONFIGURATION_REQUIRED
    4. Configure auth credentials via /configure endpoint
    5. Integration status changes to ACTIVE

    Example:
    ```
    POST /api/v1/integrations/{id}/install?user_id=user123
    {
        "organization_id": "org123",
        "configuration": {},
        "auth_credentials": {}
    }
    ```
    """
    service = IntegrationInstallationService(db)

    try:
        installation = await service.install_integration(
            integration_id=integration_id,
            organization_id=request.organization_id,
            installed_by=user_id,
            configuration=request.configuration,
            auth_credentials=request.auth_credentials,
        )

        return InstallIntegrationResponse(
            installation_id=installation.installation_id,
            integration_id=installation.integration_id,
            organization_id=installation.organization_id,
            status=InstallationStatus(installation.status),
            message=(
                f"Integration installed successfully. "
                f"Please configure authentication to activate."
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Installation failed: {str(e)}")


@router.post(
    "/installations/{installation_id}/configure",
    response_model=ConfigureIntegrationResponse,
)
async def configure_integration(
    installation_id: UUID,
    request: ConfigureIntegrationRequest,
    db: Session = Depends(get_db),
):
    """
    Configure an installed integration with auth credentials and settings.

    This endpoint is called after installation to set up OAuth tokens,
    API keys, or other authentication credentials. Once configured,
    the integration status changes to ACTIVE.

    Example:
    ```
    POST /api/v1/integrations/installations/{id}/configure
    {
        "configuration": {
            "workspace": "my-workspace",
            "channel": "#general"
        },
        "auth_credentials": {
            "oauth_token": "xoxb-...",
            "refresh_token": "xoxr-..."
        }
    }
    ```
    """
    service = IntegrationInstallationService(db)
    installation = await service.configure_installation(
        installation_id=installation_id,
        configuration=request.configuration,
        auth_credentials=request.auth_credentials,
    )

    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    return ConfigureIntegrationResponse(
        installation_id=installation.installation_id,
        status=InstallationStatus(installation.status),
        message="Integration configured and activated successfully.",
    )


@router.delete("/{integration_id}/uninstall", response_model=UninstallIntegrationResponse)
async def uninstall_integration(
    integration_id: UUID,
    request: UninstallIntegrationRequest,
    db: Session = Depends(get_db),
):
    """
    Uninstall an integration from an organization.

    Removes the integration and all associated configuration/credentials.
    """
    service = IntegrationInstallationService(db)
    success = await service.uninstall_integration(
        integration_id=integration_id,
        organization_id=request.organization_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Installation not found")

    return UninstallIntegrationResponse(
        success=True,
        message="Integration uninstalled successfully.",
    )


@router.get("/installations/{organization_id}", response_model=List[Dict[str, Any]])
async def list_installations(
    organization_id: str,
    status: Optional[InstallationStatus] = None,
    db: Session = Depends(get_db),
):
    """
    List all installed integrations for an organization.

    Optionally filter by installation status (ACTIVE, CONFIGURATION_REQUIRED, etc.).
    """
    service = IntegrationInstallationService(db)
    installations = await service.list_installations(organization_id, status=status)

    return [
        {
            "installation_id": str(inst.installation_id),
            "integration_id": str(inst.integration_id),
            "status": inst.status,
            "installed_version": inst.installed_version,
            "total_executions": inst.total_executions,
            "successful_executions": inst.successful_executions,
            "failed_executions": inst.failed_executions,
            "last_execution_at": inst.last_execution_at,
            "installed_at": inst.installed_at,
        }
        for inst in installations
    ]


@router.get(
    "/installations/{installation_id}/health",
    response_model=InstallationHealthResponse,
)
async def get_installation_health(
    installation_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get health status of an installation.

    Returns execution statistics and health metrics.
    """
    service = IntegrationInstallationService(db)
    health = await service.get_installation_health(installation_id)

    if "error" in health:
        raise HTTPException(status_code=404, detail=health["error"])

    return InstallationHealthResponse(**health)


@router.get("/installations/{installation_id}/details")
async def get_installation_details(
    installation_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get installation details including masked credentials.

    Shows what credentials are stored (masked for security) and configuration.
    Useful for debugging and verifying integrations are properly configured.
    """
    from sqlalchemy import select
    from backend.shared.credential_manager import get_credential_manager

    # Get installation
    stmt = select(IntegrationInstallationModel).where(
        IntegrationInstallationModel.installation_id == installation_id
    )
    result = await db.execute(stmt)
    installation = result.scalar_one_or_none()

    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    # Get integration name
    stmt = select(IntegrationModel).where(
        IntegrationModel.integration_id == installation.integration_id
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()

    # Mask credentials for display
    credential_manager = get_credential_manager()
    credentials = installation.auth_credentials or {}
    masked_credentials = credential_manager.mask_sensitive(credentials)

    # Determine what credentials are present
    has_oauth = bool(credentials.get("access_token"))
    has_api_key = bool(credentials.get("api_key") or credentials.get("bot_token") or credentials.get("personal_access_token"))

    return {
        "installation_id": str(installation.installation_id),
        "integration_id": str(installation.integration_id),
        "integration_name": integration.display_name if integration else "Unknown",
        "integration_slug": integration.slug if integration else "unknown",
        "organization_id": installation.organization_id,
        "status": installation.status,
        "installed_version": installation.installed_version,
        "installed_at": installation.installed_at.isoformat() if installation.installed_at else None,
        "installed_by": installation.installed_by,
        "configuration": installation.configuration or {},
        "credentials_summary": {
            "has_oauth_token": has_oauth,
            "has_api_key": has_api_key,
            "credential_keys": list(credentials.keys()) if credentials else [],
        },
        "masked_credentials": masked_credentials,
        "execution_stats": {
            "total_executions": installation.total_executions,
            "successful_executions": installation.successful_executions,
            "failed_executions": installation.failed_executions,
            "last_execution_at": installation.last_execution_at.isoformat() if installation.last_execution_at else None,
        },
    }


# ============================================================================
# Integration Execution Endpoints
# ============================================================================

@router.post("/{integration_id}/execute", response_model=ExecuteIntegrationActionResponse)
async def execute_integration_action(
    integration_id: UUID,
    request: ExecuteIntegrationActionRequest,
    db: Session = Depends(get_db),
):
    """
    Execute an integration action.

    This is called by agent workflows to interact with external services.
    For example:
    - Send a Slack message
    - Create a Jira ticket
    - Update a Salesforce record

    Example:
    ```
    POST /api/v1/integrations/{id}/execute
    {
        "installation_id": "...",
        "action_name": "send_message",
        "input_parameters": {
            "channel": "#general",
            "text": "Hello from agent!"
        },
        "workflow_execution_id": "..."
    }
    ```

    This uses real SDK implementations for supported integrations (Slack, Gmail,
    Discord, GitHub). Other integrations fall back to simulated execution.
    """
    from backend.shared.integration_executor import execute_integration_action as exec_action
    from backend.shared.integration_models import IntegrationExecution

    # Execute using the real integration executor
    result = await exec_action(
        db=db,
        installation_id=request.installation_id,
        action_name=request.action_name,
        parameters=request.input_parameters,
    )

    # Record execution for analytics
    service = IntegrationInstallationService(db)
    started_at = datetime.utcnow()
    completed_at = datetime.utcnow()

    execution = IntegrationExecution(
        installation_id=request.installation_id,
        action_name=request.action_name,
        input_parameters=request.input_parameters,
        output_result=result.get("data"),
        success=result.get("success", False),
        error_message=result.get("error_message"),
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=result.get("duration_ms", 0),
        workflow_execution_id=request.workflow_execution_id,
        task_id=request.task_id,
    )

    await service.record_execution(execution)

    return ExecuteIntegrationActionResponse(
        success=result.get("success", False),
        output_result=result.get("data"),
        error_message=result.get("error_message"),
        duration_ms=result.get("duration_ms", 0),
    )


# ============================================================================
# Rating and Review Endpoints
# ============================================================================

@router.post("/{integration_id}/rate", response_model=RateIntegrationResponse)
async def rate_integration(
    integration_id: UUID,
    request: RateIntegrationRequest,
    db: Session = Depends(get_db),
):
    """
    Rate and review an integration.

    Users can rate integrations 1-5 stars and optionally leave a review.
    This helps other users discover high-quality integrations.

    Example:
    ```
    POST /api/v1/integrations/{id}/rate
    {
        "organization_id": "org123",
        "user_id": "user123",
        "rating": 5,
        "review": "Great integration! Works perfectly with our workflows."
    }
    ```
    """
    service = IntegrationRatingService(db)

    try:
        rating = await service.add_rating(
            integration_id=integration_id,
            organization_id=request.organization_id,
            user_id=request.user_id,
            rating=request.rating,
            review=request.review,
        )

        return RateIntegrationResponse(
            rating_id=rating.rating_id,
            integration_id=rating.integration_id,
            rating=rating.rating,
            message="Rating submitted successfully.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rating failed: {str(e)}")


@router.get("/{integration_id}/ratings", response_model=List[Dict[str, Any]])
async def get_integration_ratings(
    integration_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get ratings and reviews for an integration.

    Returns paginated list of user ratings and reviews.
    """
    service = IntegrationRatingService(db)
    ratings = await service.get_ratings(integration_id, limit=limit, offset=offset)

    return [
        {
            "rating_id": str(rating.rating_id),
            "user_id": rating.user_id,
            "rating": rating.rating,
            "review": rating.review,
            "created_at": rating.created_at,
            "updated_at": rating.updated_at,
        }
        for rating in ratings
    ]


# ============================================================================
# OAuth Flow Endpoints
# ============================================================================

class OAuthStartRequest(BaseModel):
    """Request to start OAuth flow."""
    organization_id: str
    redirect_url: Optional[str] = None


class OAuthStartResponse(BaseModel):
    """Response with OAuth authorization URL."""
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """Request with OAuth callback data."""
    code: str
    state: str
    organization_id: str


class OAuthCallbackResponse(BaseModel):
    """Response after OAuth callback."""
    success: bool
    installation_id: Optional[UUID] = None
    message: str


@router.post("/{integration_slug}/oauth/start", response_model=OAuthStartResponse)
async def start_oauth_flow(
    integration_slug: str,
    request: OAuthStartRequest,
    db: Session = Depends(get_db),
):
    """
    Start OAuth flow for an integration.

    Returns an authorization URL that the user should be redirected to.
    The state parameter should be stored and validated on callback.

    Supported integrations:
    - slack: Slack OAuth 2.0
    - gmail: Google OAuth 2.0
    - github: GitHub OAuth

    Example:
    ```
    POST /api/v1/integrations/slack/oauth/start
    {
        "organization_id": "org123"
    }
    ```
    """
    import secrets

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Get OAuth URL based on integration
    try:
        if integration_slug == "slack":
            from backend.shared.integrations.slack_integration import get_slack_oauth_url
            auth_url = get_slack_oauth_url(state)
        elif integration_slug == "gmail":
            from backend.shared.integrations.gmail_integration import get_gmail_oauth_url
            auth_url = get_gmail_oauth_url(state)
        elif integration_slug == "github":
            from backend.shared.integrations.github_integration import get_github_oauth_url
            auth_url = get_github_oauth_url(state)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"OAuth not supported for integration: {integration_slug}"
            )

        return OAuthStartResponse(
            authorization_url=auth_url,
            state=state,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"OAuth not configured for {integration_slug}: {str(e)}"
        )


@router.post("/{integration_slug}/oauth/callback", response_model=OAuthCallbackResponse)
async def handle_oauth_callback(
    integration_slug: str,
    request: OAuthCallbackRequest,
    user_id: str = Query("default-user", description="User ID completing OAuth"),
    db: Session = Depends(get_db),
):
    """
    Handle OAuth callback and store credentials.

    This endpoint is called after the user completes OAuth authorization.
    It exchanges the authorization code for access tokens and stores them.

    Example:
    ```
    POST /api/v1/integrations/slack/oauth/callback
    {
        "code": "oauth-code-from-provider",
        "state": "state-from-start",
        "organization_id": "org123"
    }
    ```
    """
    from sqlalchemy import select

    # Exchange code for tokens
    try:
        if integration_slug == "slack":
            from backend.shared.integrations.slack_integration import exchange_slack_code
            tokens = await exchange_slack_code(request.code)
        elif integration_slug == "gmail":
            from backend.shared.integrations.gmail_integration import exchange_gmail_code
            tokens = await exchange_gmail_code(request.code)
        elif integration_slug == "github":
            from backend.shared.integrations.github_integration import exchange_github_code
            tokens = await exchange_github_code(request.code)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"OAuth not supported for integration: {integration_slug}"
            )

        if not tokens:
            return OAuthCallbackResponse(
                success=False,
                message="Failed to exchange authorization code for tokens"
            )

        # Find or create integration installation
        # First, find the integration by slug
        stmt = select(IntegrationModel).where(IntegrationModel.slug == integration_slug)
        result = await db.execute(stmt)
        integration = result.scalar_one_or_none()

        if not integration:
            raise HTTPException(
                status_code=404,
                detail=f"Integration not found: {integration_slug}"
            )

        # Check if already installed
        service = IntegrationInstallationService(db)
        existing = await service.get_installation(
            integration.integration_id,
            request.organization_id,
        )

        if existing:
            # Update existing installation with new tokens
            existing.auth_credentials = tokens
            existing.status = InstallationStatus.ACTIVE.value
            existing.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(existing)

            return OAuthCallbackResponse(
                success=True,
                installation_id=existing.installation_id,
                message=f"{integration.display_name} reconnected successfully!"
            )
        else:
            # Create new installation
            installation = await service.install_integration(
                integration_id=integration.integration_id,
                organization_id=request.organization_id,
                installed_by=user_id,
                auth_credentials=tokens,
            )

            # Mark as active since we have valid tokens
            installation.status = InstallationStatus.ACTIVE.value
            await db.commit()
            await db.refresh(installation)

            return OAuthCallbackResponse(
                success=True,
                installation_id=installation.installation_id,
                message=f"{integration.display_name} connected successfully!"
            )

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"OAuth callback failed: {e}")
        return OAuthCallbackResponse(
            success=False,
            message=f"OAuth authentication failed: {str(e)}"
        )


@router.get("/installations/{installation_id}/actions")
async def get_installation_actions(
    installation_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get available actions for an installed integration.

    Returns the list of actions that can be executed for this integration,
    including their input/output schemas.
    """
    from backend.shared.integration_executor import get_integration_actions
    actions = await get_integration_actions(db, installation_id)

    return {"actions": actions, "count": len(actions)}


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "integration-marketplace",
        "timestamp": datetime.utcnow().isoformat(),
    }

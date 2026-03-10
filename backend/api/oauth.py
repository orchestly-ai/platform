"""
OAuth API Routes

Provides endpoints for OAuth2 authorization flow:
- GET  /api/oauth/providers          - List available OAuth providers
- GET  /api/oauth/{provider}/authorize - Start OAuth flow
- GET  /api/oauth/{provider}/callback  - Handle OAuth callback
- GET  /api/oauth/{provider}/status    - Get connection status
- POST /api/oauth/{provider}/revoke    - Revoke OAuth connection
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from backend.integrations.oauth import (
    get_oauth_handler,
    get_oauth_provider_registry,
)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


# ============================================================================
# Response Models
# ============================================================================

class OAuthProviderInfo(BaseModel):
    """OAuth provider information."""
    id: str
    name: str
    display_name: str
    description: str
    icon_url: str
    is_configured: bool


class OAuthProvidersResponse(BaseModel):
    """List of OAuth providers."""
    providers: List[OAuthProviderInfo]


class OAuthAuthorizeResponse(BaseModel):
    """Authorization URL response."""
    authorization_url: str
    state: str


class OAuthStatusResponse(BaseModel):
    """OAuth connection status."""
    connected: bool
    provider: str
    user_info: Optional[Dict[str, Any]] = None
    scopes: Optional[List[str]] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None


class OAuthCallbackSuccess(BaseModel):
    """Successful OAuth callback."""
    success: bool = True
    provider: str
    user_info: Optional[Dict[str, Any]] = None
    message: str = "Successfully connected"


# ============================================================================
# Routes
# ============================================================================

@router.get("/providers", response_model=OAuthProvidersResponse)
async def list_oauth_providers():
    """
    List all available OAuth providers.

    Returns providers that support OAuth2, indicating which are configured.
    """
    registry = get_oauth_provider_registry()
    providers = registry.list_providers()

    return OAuthProvidersResponse(
        providers=[
            OAuthProviderInfo(
                id=p.id,
                name=p.name,
                display_name=p.display_name,
                description=p.description,
                icon_url=p.icon_url,
                is_configured=p.is_configured(),
            )
            for p in providers
        ]
    )


@router.get("/{provider}/authorize")
async def start_oauth_flow(
    provider: str,
    organization_id: str = Query(..., description="Organization ID"),
    redirect_uri: str = Query(..., description="Callback URL after authorization"),
    scopes: Optional[str] = Query(None, description="Comma-separated scopes (optional)"),
    redirect: bool = Query(True, description="If true, redirects to provider. If false, returns URL."),
):
    """
    Start OAuth authorization flow.

    Generates an authorization URL and either:
    - Redirects the user to the provider (default)
    - Returns the URL for the frontend to handle

    Example:
        GET /api/oauth/google/authorize?organization_id=org-123&redirect_uri=http://localhost:3000/oauth/callback
    """
    handler = get_oauth_handler()

    # Parse scopes if provided
    scope_list = None
    if scopes:
        scope_list = [s.strip() for s in scopes.split(",")]

    try:
        auth_url = await handler.get_authorization_url(
            provider=provider,
            organization_id=organization_id,
            redirect_uri=redirect_uri,
            scopes=scope_list,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if redirect:
        return RedirectResponse(url=auth_url)
    else:
        # Extract state from URL for frontend to track
        import urllib.parse
        parsed = urllib.parse.urlparse(auth_url)
        params = urllib.parse.parse_qs(parsed.query)
        state = params.get("state", [""])[0]

        return OAuthAuthorizeResponse(
            authorization_url=auth_url,
            state=state,
        )


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State token for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from provider"),
    error_description: Optional[str] = Query(None, description="Error description"),
):
    """
    Handle OAuth callback from provider.

    The provider redirects here after user authorization.
    Exchanges the code for tokens and stores them.

    On success, redirects to a success page.
    On error, redirects to an error page.
    """
    # Handle errors from provider
    if error:
        error_msg = error_description or error
        # Redirect to error page
        return RedirectResponse(
            url=f"/oauth/error?provider={provider}&error={error_msg}"
        )

    handler = get_oauth_handler()

    try:
        token = await handler.handle_callback(
            provider=provider,
            code=code,
            state=state,
        )

        # Redirect to success page
        return RedirectResponse(
            url=f"/oauth/success?provider={provider}"
        )

    except ValueError as e:
        return RedirectResponse(
            url=f"/oauth/error?provider={provider}&error={str(e)}"
        )


@router.get("/{provider}/callback/json", response_model=OAuthCallbackSuccess)
async def oauth_callback_json(
    provider: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State token for CSRF protection"),
):
    """
    Handle OAuth callback and return JSON response.

    Alternative to redirect-based callback for SPAs.
    """
    handler = get_oauth_handler()

    try:
        token = await handler.handle_callback(
            provider=provider,
            code=code,
            state=state,
        )

        return OAuthCallbackSuccess(
            provider=provider,
            user_info=token.user_info,
            message=f"Successfully connected to {provider}",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{provider}/status", response_model=OAuthStatusResponse)
async def get_oauth_status(
    provider: str,
    organization_id: str = Query(..., description="Organization ID"),
):
    """
    Get OAuth connection status for a provider.

    Returns whether the organization is connected and connection details.
    """
    handler = get_oauth_handler()

    status = await handler.get_connection_status(provider, organization_id)

    return OAuthStatusResponse(**status)


@router.post("/{provider}/revoke")
async def revoke_oauth_connection(
    provider: str,
    organization_id: str = Query(..., description="Organization ID"),
):
    """
    Revoke OAuth connection.

    Revokes tokens at the provider (if supported) and removes local tokens.
    """
    handler = get_oauth_handler()

    success = await handler.revoke_token(provider, organization_id)

    if success:
        return {"success": True, "message": f"Disconnected from {provider}"}
    else:
        raise HTTPException(status_code=404, detail="No connection found")


@router.post("/{provider}/refresh")
async def refresh_oauth_token(
    provider: str,
    organization_id: str = Query(..., description="Organization ID"),
):
    """
    Manually refresh OAuth token.

    Normally tokens are auto-refreshed, but this allows manual refresh.
    """
    handler = get_oauth_handler()

    try:
        token = await handler.refresh_token(provider, organization_id)
        return {
            "success": True,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{provider}/token")
async def get_oauth_token(
    provider: str,
    organization_id: str = Query(..., description="Organization ID"),
):
    """
    Get current access token (for internal use).

    Returns the access token, refreshing if needed.
    This endpoint should be protected in production.
    """
    handler = get_oauth_handler()

    access_token = await handler.get_access_token(provider, organization_id)

    if not access_token:
        raise HTTPException(status_code=404, detail="No token found. Please connect first.")

    return {
        "access_token": access_token,
        "token_type": "Bearer",
    }

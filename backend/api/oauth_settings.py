"""
OAuth Settings API

Allows organizations to configure their own OAuth app credentials
for the hybrid approach.

Endpoints:
- GET  /api/settings/oauth                    - List org OAuth configs
- GET  /api/settings/oauth/{provider}         - Get config for provider
- POST /api/settings/oauth/{provider}         - Save OAuth config
- DELETE /api/settings/oauth/{provider}       - Remove custom config
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.integrations.oauth.org_config import (
    OrganizationOAuthConfig,
    get_org_oauth_config_storage,
)
from backend.integrations.oauth.providers import get_oauth_provider_registry

router = APIRouter(prefix="/api/settings/oauth", tags=["settings", "oauth"])


# ============================================================================
# Request/Response Models
# ============================================================================

class OAuthConfigInput(BaseModel):
    """Input for saving OAuth configuration."""
    client_id: str = Field(..., description="OAuth Client ID")
    client_secret: str = Field(..., description="OAuth Client Secret")
    custom_scopes: Optional[List[str]] = Field(None, description="Custom scopes (optional)")
    enabled: bool = Field(True, description="Enable this custom config")


class OAuthConfigResponse(BaseModel):
    """OAuth configuration response (secrets masked)."""
    provider: str
    client_id: str
    client_id_masked: str  # Show only last 4 chars
    has_client_secret: bool
    custom_scopes: Optional[List[str]]
    enabled: bool
    is_custom: bool  # True = org config, False = platform default
    created_at: Optional[str]
    updated_at: Optional[str]


class OAuthConfigListResponse(BaseModel):
    """List of OAuth configurations."""
    configs: List[OAuthConfigResponse]
    organization_id: str


class OAuthConfigSaveResponse(BaseModel):
    """Response after saving config."""
    success: bool
    message: str
    provider: str


# ============================================================================
# Helper Functions
# ============================================================================

def mask_client_id(client_id: str) -> str:
    """Mask client ID showing only last 4 characters."""
    if len(client_id) <= 4:
        return "****"
    return "*" * (len(client_id) - 4) + client_id[-4:]


def config_to_response(config: OrganizationOAuthConfig, is_custom: bool = True) -> OAuthConfigResponse:
    """Convert config to response model."""
    return OAuthConfigResponse(
        provider=config.provider,
        client_id=config.client_id,
        client_id_masked=mask_client_id(config.client_id),
        has_client_secret=bool(config.client_secret),
        custom_scopes=config.custom_scopes,
        enabled=config.enabled,
        is_custom=is_custom,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


# ============================================================================
# Routes
# ============================================================================

@router.get("", response_model=OAuthConfigListResponse)
async def list_oauth_configs(
    organization_id: str = Query(..., description="Organization ID"),
):
    """
    List OAuth configurations for an organization.

    Shows both custom configs and available platform defaults.
    """
    storage = get_org_oauth_config_storage()
    registry = get_oauth_provider_registry()

    # Get custom configs for this org
    custom_configs = await storage.list_for_org(organization_id)
    custom_providers = {c.provider for c in custom_configs}

    configs = []

    # Add custom configs
    for config in custom_configs:
        configs.append(config_to_response(config, is_custom=True))

    # Add platform defaults for providers without custom config
    for provider in registry.list_providers():
        if provider.id not in custom_providers:
            # Show platform default status
            configs.append(OAuthConfigResponse(
                provider=provider.id,
                client_id="(platform default)" if provider.is_configured() else "(not configured)",
                client_id_masked="(platform default)" if provider.is_configured() else "(not configured)",
                has_client_secret=provider.is_configured(),
                custom_scopes=None,
                enabled=True,
                is_custom=False,
                created_at=None,
                updated_at=None,
            ))

    return OAuthConfigListResponse(
        configs=configs,
        organization_id=organization_id,
    )


@router.get("/{provider}", response_model=OAuthConfigResponse)
async def get_oauth_config(
    provider: str,
    organization_id: str = Query(..., description="Organization ID"),
):
    """
    Get OAuth configuration for a specific provider.

    Returns custom config if set, otherwise platform default info.
    """
    storage = get_org_oauth_config_storage()
    registry = get_oauth_provider_registry()

    # Check for custom config
    custom_config = await storage.get(organization_id, provider)
    if custom_config:
        return config_to_response(custom_config, is_custom=True)

    # Check platform default
    platform_config = registry.get(provider)
    if not platform_config:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    return OAuthConfigResponse(
        provider=provider,
        client_id="(platform default)" if platform_config.is_configured() else "(not configured)",
        client_id_masked="(platform default)" if platform_config.is_configured() else "(not configured)",
        has_client_secret=platform_config.is_configured(),
        custom_scopes=None,
        enabled=True,
        is_custom=False,
        created_at=None,
        updated_at=None,
    )


@router.post("/{provider}", response_model=OAuthConfigSaveResponse)
async def save_oauth_config(
    provider: str,
    config_input: OAuthConfigInput,
    organization_id: str = Query(..., description="Organization ID"),
):
    """
    Save custom OAuth configuration for a provider.

    This allows organizations to use their own OAuth apps.
    """
    registry = get_oauth_provider_registry()
    storage = get_org_oauth_config_storage()

    # Validate provider exists
    platform_config = registry.get(provider)
    if not platform_config:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    # Validate input
    if not config_input.client_id or not config_input.client_secret:
        raise HTTPException(status_code=400, detail="Client ID and Client Secret are required")

    # Create config
    config = OrganizationOAuthConfig(
        organization_id=organization_id,
        provider=provider,
        client_id=config_input.client_id,
        client_secret=config_input.client_secret,
        custom_scopes=config_input.custom_scopes,
        enabled=config_input.enabled,
    )

    # Save (encrypted)
    await storage.save(config)

    return OAuthConfigSaveResponse(
        success=True,
        message=f"Custom OAuth configuration saved for {provider}",
        provider=provider,
    )


@router.delete("/{provider}")
async def delete_oauth_config(
    provider: str,
    organization_id: str = Query(..., description="Organization ID"),
):
    """
    Delete custom OAuth configuration.

    Organization will fall back to platform default.
    """
    storage = get_org_oauth_config_storage()

    deleted = await storage.delete(organization_id, provider)

    if deleted:
        return {
            "success": True,
            "message": f"Custom OAuth configuration removed for {provider}. Using platform default.",
        }
    else:
        return {
            "success": True,
            "message": f"No custom configuration found for {provider}. Already using platform default.",
        }


@router.get("/{provider}/redirect-uri")
async def get_redirect_uri(
    provider: str,
    base_url: str = Query(..., description="Base URL of your application"),
):
    """
    Get the redirect URI to configure in your OAuth app.

    Use this when setting up your own OAuth app at the provider.
    """
    # Normalize base URL
    base_url = base_url.rstrip("/")

    return {
        "provider": provider,
        "redirect_uri": f"{base_url}/api/oauth/{provider}/callback",
        "instructions": f"""
To configure your {provider} OAuth app:

1. Go to the {provider} developer console
2. Create a new OAuth application
3. Set the redirect URI to:
   {base_url}/api/oauth/{provider}/callback
4. Copy the Client ID and Client Secret
5. Save them using POST /api/settings/oauth/{provider}
        """.strip(),
    }

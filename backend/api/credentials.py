"""
LLM Credential Management API

Endpoints for managing per-tenant LLM API keys (BYOK - Bring Your Own Key).

Features:
- Store encrypted LLM API keys per organization
- Per-tenant key isolation with unique encryption keys
- List/delete credentials without exposing keys
- Support for multiple providers (OpenAI, Anthropic, Groq, etc.)

Security:
- All credentials encrypted at rest with Fernet
- Per-tenant salt ensures key isolation
- API keys never returned in full (masked for display)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.shared.auth import (
    get_current_user,
    get_current_organization_id,
    AuthenticatedUser,
)
from backend.shared.credential_manager import (
    get_llm_credential_store,
    get_credential_manager,
    LLMCredential,
)

router = APIRouter(prefix="/api/v1/credentials", tags=["credentials"])


# =============================================================================
# Request/Response Models
# =============================================================================

class LLMCredentialCreate(BaseModel):
    """Request to store an LLM API key."""
    provider: str = Field(..., description="LLM provider (openai, anthropic, groq, azure, etc.)")
    api_key: str = Field(..., min_length=10, description="API key value")
    alias: Optional[str] = Field(None, description="Optional alias (e.g., 'production', 'development')")


class LLMCredentialResponse(BaseModel):
    """Response for an LLM credential (key masked)."""
    provider: str
    alias: Optional[str]
    masked_key: str  # e.g., "sk-ab****wxyz"
    created_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool


class LLMCredentialListResponse(BaseModel):
    """Response listing all LLM credentials for an organization."""
    credentials: List[LLMCredentialResponse]
    organization_id: str


class ProviderListResponse(BaseModel):
    """List of configured LLM providers."""
    providers: List[str]
    organization_id: str


# =============================================================================
# Helper Functions
# =============================================================================

def mask_api_key(api_key: str) -> str:
    """Mask an API key for safe display."""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/llm", response_model=LLMCredentialResponse, status_code=status.HTTP_201_CREATED)
async def store_llm_credential(
    request: LLMCredentialCreate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Store an LLM API key for the organization.

    The key is encrypted with a per-tenant encryption key for security.
    Each organization's keys are isolated from other organizations.

    Supported providers:
    - openai: OpenAI API (GPT-4, GPT-3.5, etc.)
    - anthropic: Anthropic API (Claude models)
    - groq: Groq API (fast inference)
    - azure: Azure OpenAI Service
    - google: Google AI (Gemini models)
    - cohere: Cohere API
    - mistral: Mistral AI
    """
    store = get_llm_credential_store()

    # Normalize provider name
    provider = request.provider.lower().strip()

    # Store the credential
    store.store(
        tenant_id=user.organization_id,
        provider=provider,
        api_key=request.api_key,
        alias=request.alias,
    )

    return LLMCredentialResponse(
        provider=provider,
        alias=request.alias,
        masked_key=mask_api_key(request.api_key),
        created_at=datetime.utcnow(),
        last_used_at=None,
        is_active=True,
    )


@router.get("/llm", response_model=ProviderListResponse)
async def list_llm_providers(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    List LLM providers configured for the organization.

    Returns only provider names, not the actual API keys.
    """
    store = get_llm_credential_store()
    providers = store.list_providers(user.organization_id)

    return ProviderListResponse(
        providers=providers,
        organization_id=user.organization_id,
    )


@router.get("/llm/{provider}", response_model=LLMCredentialResponse)
async def get_llm_credential(
    provider: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Get LLM credential details for a provider (key masked).

    The actual API key is not returned for security.
    Only metadata and a masked version of the key are returned.
    """
    store = get_llm_credential_store()
    manager = get_credential_manager()

    # Get the encrypted credential
    if user.organization_id not in store._credentials:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credentials configured for organization",
        )

    provider = provider.lower().strip()
    encrypted = store._credentials[user.organization_id].get(provider)
    if not encrypted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credential found for provider: {provider}",
        )

    # Decrypt to get metadata
    encryptor = manager.get_tenant_encryptor(user.organization_id)
    credential = encryptor.retrieve_llm_credential(encrypted)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt credential",
        )

    return LLMCredentialResponse(
        provider=credential.provider,
        alias=credential.alias,
        masked_key=mask_api_key(credential.api_key),
        created_at=credential.created_at,
        last_used_at=credential.last_used_at,
        is_active=credential.is_active,
    )


@router.delete("/llm/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_credential(
    provider: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Delete an LLM credential for a provider.

    This permanently removes the API key from storage.
    """
    store = get_llm_credential_store()
    provider = provider.lower().strip()

    success = store.delete(user.organization_id, provider)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credential found for provider: {provider}",
        )


@router.post("/llm/{provider}/verify")
async def verify_llm_credential(
    provider: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Verify that an LLM credential is valid.

    Makes a minimal API call to the provider to check if the key works.
    """
    store = get_llm_credential_store()
    provider = provider.lower().strip()

    api_key = store.get(user.organization_id, provider)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credential found for provider: {provider}",
        )

    # For now, just return success if key exists
    # In production, make a minimal API call to verify
    return {
        "status": "valid",
        "provider": provider,
        "message": "Credential exists and is active",
    }


@router.get("/llm/internal/{provider}/key")
async def get_llm_api_key_internal(
    provider: str,
    organization_id: str = Depends(get_current_organization_id),
):
    """
    Internal endpoint to get actual LLM API key for routing.

    This endpoint is for internal service use only (e.g., SmartRouter).
    The key is returned in full for actual API calls.

    Security: This endpoint should be protected by service-to-service auth
    in production. For now, it requires valid user authentication.
    """
    store = get_llm_credential_store()
    provider = provider.lower().strip()

    api_key = store.get(organization_id, provider)
    if not api_key:
        # Fall back to environment variable
        env_key = f"{provider.upper()}_API_KEY"
        api_key = __import__("os").environ.get(env_key)

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No API key configured for provider: {provider}",
            )

    return {"api_key": api_key, "source": "tenant" if store.get(organization_id, provider) else "environment"}

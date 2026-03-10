"""
Prompt Registry REST API

Complete API for prompt management with versioning:
- CRUD operations for prompt templates
- Version management with semantic versioning
- Prompt rendering with variable substitution
- Usage analytics and tracking

Integrates with:
- prompt_models.py: Data models
- prompt_service.py: Business logic
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.shared.prompt_service import PromptService
from backend.shared.prompt_models import (
    PromptTemplateModel,
    PromptVersionModel,
    PromptUsageStatsModel,
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class PromptTemplateCreateRequest(BaseModel):
    """Create prompt template request"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None


class PromptTemplateUpdateRequest(BaseModel):
    """Update prompt template request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class PromptVersionCreateRequest(BaseModel):
    """Create prompt version request"""
    version: str = Field(..., min_length=1, max_length=50)
    content: str = Field(..., min_length=1)
    model_hint: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PromptRenderRequest(BaseModel):
    """Render prompt request"""
    version: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)


class PromptTemplateResponse(BaseModel):
    """Prompt template response"""
    id: str
    organization_id: str
    name: str
    slug: str
    description: Optional[str]
    category: Optional[str]
    default_version_id: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class PromptVersionResponse(BaseModel):
    """Prompt version response"""
    id: str
    template_id: str
    version: str
    content: str
    variables: List[str]
    model_hint: Optional[str]
    metadata: Dict[str, Any]
    is_published: bool
    published_at: Optional[datetime]
    created_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class PromptUsageStatsResponse(BaseModel):
    """Prompt usage stats response"""
    id: str
    version_id: str
    date: str
    invocations: int
    avg_latency_ms: Optional[float]
    avg_tokens: Optional[int]
    success_rate: Optional[float]

    class Config:
        from_attributes = True


class PromptRenderResponse(BaseModel):
    """Rendered prompt response"""
    template_id: str
    version_id: str
    version: str
    content: str
    rendered_content: str
    variables: Dict[str, Any]
    model_hint: Optional[str]


# =============================================================================
# ROUTER
# =============================================================================


router = APIRouter(prefix="/api/prompts", tags=["Prompt Registry"])


# Utility function to get organization_id from auth
# For now, using a demo organization_id (original working pattern)
def get_organization_id() -> UUID:
    """Get organization ID from auth context."""
    # TODO: Extract from JWT token or session when auth is fully implemented
    return UUID("00000000-0000-0000-0000-000000000001")


def get_user_id() -> UUID:
    """Get user ID from auth context."""
    # TODO: Extract from JWT token or session when auth is fully implemented
    return UUID("00000000-0000-0000-0000-000000000002")


# =============================================================================
# TEMPLATE ENDPOINTS
# =============================================================================


@router.post("", response_model=PromptTemplateResponse, status_code=201)
async def create_template(
    request: PromptTemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new prompt template.

    Creates a new prompt template with automatic slug generation.
    """
    organization_id = get_organization_id()
    user_id = get_user_id()

    template = await PromptService.create_template(
        db=db,
        organization_id=organization_id,
        name=request.name,
        description=request.description,
        category=request.category,
        created_by=user_id,
    )

    return PromptTemplateResponse(
        id=str(template.id),
        organization_id=str(template.organization_id),
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=template.category,
        default_version_id=str(template.default_version_id) if template.default_version_id else None,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
        created_by=str(template.created_by) if template.created_by else None,
    )


@router.get("", response_model=List[PromptTemplateResponse])
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    List prompt templates.

    Returns paginated list of prompt templates with optional filtering.
    """
    organization_id = get_organization_id()

    templates, total_count = await PromptService.list_templates(
        db=db,
        organization_id=organization_id,
        category=category,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )

    return [
        PromptTemplateResponse(
            id=str(t.id),
            organization_id=str(t.organization_id),
            name=t.name,
            slug=t.slug,
            description=t.description,
            category=t.category,
            default_version_id=str(t.default_version_id) if t.default_version_id else None,
            is_active=t.is_active,
            created_at=t.created_at,
            updated_at=t.updated_at,
            created_by=str(t.created_by) if t.created_by else None,
        )
        for t in templates
    ]


@router.get("/{slug}", response_model=PromptTemplateResponse)
async def get_template(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get prompt template by slug.

    Returns template details including default version reference.
    """
    organization_id = get_organization_id()

    template = await PromptService.get_template(
        db=db,
        organization_id=organization_id,
        slug=slug,
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return PromptTemplateResponse(
        id=str(template.id),
        organization_id=str(template.organization_id),
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=template.category,
        default_version_id=str(template.default_version_id) if template.default_version_id else None,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
        created_by=str(template.created_by) if template.created_by else None,
    )


@router.put("/{slug}", response_model=PromptTemplateResponse)
async def update_template(
    slug: str,
    request: PromptTemplateUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update prompt template.

    Updates template metadata. Does not affect versions.
    """
    organization_id = get_organization_id()

    template = await PromptService.update_template(
        db=db,
        organization_id=organization_id,
        slug=slug,
        name=request.name,
        description=request.description,
        category=request.category,
        is_active=request.is_active,
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return PromptTemplateResponse(
        id=str(template.id),
        organization_id=str(template.organization_id),
        name=template.name,
        slug=template.slug,
        description=template.description,
        category=template.category,
        default_version_id=str(template.default_version_id) if template.default_version_id else None,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
        created_by=str(template.created_by) if template.created_by else None,
    )


# =============================================================================
# VERSION ENDPOINTS
# =============================================================================


@router.post("/{slug}/versions", response_model=PromptVersionResponse, status_code=201)
async def create_version(
    slug: str,
    request: PromptVersionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create new prompt version.

    Creates a new version for the specified template.
    Variables are automatically extracted from content.
    """
    from sqlalchemy.exc import IntegrityError

    organization_id = get_organization_id()
    user_id = get_user_id()

    try:
        version = await PromptService.create_version(
            db=db,
            organization_id=organization_id,
            slug=slug,
            version=request.version,
            content=request.content,
            model_hint=request.model_hint,
            metadata=request.metadata,
            created_by=user_id,
        )
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Version '{request.version}' already exists for this prompt"
        )

    if not version:
        raise HTTPException(status_code=404, detail="Template not found")

    return PromptVersionResponse(
        id=str(version.id),
        template_id=str(version.template_id),
        version=version.version,
        content=version.content,
        variables=version.variables,
        model_hint=version.model_hint,
        metadata=version.extra_metadata,
        is_published=version.is_published,
        published_at=version.published_at,
        created_at=version.created_at,
        created_by=str(version.created_by) if version.created_by else None,
    )


@router.get("/{slug}/versions", response_model=List[PromptVersionResponse])
async def list_versions(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List all versions for a template.

    Returns versions ordered by creation date (newest first).
    """
    organization_id = get_organization_id()

    versions = await PromptService.list_versions(
        db=db,
        organization_id=organization_id,
        slug=slug,
    )

    return [
        PromptVersionResponse(
            id=str(v.id),
            template_id=str(v.template_id),
            version=v.version,
            content=v.content,
            variables=v.variables,
            model_hint=v.model_hint,
            metadata=v.extra_metadata,
            is_published=v.is_published,
            published_at=v.published_at,
            created_at=v.created_at,
            created_by=str(v.created_by) if v.created_by else None,
        )
        for v in versions
    ]


@router.get("/{slug}/versions/{version}", response_model=PromptVersionResponse)
async def get_version(
    slug: str,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get specific version.

    Returns version details including content and variables.
    """
    organization_id = get_organization_id()

    prompt_version = await PromptService.get_version(
        db=db,
        organization_id=organization_id,
        slug=slug,
        version=version,
    )

    if not prompt_version:
        raise HTTPException(status_code=404, detail="Version not found")

    return PromptVersionResponse(
        id=str(prompt_version.id),
        template_id=str(prompt_version.template_id),
        version=prompt_version.version,
        content=prompt_version.content,
        variables=prompt_version.variables,
        model_hint=prompt_version.model_hint,
        metadata=prompt_version.extra_metadata,
        is_published=prompt_version.is_published,
        published_at=prompt_version.published_at,
        created_at=prompt_version.created_at,
        created_by=str(prompt_version.created_by) if prompt_version.created_by else None,
    )


@router.put("/{slug}/versions/{version}/publish", response_model=PromptVersionResponse)
async def publish_version(
    slug: str,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Publish a version.

    Marks version as published and sets it as the template's default version.
    """
    organization_id = get_organization_id()

    prompt_version = await PromptService.publish_version(
        db=db,
        organization_id=organization_id,
        slug=slug,
        version=version,
    )

    if not prompt_version:
        raise HTTPException(status_code=404, detail="Version not found")

    return PromptVersionResponse(
        id=str(prompt_version.id),
        template_id=str(prompt_version.template_id),
        version=prompt_version.version,
        content=prompt_version.content,
        variables=prompt_version.variables,
        model_hint=prompt_version.model_hint,
        metadata=prompt_version.extra_metadata,
        is_published=prompt_version.is_published,
        published_at=prompt_version.published_at,
        created_at=prompt_version.created_at,
        created_by=str(prompt_version.created_by) if prompt_version.created_by else None,
    )


# =============================================================================
# RENDERING ENDPOINT
# =============================================================================


@router.post("/{slug}/render", response_model=PromptRenderResponse)
async def render_prompt(
    slug: str,
    request: PromptRenderRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Render prompt with variable substitution.

    Substitutes variables in the prompt content and returns rendered result.
    If version is not specified, uses the template's default version.
    """
    organization_id = get_organization_id()

    try:
        result = await PromptService.render_prompt(
            db=db,
            organization_id=organization_id,
            slug=slug,
            version=request.version,
            variables=request.variables,
        )

        if not result:
            raise HTTPException(status_code=404, detail="Template or version not found")

        return PromptRenderResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# USAGE STATS ENDPOINTS
# =============================================================================


@router.get("/{slug}/versions/{version}/stats", response_model=List[PromptUsageStatsResponse])
async def get_usage_stats(
    slug: str,
    version: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get usage statistics for a version.

    Returns daily usage metrics for the specified version.
    """
    organization_id = get_organization_id()

    # Get version to get its ID
    prompt_version = await PromptService.get_version(
        db=db,
        organization_id=organization_id,
        slug=slug,
        version=version,
    )

    if not prompt_version:
        raise HTTPException(status_code=404, detail="Version not found")

    stats = await PromptService.get_usage_stats(
        db=db,
        version_id=prompt_version.id,
        days=days,
    )

    return [
        PromptUsageStatsResponse(
            id=str(s.id),
            version_id=str(s.version_id),
            date=s.date.isoformat(),
            invocations=s.invocations,
            avg_latency_ms=s.avg_latency_ms,
            avg_tokens=s.avg_tokens,
            success_rate=s.success_rate,
        )
        for s in stats
    ]

@router.delete("/{slug}", status_code=204)
async def delete_prompt_template(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a prompt template and all its versions.

    This will permanently delete the template and all associated:
    - Versions
    - Usage statistics

    Args:
        slug: Template slug

    Returns:
        204 No Content on success

    Raises:
        404: Template not found
    """
    organization_id = get_organization_id()

    try:
        await PromptService.delete_template(
            db=db,
            slug=slug,
            organization_id=organization_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return None

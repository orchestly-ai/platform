"""
Workflow Template API Endpoints - P1 Feature #2

REST API for workflow template marketplace.

Endpoints:
- GET    /api/v1/templates              - List/search templates
- POST   /api/v1/templates              - Create template
- GET    /api/v1/templates/{id}         - Get template details
- PUT    /api/v1/templates/{id}         - Update template
- DELETE /api/v1/templates/{id}         - Delete template
- GET    /api/v1/templates/slug/{slug}  - Get template by slug
- GET    /api/v1/templates/featured     - Get featured templates
- GET    /api/v1/templates/popular      - Get popular templates
- GET    /api/v1/templates/top-rated    - Get top-rated templates
- POST   /api/v1/templates/{id}/versions     - Create new version
- GET    /api/v1/templates/{id}/versions     - Get all versions
- POST   /api/v1/templates/{id}/rate         - Rate template
- POST   /api/v1/templates/{id}/favorite     - Toggle favorite
- POST   /api/v1/templates/import            - Import template
- GET    /api/v1/templates/{id}/export       - Export template
- GET    /api/v1/templates/categories        - Get all categories
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from backend.database.session import get_db
from backend.shared.template_models import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListItem,
    TemplateVersionCreate,
    TemplateVersionResponse,
    TemplateRatingCreate,
    TemplateRatingResponse,
    TemplateSearchFilters,
    TemplateImportRequest,
    TemplateCategory,
    TemplateVisibility,
    TemplateDifficulty,
)
from backend.shared.template_service import TemplateService
from backend.shared.auth import get_current_user_id, get_current_organization_id


router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


# Alias for backwards compatibility
async def get_organization_id() -> Optional[int]:
    """Get current user's organization ID as int."""
    return None


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Create new workflow template.

    Creates a template with initial version 1.0.0.
    """
    template = await TemplateService.create_template(
        db, template_data, user_id, organization_id
    )
    return template


@router.get("", response_model=dict)
async def list_templates(
    category: Optional[TemplateCategory] = None,
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    difficulty: Optional[TemplateDifficulty] = None,
    visibility: Optional[TemplateVisibility] = None,
    is_verified: Optional[bool] = None,
    is_featured: Optional[bool] = None,
    min_rating: Optional[float] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    List and search workflow templates.

    Supports filtering by category, tags, difficulty, rating, etc.
    Returns paginated results with total count.
    """
    # Parse tags
    tag_list = [tag.strip() for tag in tags.split(",")] if tags else None

    filters = TemplateSearchFilters(
        category=category,
        tags=tag_list,
        difficulty=difficulty,
        visibility=visibility,
        is_verified=is_verified,
        is_featured=is_featured,
        min_rating=min_rating,
        search_query=search,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )

    templates, total = await TemplateService.search_templates(db, filters, user_id)

    return {
        "templates": [TemplateListItem.model_validate(t) for t in templates],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/featured", response_model=List[TemplateListItem])
async def get_featured_templates(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get featured templates."""
    templates = await TemplateService.get_featured_templates(db, limit)
    return [TemplateListItem.model_validate(t) for t in templates]


@router.get("/popular", response_model=List[TemplateListItem])
async def get_popular_templates(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get most popular templates by usage count."""
    templates = await TemplateService.get_popular_templates(db, limit)
    return [TemplateListItem.model_validate(t) for t in templates]


@router.get("/top-rated", response_model=List[TemplateListItem])
async def get_top_rated_templates(
    limit: int = Query(10, le=50),
    min_ratings: int = Query(3, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Get top-rated templates."""
    templates = await TemplateService.get_top_rated_templates(db, limit, min_ratings)
    return [TemplateListItem.model_validate(t) for t in templates]


@router.get("/categories", response_model=List[dict])
async def get_categories():
    """Get all template categories."""
    return [
        {"value": cat.value, "label": cat.value.replace("_", " ").title()}
        for cat in TemplateCategory
    ]


@router.get("/slug/{slug}", response_model=TemplateResponse)
async def get_template_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get template by slug."""
    template = await TemplateService.get_template_by_slug(db, slug, user_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or not accessible",
        )

    return template


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get template details."""
    template = await TemplateService.get_template(db, template_id, user_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or not accessible",
        )

    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Update template."""
    template = await TemplateService.update_template(
        db, template_id, template_data, user_id
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or unauthorized",
        )

    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Delete template (soft delete)."""
    success = await TemplateService.delete_template(db, template_id, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or unauthorized",
        )

    return None


@router.post("/{template_id}/versions", response_model=TemplateVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_template_version(
    template_id: int,
    version_data: TemplateVersionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Create new template version."""
    version = await TemplateService.create_version(
        db, template_id, version_data, user_id
    )

    if not version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create version - template not found, unauthorized, or version already exists",
        )

    return version


@router.get("/{template_id}/versions", response_model=List[TemplateVersionResponse])
async def get_template_versions(
    template_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all versions for a template."""
    versions = await TemplateService.get_versions(db, template_id)
    return versions


@router.post("/{template_id}/rate", response_model=TemplateRatingResponse)
async def rate_template(
    template_id: int,
    rating_data: TemplateRatingCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Rate a template (1-5 stars)."""
    rating = await TemplateService.rate_template(
        db, template_id, rating_data, user_id
    )

    if not rating:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return rating


@router.post("/{template_id}/favorite", response_model=dict)
async def toggle_favorite(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Toggle favorite status for a template."""
    is_favorited = await TemplateService.toggle_favorite(db, template_id, user_id)

    return {"is_favorited": is_favorited}


@router.post("/import", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def import_template(
    import_data: TemplateImportRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Import template from JSON.

    Supports customizing parameters during import.
    """
    template = await TemplateService.import_template(
        db,
        import_data.template_data,
        user_id,
        organization_id,
        import_data.customize_parameters,
    )

    return template


@router.get("/{template_id}/export", response_model=dict)
async def export_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Export template as JSON."""
    export_data = await TemplateService.export_template(db, template_id, user_id)

    if not export_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or not accessible",
        )

    return export_data

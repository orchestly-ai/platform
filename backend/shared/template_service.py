"""
Workflow Template Service - P1 Feature #2

Business logic for workflow template management.
Handles template CRUD, versioning, search, import/export, and analytics.

Key Features:
- Template creation and management with automatic slug generation
- Version control with semantic versioning
- Smart search with full-text and filters
- Import/export templates as JSON
- Usage analytics and ratings
- Template verification and featuring
"""

import re
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy import select, func, or_, and_, desc, asc
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.shared.template_models import (
    WorkflowTemplate,
    TemplateVersion,
    TemplateRating,
    TemplateFavorite,
    TemplateUsageLog,
    TemplateCategory,
    TemplateVisibility,
    TemplateDifficulty,
    TemplateCreate,
    TemplateUpdate,
    TemplateVersionCreate,
    TemplateRatingCreate,
    TemplateSearchFilters,
)


class TemplateService:
    """Service for managing workflow templates."""

    @staticmethod
    def _generate_slug(name: str) -> str:
        """Generate URL-friendly slug from template name."""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        return slug

    @staticmethod
    async def create_template(
        db: AsyncSession,
        template_data: TemplateCreate,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> WorkflowTemplate:
        """
        Create new workflow template.

        Args:
            db: Database session
            template_data: Template creation data
            user_id: Creator user ID
            organization_id: Organization ID if applicable

        Returns:
            Created template
        """
        # Generate unique slug
        base_slug = TemplateService._generate_slug(template_data.name)
        slug = base_slug
        counter = 1

        while True:
            stmt = select(WorkflowTemplate).where(WorkflowTemplate.slug == slug)
            result = await db.execute(stmt)
            if not result.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Create template
        # Convert parameters dict (which may have Pydantic models as values) to JSON-serializable dict
        params_dict = {}
        if template_data.parameters:
            for key, value in template_data.parameters.items():
                if hasattr(value, 'dict'):
                    params_dict[key] = value.dict()
                elif hasattr(value, '__dict__'):
                    params_dict[key] = vars(value)
                else:
                    params_dict[key] = value

        template = WorkflowTemplate(
            name=template_data.name,
            slug=slug,
            description=template_data.description,
            category=template_data.category,
            tags=template_data.tags,
            difficulty=template_data.difficulty,
            visibility=template_data.visibility,
            created_by_user_id=user_id,
            organization_id=organization_id,
            workflow_definition=template_data.workflow_definition,
            parameters=params_dict,
            required_integrations=template_data.required_integrations,
            icon=template_data.icon,
            documentation=template_data.documentation,
            use_cases=template_data.use_cases,
        )

        db.add(template)
        await db.flush()

        # Create initial version
        version = TemplateVersion(
            template_id=template.id,
            version="1.0.0",
            version_number=1,
            workflow_definition=template_data.workflow_definition,
            parameters=template.parameters,
            required_integrations=template_data.required_integrations,
            changelog="Initial version",
            created_by_user_id=user_id,
        )

        db.add(version)
        await db.flush()

        # Update template with current version
        template.current_version_id = version.id
        await db.commit()
        await db.refresh(template)

        return template

    @staticmethod
    async def get_template(
        db: AsyncSession,
        template_id: int,
        user_id: Optional[str] = None,
    ) -> Optional[WorkflowTemplate]:
        """
        Get template by ID with visibility check.

        Args:
            db: Database session
            template_id: Template ID
            user_id: Requesting user ID for visibility check

        Returns:
            Template if found and accessible, None otherwise
        """
        stmt = select(WorkflowTemplate).where(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.is_active == True,
        )

        result = await db.execute(stmt)
        template = result.scalar_one_or_none()

        if not template:
            return None

        # Check visibility
        if template.visibility == TemplateVisibility.PUBLIC or template.visibility == TemplateVisibility.VERIFIED:
            # Log view
            if user_id:
                await TemplateService._log_usage(db, template.id, user_id, "viewed")
            template.view_count += 1
            await db.commit()
            return template
        elif template.visibility == TemplateVisibility.PRIVATE:
            if user_id and template.created_by_user_id == user_id:
                return template
        elif template.visibility == TemplateVisibility.ORGANIZATION:
            # Check if user is in same organization (simplified - would need user lookup)
            if user_id and template.created_by_user_id == user_id:
                return template

        return None

    @staticmethod
    async def get_template_by_slug(
        db: AsyncSession,
        slug: str,
        user_id: Optional[str] = None,
    ) -> Optional[WorkflowTemplate]:
        """Get template by slug."""
        stmt = select(WorkflowTemplate).where(
            WorkflowTemplate.slug == slug,
            WorkflowTemplate.is_active == True,
        )

        result = await db.execute(stmt)
        template = result.scalar_one_or_none()

        if not template:
            return None

        # Use same visibility logic
        return await TemplateService.get_template(db, template.id, user_id)

    @staticmethod
    async def update_template(
        db: AsyncSession,
        template_id: int,
        template_data: TemplateUpdate,
        user_id: str,
    ) -> Optional[WorkflowTemplate]:
        """Update existing template."""
        template = await TemplateService.get_template(db, template_id, user_id)

        if not template or template.created_by_user_id != user_id:
            return None

        # Update fields (explicit allowlist prevents mass-assignment)
        _ALLOWED_TEMPLATE_FIELDS = {
            "name", "description", "category", "tags", "content",
            "variables", "is_public", "status", "version",
        }
        update_data = template_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field in _ALLOWED_TEMPLATE_FIELDS:
                setattr(template, field, value)

        template.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(template)

        return template

    @staticmethod
    async def delete_template(
        db: AsyncSession,
        template_id: int,
        user_id: str,
    ) -> bool:
        """Soft delete template."""
        template = await TemplateService.get_template(db, template_id, user_id)

        if not template or template.created_by_user_id != user_id:
            return False

        template.is_active = False
        await db.commit()

        return True

    @staticmethod
    async def search_templates(
        db: AsyncSession,
        filters: TemplateSearchFilters,
        user_id: Optional[str] = None,
    ) -> Tuple[List[WorkflowTemplate], int]:
        """
        Search templates with filters.

        Returns:
            Tuple of (templates, total_count)
        """
        # Build query
        stmt = select(WorkflowTemplate).where(WorkflowTemplate.is_active == True)

        # Visibility filter
        visibility_conditions = [
            WorkflowTemplate.visibility == TemplateVisibility.PUBLIC,
            WorkflowTemplate.visibility == TemplateVisibility.VERIFIED,
        ]
        if user_id:
            visibility_conditions.append(WorkflowTemplate.created_by_user_id == user_id)

        stmt = stmt.where(or_(*visibility_conditions))

        # Category filter
        if filters.category:
            stmt = stmt.where(WorkflowTemplate.category == filters.category)

        # Tags filter (match any tag)
        if filters.tags:
            tag_conditions = [
                func.cast(WorkflowTemplate.tags, JSONB).op('@>')(func.cast([tag], JSONB))
                for tag in filters.tags
            ]
            stmt = stmt.where(or_(*tag_conditions))

        # Difficulty filter
        if filters.difficulty:
            stmt = stmt.where(WorkflowTemplate.difficulty == filters.difficulty)

        # Visibility filter (explicit)
        if filters.visibility:
            stmt = stmt.where(WorkflowTemplate.visibility == filters.visibility)

        # Verified filter
        if filters.is_verified is not None:
            stmt = stmt.where(WorkflowTemplate.is_verified == filters.is_verified)

        # Featured filter
        if filters.is_featured is not None:
            stmt = stmt.where(WorkflowTemplate.is_featured == filters.is_featured)

        # Rating filter
        if filters.min_rating is not None:
            stmt = stmt.where(WorkflowTemplate.average_rating >= filters.min_rating)

        # Search query (name or description)
        if filters.search_query:
            search_pattern = f"%{filters.search_query}%"
            stmt = stmt.where(
                or_(
                    WorkflowTemplate.name.ilike(search_pattern),
                    WorkflowTemplate.description.ilike(search_pattern),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Sorting
        if filters.sort_by == "created_at":
            order_col = WorkflowTemplate.created_at
        elif filters.sort_by == "usage_count":
            order_col = WorkflowTemplate.usage_count
        elif filters.sort_by == "average_rating":
            order_col = WorkflowTemplate.average_rating
        elif filters.sort_by == "favorite_count":
            order_col = WorkflowTemplate.favorite_count
        else:
            order_col = WorkflowTemplate.created_at

        if filters.sort_order == "desc":
            stmt = stmt.order_by(desc(order_col))
        else:
            stmt = stmt.order_by(asc(order_col))

        # Pagination
        stmt = stmt.limit(filters.limit).offset(filters.offset)

        # Execute
        result = await db.execute(stmt)
        templates = result.scalars().all()

        return list(templates), total

    @staticmethod
    async def create_version(
        db: AsyncSession,
        template_id: int,
        version_data: TemplateVersionCreate,
        user_id: str,
    ) -> Optional[TemplateVersion]:
        """Create new template version."""
        template = await TemplateService.get_template(db, template_id, user_id)

        if not template or template.created_by_user_id != user_id:
            return None

        # Check version doesn't already exist
        stmt = select(TemplateVersion).where(
            TemplateVersion.template_id == template_id,
            TemplateVersion.version == version_data.version,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            return None  # Version already exists

        # Get next version number
        stmt = select(func.max(TemplateVersion.version_number)).where(
            TemplateVersion.template_id == template_id
        )
        result = await db.execute(stmt)
        max_version = result.scalar() or 0

        # Serialize parameters (convert Pydantic models to dicts)
        params_dict = {}
        if version_data.parameters:
            for key, value in version_data.parameters.items():
                if hasattr(value, 'dict'):
                    params_dict[key] = value.dict()
                elif hasattr(value, '__dict__'):
                    params_dict[key] = vars(value)
                else:
                    params_dict[key] = value

        # Create version
        version = TemplateVersion(
            template_id=template_id,
            version=version_data.version,
            version_number=max_version + 1,
            workflow_definition=version_data.workflow_definition,
            parameters=params_dict,
            required_integrations=version_data.required_integrations,
            changelog=version_data.changelog,
            breaking_changes=version_data.breaking_changes,
            created_by_user_id=user_id,
        )

        db.add(version)
        await db.flush()

        # Update template
        template.current_version_id = version.id
        template.version_count += 1
        template.workflow_definition = version_data.workflow_definition
        template.parameters = version.parameters
        template.required_integrations = version_data.required_integrations
        template.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(version)

        return version

    @staticmethod
    async def get_versions(
        db: AsyncSession,
        template_id: int,
    ) -> List[TemplateVersion]:
        """Get all versions for a template."""
        stmt = select(TemplateVersion).where(
            TemplateVersion.template_id == template_id,
            TemplateVersion.is_active == True,
        ).order_by(desc(TemplateVersion.version_number))

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def rate_template(
        db: AsyncSession,
        template_id: int,
        rating_data: TemplateRatingCreate,
        user_id: str,
    ) -> Optional[TemplateRating]:
        """Rate a template."""
        template = await TemplateService.get_template(db, template_id, user_id)
        if not template:
            return None

        # Check if user already rated
        stmt = select(TemplateRating).where(
            TemplateRating.template_id == template_id,
            TemplateRating.user_id == user_id,
        )
        result = await db.execute(stmt)
        existing_rating = result.scalar_one_or_none()

        if existing_rating:
            # Update existing rating
            old_rating = existing_rating.rating
            existing_rating.rating = rating_data.rating
            existing_rating.review = rating_data.review
            existing_rating.updated_at = datetime.utcnow()
            rating = existing_rating
        else:
            # Create new rating
            rating = TemplateRating(
                template_id=template_id,
                user_id=user_id,
                rating=rating_data.rating,
                review=rating_data.review,
            )
            db.add(rating)
            old_rating = None

        await db.flush()

        # Recalculate average rating
        stmt = select(
            func.avg(TemplateRating.rating),
            func.count(TemplateRating.id)
        ).where(TemplateRating.template_id == template_id)

        result = await db.execute(stmt)
        avg_rating, rating_count = result.one()

        template.average_rating = float(avg_rating) if avg_rating else 0.0
        template.rating_count = rating_count or 0

        await db.commit()
        await db.refresh(rating)

        return rating

    @staticmethod
    async def toggle_favorite(
        db: AsyncSession,
        template_id: int,
        user_id: str,
    ) -> bool:
        """Toggle favorite status for a template."""
        template = await TemplateService.get_template(db, template_id, user_id)
        if not template:
            return False

        # Check if already favorited
        stmt = select(TemplateFavorite).where(
            TemplateFavorite.template_id == template_id,
            TemplateFavorite.user_id == user_id,
        )
        result = await db.execute(stmt)
        favorite = result.scalar_one_or_none()

        if favorite:
            # Remove favorite
            await db.delete(favorite)
            template.favorite_count = max(0, template.favorite_count - 1)
            is_favorited = False
        else:
            # Add favorite
            favorite = TemplateFavorite(
                template_id=template_id,
                user_id=user_id,
            )
            db.add(favorite)
            template.favorite_count += 1
            is_favorited = True

        await db.commit()
        return is_favorited

    @staticmethod
    async def import_template(
        db: AsyncSession,
        template_data: Dict[str, Any],
        user_id: str,
        organization_id: Optional[int] = None,
        customize_parameters: Optional[Dict[str, Any]] = None,
    ) -> WorkflowTemplate:
        """
        Import template from JSON data.

        Args:
            db: Database session
            template_data: Template JSON data
            user_id: Importing user ID
            organization_id: Organization ID
            customize_parameters: Custom parameter values

        Returns:
            Imported template
        """
        # Extract template data
        create_data = TemplateCreate(
            name=template_data.get("name", "Imported Template"),
            description=template_data.get("description", ""),
            category=TemplateCategory(template_data.get("category", "other")),
            tags=template_data.get("tags", []),
            difficulty=TemplateDifficulty(template_data.get("difficulty", "beginner")),
            visibility=TemplateVisibility.PRIVATE,  # Imported templates are private
            workflow_definition=template_data["workflow_definition"],
            parameters=template_data.get("parameters", {}),
            required_integrations=template_data.get("required_integrations", []),
            icon=template_data.get("icon"),
            documentation=template_data.get("documentation"),
            use_cases=template_data.get("use_cases", []),
        )

        # Apply customizations
        if customize_parameters:
            create_data.parameters.update(customize_parameters)

        # Create template
        template = await TemplateService.create_template(
            db, create_data, user_id, organization_id
        )

        # Log import
        await TemplateService._log_usage(db, template.id, user_id, "imported")

        return template

    @staticmethod
    async def export_template(
        db: AsyncSession,
        template_id: int,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Export template as JSON."""
        template = await TemplateService.get_template(db, template_id, user_id)
        if not template:
            return None

        # Build export data
        export_data = {
            "name": template.name,
            "description": template.description,
            "category": template.category if isinstance(template.category, str) else template.category.value,
            "tags": template.tags,
            "difficulty": template.difficulty if isinstance(template.difficulty, str) else template.difficulty.value,
            "workflow_definition": template.workflow_definition,
            "parameters": template.parameters,
            "required_integrations": template.required_integrations,
            "icon": template.icon,
            "documentation": template.documentation,
            "use_cases": template.use_cases,
            "version": "1.0.0",  # Default version for export
            "exported_at": datetime.utcnow().isoformat(),
        }

        return export_data

    @staticmethod
    async def _log_usage(
        db: AsyncSession,
        template_id: int,
        user_id: str,
        action: str,
        workflow_id: Optional[int] = None,
    ) -> None:
        """Log template usage."""
        usage_log = TemplateUsageLog(
            template_id=template_id,
            user_id=user_id,
            action=action,
            workflow_id=workflow_id,
        )
        db.add(usage_log)

        # Update usage count for certain actions
        if action in ["imported", "deployed"]:
            stmt = select(WorkflowTemplate).where(WorkflowTemplate.id == template_id)
            result = await db.execute(stmt)
            template = result.scalar_one_or_none()
            if template:
                template.usage_count += 1

        await db.commit()

    @staticmethod
    async def get_featured_templates(
        db: AsyncSession,
        limit: int = 10,
    ) -> List[WorkflowTemplate]:
        """Get featured templates."""
        stmt = select(WorkflowTemplate).where(
            WorkflowTemplate.is_active == True,
            WorkflowTemplate.is_featured == True,
            or_(
                WorkflowTemplate.visibility == TemplateVisibility.PUBLIC,
                WorkflowTemplate.visibility == TemplateVisibility.VERIFIED,
            )
        ).order_by(desc(WorkflowTemplate.usage_count)).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_popular_templates(
        db: AsyncSession,
        limit: int = 10,
    ) -> List[WorkflowTemplate]:
        """Get popular templates by usage count."""
        stmt = select(WorkflowTemplate).where(
            WorkflowTemplate.is_active == True,
            or_(
                WorkflowTemplate.visibility == TemplateVisibility.PUBLIC,
                WorkflowTemplate.visibility == TemplateVisibility.VERIFIED,
            )
        ).order_by(desc(WorkflowTemplate.usage_count)).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_top_rated_templates(
        db: AsyncSession,
        limit: int = 10,
        min_ratings: int = 3,
    ) -> List[WorkflowTemplate]:
        """Get top-rated templates."""
        stmt = select(WorkflowTemplate).where(
            WorkflowTemplate.is_active == True,
            WorkflowTemplate.rating_count >= min_ratings,
            or_(
                WorkflowTemplate.visibility == TemplateVisibility.PUBLIC,
                WorkflowTemplate.visibility == TemplateVisibility.VERIFIED,
            )
        ).order_by(desc(WorkflowTemplate.average_rating)).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

"""
Prompt Registry Service

Business logic for prompt template management with versioning.
Handles template CRUD, version control, rendering, and analytics.

Key Features:
- Template creation and management with slug-based identification
- Semantic versioning support (1.0.0, 1.0.1, 2.0.0, etc.)
- Variable substitution with {{variable}} syntax
- Prompt rendering with validation
- Usage analytics tracking
- Multi-model optimization hints
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from uuid import UUID, uuid4
from sqlalchemy import select, func, or_, and_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.shared.prompt_models import (
    PromptTemplateModel,
    PromptVersionModel,
    PromptUsageStatsModel,
)


class PromptService:
    """Service for managing prompt templates and versions."""

    @staticmethod
    def _generate_slug(name: str) -> str:
        """Generate URL-friendly slug from template name."""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        return slug

    @staticmethod
    def _extract_variables(content: str) -> List[str]:
        """
        Extract variable names from prompt content.

        Variables are marked with {{variable_name}} syntax.

        Args:
            content: Prompt content

        Returns:
            List of unique variable names
        """
        pattern = r'\{\{(\w+)\}\}'
        variables = re.findall(pattern, content)
        return list(set(variables))

    @staticmethod
    def _render_prompt(content: str, variables: Dict[str, Any]) -> str:
        """
        Render prompt by substituting variables.

        Args:
            content: Prompt content with {{variable}} placeholders
            variables: Dictionary of variable values

        Returns:
            Rendered prompt content

        Raises:
            ValueError: If required variables are missing
        """
        # Extract required variables
        required_vars = PromptService._extract_variables(content)

        # Check for missing variables
        missing_vars = [var for var in required_vars if var not in variables]
        if missing_vars:
            raise ValueError(f"Missing required variables: {', '.join(missing_vars)}")

        # Substitute variables
        rendered = content
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            rendered = rendered.replace(placeholder, str(var_value))

        return rendered

    @staticmethod
    async def create_template(
        db: AsyncSession,
        organization_id: UUID,
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        created_by: Optional[UUID] = None,
    ) -> PromptTemplateModel:
        """
        Create new prompt template.

        Args:
            db: Database session
            organization_id: Organization UUID
            name: Template name
            description: Template description
            category: Template category
            created_by: Creator user UUID

        Returns:
            Created template
        """
        # Generate unique slug
        base_slug = PromptService._generate_slug(name)
        slug = base_slug
        counter = 1

        while True:
            stmt = select(PromptTemplateModel).where(
                and_(
                    PromptTemplateModel.organization_id == organization_id,
                    PromptTemplateModel.slug == slug
                )
            )
            result = await db.execute(stmt)
            if not result.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Create template
        template = PromptTemplateModel(
            id=uuid4(),
            organization_id=organization_id,
            name=name,
            slug=slug,
            description=description,
            category=category,
            created_by=created_by,
        )

        db.add(template)
        await db.commit()
        await db.refresh(template)

        return template

    @staticmethod
    async def get_template(
        db: AsyncSession,
        organization_id: UUID,
        slug: str,
    ) -> Optional[PromptTemplateModel]:
        """
        Get template by organization and slug.

        Args:
            db: Database session
            organization_id: Organization UUID
            slug: Template slug

        Returns:
            Template if found, None otherwise
        """
        stmt = select(PromptTemplateModel).where(
            and_(
                PromptTemplateModel.organization_id == organization_id,
                PromptTemplateModel.slug == slug
            )
        ).options(selectinload(PromptTemplateModel.versions))

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_templates(
        db: AsyncSession,
        organization_id: UUID,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[PromptTemplateModel], int]:
        """
        List prompt templates with filtering.

        Args:
            db: Database session
            organization_id: Organization UUID
            category: Filter by category
            is_active: Filter by active status
            limit: Maximum number of results
            offset: Result offset

        Returns:
            Tuple of (templates, total_count)
        """
        # Build query
        conditions = [PromptTemplateModel.organization_id == organization_id]

        if category is not None:
            conditions.append(PromptTemplateModel.category == category)
        if is_active is not None:
            conditions.append(PromptTemplateModel.is_active == is_active)

        # Get total count
        count_stmt = select(func.count()).select_from(PromptTemplateModel).where(and_(*conditions))
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar()

        # Get templates
        stmt = (
            select(PromptTemplateModel)
            .where(and_(*conditions))
            .order_by(desc(PromptTemplateModel.updated_at))
            .limit(limit)
            .offset(offset)
            .options(selectinload(PromptTemplateModel.versions))
        )

        result = await db.execute(stmt)
        templates = result.scalars().all()

        return list(templates), total_count

    @staticmethod
    async def update_template(
        db: AsyncSession,
        organization_id: UUID,
        slug: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[PromptTemplateModel]:
        """
        Update prompt template.

        Args:
            db: Database session
            organization_id: Organization UUID
            slug: Template slug
            name: New template name
            description: New description
            category: New category
            is_active: New active status

        Returns:
            Updated template if found, None otherwise
        """
        template = await PromptService.get_template(db, organization_id, slug)
        if not template:
            return None

        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if category is not None:
            template.category = category
        if is_active is not None:
            template.is_active = is_active

        template.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(template)

        return template

    @staticmethod
    async def create_version(
        db: AsyncSession,
        organization_id: UUID,
        slug: str,
        version: str,
        content: str,
        model_hint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[UUID] = None,
    ) -> Optional[PromptVersionModel]:
        """
        Create new prompt version.

        Args:
            db: Database session
            organization_id: Organization UUID
            slug: Template slug
            version: Version string (e.g., "1.0.0")
            content: Prompt content
            model_hint: Suggested model
            metadata: Additional metadata
            created_by: Creator user UUID

        Returns:
            Created version if template found, None otherwise
        """
        template = await PromptService.get_template(db, organization_id, slug)
        if not template:
            return None

        # Extract variables from content
        variables = PromptService._extract_variables(content)

        # Create version
        prompt_version = PromptVersionModel(
            id=uuid4(),
            template_id=template.id,
            version=version,
            content=content,
            variables=variables,
            model_hint=model_hint,
            extra_metadata=metadata or {},
            created_by=created_by,
        )

        db.add(prompt_version)
        await db.commit()
        await db.refresh(prompt_version)

        return prompt_version

    @staticmethod
    async def get_version(
        db: AsyncSession,
        organization_id: UUID,
        slug: str,
        version: str,
    ) -> Optional[PromptVersionModel]:
        """
        Get specific prompt version.

        Args:
            db: Database session
            organization_id: Organization UUID
            slug: Template slug
            version: Version string

        Returns:
            Version if found, None otherwise
        """
        template = await PromptService.get_template(db, organization_id, slug)
        if not template:
            return None

        stmt = select(PromptVersionModel).where(
            and_(
                PromptVersionModel.template_id == template.id,
                PromptVersionModel.version == version
            )
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_versions(
        db: AsyncSession,
        organization_id: UUID,
        slug: str,
    ) -> List[PromptVersionModel]:
        """
        List all versions for a template.

        Args:
            db: Database session
            organization_id: Organization UUID
            slug: Template slug

        Returns:
            List of versions
        """
        template = await PromptService.get_template(db, organization_id, slug)
        if not template:
            return []

        stmt = (
            select(PromptVersionModel)
            .where(PromptVersionModel.template_id == template.id)
            .order_by(desc(PromptVersionModel.created_at))
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def publish_version(
        db: AsyncSession,
        organization_id: UUID,
        slug: str,
        version: str,
    ) -> Optional[PromptVersionModel]:
        """
        Publish a prompt version.

        Args:
            db: Database session
            organization_id: Organization UUID
            slug: Template slug
            version: Version string

        Returns:
            Published version if found, None otherwise
        """
        prompt_version = await PromptService.get_version(db, organization_id, slug, version)
        if not prompt_version:
            return None

        prompt_version.is_published = True
        prompt_version.published_at = datetime.utcnow()

        # Update template's default version
        template = await PromptService.get_template(db, organization_id, slug)
        if template:
            template.default_version_id = prompt_version.id
            template.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(prompt_version)

        return prompt_version

    @staticmethod
    async def render_prompt(
        db: AsyncSession,
        organization_id: UUID,
        slug: str,
        version: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Render prompt with variable substitution.

        Args:
            db: Database session
            organization_id: Organization UUID
            slug: Template slug
            version: Version string (uses default if not specified)
            variables: Variable values for substitution

        Returns:
            Rendered prompt data if found, None otherwise

        Raises:
            ValueError: If required variables are missing
        """
        template = await PromptService.get_template(db, organization_id, slug)
        if not template:
            return None

        # Get version
        if version:
            prompt_version = await PromptService.get_version(db, organization_id, slug, version)
        else:
            # Use default version
            if not template.default_version_id:
                return None
            stmt = select(PromptVersionModel).where(PromptVersionModel.id == template.default_version_id)
            result = await db.execute(stmt)
            prompt_version = result.scalar_one_or_none()

        if not prompt_version:
            return None

        # Render prompt
        rendered_content = PromptService._render_prompt(
            prompt_version.content,
            variables or {}
        )

        return {
            "template_id": str(template.id),
            "version_id": str(prompt_version.id),
            "version": prompt_version.version,
            "content": prompt_version.content,
            "rendered_content": rendered_content,
            "variables": variables or {},
            "model_hint": prompt_version.model_hint,
        }

    @staticmethod
    async def track_usage(
        db: AsyncSession,
        version_id: UUID,
        latency_ms: Optional[float] = None,
        tokens: Optional[int] = None,
        success: bool = True,
    ) -> None:
        """
        Track prompt usage statistics.

        Args:
            db: Database session
            version_id: Version UUID
            latency_ms: Request latency in milliseconds
            tokens: Token count
            success: Whether the request succeeded
        """
        today = date.today()

        # Get or create stats for today
        stmt = select(PromptUsageStatsModel).where(
            and_(
                PromptUsageStatsModel.version_id == version_id,
                PromptUsageStatsModel.date == today
            )
        )
        result = await db.execute(stmt)
        stats = result.scalar_one_or_none()

        if not stats:
            # Create new stats
            stats = PromptUsageStatsModel(
                id=uuid4(),
                version_id=version_id,
                date=today,
                invocations=1,
                avg_latency_ms=latency_ms,
                avg_tokens=tokens,
                success_rate=1.0 if success else 0.0,
            )
            db.add(stats)
        else:
            # Update existing stats
            stats.invocations += 1

            # Update running averages
            if latency_ms is not None:
                if stats.avg_latency_ms is None:
                    stats.avg_latency_ms = latency_ms
                else:
                    stats.avg_latency_ms = (
                        (stats.avg_latency_ms * (stats.invocations - 1) + latency_ms) / stats.invocations
                    )

            if tokens is not None:
                if stats.avg_tokens is None:
                    stats.avg_tokens = tokens
                else:
                    stats.avg_tokens = int(
                        (stats.avg_tokens * (stats.invocations - 1) + tokens) / stats.invocations
                    )

            if stats.success_rate is None:
                stats.success_rate = 1.0 if success else 0.0
            else:
                stats.success_rate = (
                    (stats.success_rate * (stats.invocations - 1) + (1.0 if success else 0.0)) / stats.invocations
                )

        await db.commit()

    @staticmethod
    async def get_usage_stats(
        db: AsyncSession,
        version_id: UUID,
        days: int = 30,
    ) -> List[PromptUsageStatsModel]:
        """
        Get usage statistics for a version.

        Args:
            db: Database session
            version_id: Version UUID
            days: Number of days to retrieve

        Returns:
            List of usage stats
        """
        stmt = (
            select(PromptUsageStatsModel)
            .where(PromptUsageStatsModel.version_id == version_id)
            .order_by(desc(PromptUsageStatsModel.date))
            .limit(days)
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def delete_template(
        db: AsyncSession,
        slug: str,
        organization_id: UUID,
    ) -> bool:
        """
        Delete a prompt template and all its versions.

        This will cascade delete all versions and usage stats associated with the template.

        Args:
            db: Database session
            slug: Template slug
            organization_id: Organization UUID

        Returns:
            True if deleted

        Raises:
            ValueError: If template not found
        """
        # Find template
        stmt = select(PromptTemplateModel).where(
            PromptTemplateModel.slug == slug,
            PromptTemplateModel.organization_id == organization_id,
        )
        result = await db.execute(stmt)
        template = result.scalar_one_or_none()

        if not template:
            raise ValueError(f"Template not found: {slug}")

        # Delete template (cascade will delete versions and stats)
        await db.delete(template)
        await db.commit()

        return True

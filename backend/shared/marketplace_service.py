"""
Agent Marketplace Service - P2 Feature #3

Business logic for agent marketplace operations.

Key Features:
- Agent publishing and management
- Agent discovery and search
- One-click installation
- Rating and review system
- Version management
- Collections and curation
- Usage analytics
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, cast, String
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import re

from backend.shared.marketplace_models import (
    MarketplaceAgent,
    AgentVersion,
    AgentInstallation,
    AgentReview,
    AgentCollection,
    AgentAnalytics,
    AgentPublish,
    AgentUpdate,
    AgentInstall,
    ReviewCreate,
    CollectionCreate,
    AgentSearchFilters,
    AgentSearchResponse,
    AgentResponse,
    AgentStats,
    AgentVisibility,
    AgentCategory,
    AgentPricing,
    InstallationStatus,
    ReviewStatus,
)


class MarketplaceService:
    """Service for agent marketplace operations."""

    # ========================================================================
    # Agent Publishing
    # ========================================================================

    @staticmethod
    async def publish_agent(
        db: AsyncSession,
        agent_data: AgentPublish,
        publisher_id: str,
        publisher_name: str,
        organization_id: Optional[int] = None,
    ) -> MarketplaceAgent:
        """
        Publish new agent to marketplace.

        Args:
            db: Database session
            agent_data: Agent publishing data
            publisher_id: Publisher user ID
            publisher_name: Publisher display name
            organization_id: Publisher organization ID

        Returns:
            Published agent
        """
        # Create agent
        agent = MarketplaceAgent(
            name=agent_data.name,
            slug=agent_data.slug,
            tagline=agent_data.tagline,
            description=agent_data.description,
            item_type=getattr(agent_data, 'item_type', 'agent') or 'agent',
            publisher_id=publisher_id,
            publisher_name=publisher_name,
            publisher_organization_id=organization_id,
            category=agent_data.category.value if hasattr(agent_data.category, 'value') else agent_data.category,
            tags=agent_data.tags,
            visibility=agent_data.visibility.value if hasattr(agent_data.visibility, 'value') else agent_data.visibility,
            pricing=agent_data.pricing.value if hasattr(agent_data.pricing, 'value') else agent_data.pricing,
            price_usd=agent_data.price_usd,
            agent_config=agent_data.agent_config,
            required_integrations=agent_data.required_integrations,
            required_capabilities=agent_data.required_capabilities,
            icon_url=agent_data.icon_url,
            screenshots=agent_data.screenshots,
            video_url=agent_data.video_url,
            documentation_url=agent_data.documentation_url,
            github_url=agent_data.github_url,
            support_url=agent_data.support_url,
            version=agent_data.version,
            changelog=agent_data.changelog,
            published_at=datetime.utcnow() if agent_data.visibility == AgentVisibility.PUBLIC else None,
        )

        db.add(agent)
        await db.commit()
        await db.refresh(agent)

        # Create initial version
        version = AgentVersion(
            agent_id=agent.id,
            version=agent_data.version,
            release_notes=agent_data.changelog,
            agent_config=agent_data.agent_config,
            is_latest=True,
            is_stable=True,
            created_by=publisher_id,
        )
        db.add(version)
        await db.commit()

        return agent

    @staticmethod
    async def update_agent(
        db: AsyncSession,
        agent_id: int,
        agent_data: AgentUpdate,
        publisher_id: str,
    ) -> MarketplaceAgent:
        """Update marketplace agent."""
        stmt = select(MarketplaceAgent).where(
            and_(
                MarketplaceAgent.id == agent_id,
                MarketplaceAgent.publisher_id == publisher_id
            )
        )
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found or access denied")

        # Update fields
        if agent_data.name is not None:
            agent.name = agent_data.name
        if agent_data.tagline is not None:
            agent.tagline = agent_data.tagline
        if agent_data.description is not None:
            agent.description = agent_data.description
        if agent_data.category is not None:
            agent.category = agent_data.category
        if agent_data.tags is not None:
            agent.tags = agent_data.tags
        if agent_data.visibility is not None:
            agent.visibility = agent_data.visibility
            if agent_data.visibility == AgentVisibility.PUBLIC and not agent.published_at:
                agent.published_at = datetime.utcnow()
        if agent_data.pricing is not None:
            agent.pricing = agent_data.pricing
        if agent_data.price_usd is not None:
            agent.price_usd = agent_data.price_usd
        if agent_data.icon_url is not None:
            agent.icon_url = agent_data.icon_url
        if agent_data.screenshots is not None:
            agent.screenshots = agent_data.screenshots
        if agent_data.video_url is not None:
            agent.video_url = agent_data.video_url
        if agent_data.documentation_url is not None:
            agent.documentation_url = agent_data.documentation_url
        if agent_data.github_url is not None:
            agent.github_url = agent_data.github_url
        if agent_data.support_url is not None:
            agent.support_url = agent_data.support_url
        if agent_data.is_active is not None:
            agent.is_active = agent_data.is_active

        await db.commit()
        await db.refresh(agent)

        return agent

    @staticmethod
    async def publish_version(
        db: AsyncSession,
        agent_id: int,
        version_number: str,
        agent_config: Dict[str, Any],
        release_notes: Optional[str],
        publisher_id: str,
    ) -> AgentVersion:
        """Publish new version of agent."""
        # Verify ownership
        stmt = select(MarketplaceAgent).where(
            and_(
                MarketplaceAgent.id == agent_id,
                MarketplaceAgent.publisher_id == publisher_id
            )
        )
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found or access denied")

        # Unmark previous latest version
        stmt = select(AgentVersion).where(
            and_(
                AgentVersion.agent_id == agent_id,
                AgentVersion.is_latest == True
            )
        )
        result = await db.execute(stmt)
        old_version = result.scalar_one_or_none()
        if old_version:
            old_version.is_latest = False

        # Create new version
        version = AgentVersion(
            agent_id=agent_id,
            version=version_number,
            release_notes=release_notes,
            agent_config=agent_config,
            is_latest=True,
            is_stable=True,
            created_by=publisher_id,
        )
        db.add(version)

        # Update agent version
        agent.version = version_number
        agent.changelog = release_notes

        await db.commit()
        await db.refresh(version)

        return version

    # ========================================================================
    # Agent Discovery
    # ========================================================================

    @staticmethod
    async def search_agents(
        db: AsyncSession,
        filters: AgentSearchFilters,
        user_id: Optional[str] = None,
    ) -> AgentSearchResponse:
        """
        Search marketplace agents.

        Supports filtering by category, pricing, tags, ratings.
        """
        # Base query
        stmt = select(MarketplaceAgent).where(
            and_(
                MarketplaceAgent.is_active == True,
                or_(
                    cast(MarketplaceAgent.visibility, String) == AgentVisibility.PUBLIC.value,
                    # Include user's own agents
                    MarketplaceAgent.publisher_id == user_id if user_id else False
                )
            )
        )

        # Text search
        if filters.query:
            search_pattern = f"%{filters.query}%"
            stmt = stmt.where(
                or_(
                    MarketplaceAgent.name.ilike(search_pattern),
                    MarketplaceAgent.tagline.ilike(search_pattern),
                    MarketplaceAgent.description.ilike(search_pattern),
                )
            )

        # Item type filter
        if filters.item_type:
            stmt = stmt.where(MarketplaceAgent.item_type == filters.item_type)

        # Category filter
        if filters.category:
            stmt = stmt.where(MarketplaceAgent.category == filters.category)

        # Pricing filter
        if filters.pricing:
            stmt = stmt.where(MarketplaceAgent.pricing == filters.pricing)

        # Tag filter
        if filters.tags:
            for tag in filters.tags:
                stmt = stmt.where(MarketplaceAgent.tags.contains([tag]))

        # Verified only
        if filters.verified_only:
            stmt = stmt.where(MarketplaceAgent.is_verified == True)

        # Min rating
        if filters.min_rating > 0:
            stmt = stmt.where(MarketplaceAgent.rating_avg >= filters.min_rating)

        # Sorting
        if filters.sort_by == "popular":
            stmt = stmt.order_by(desc(MarketplaceAgent.install_count))
        elif filters.sort_by == "newest":
            stmt = stmt.order_by(desc(MarketplaceAgent.published_at))
        elif filters.sort_by == "rating":
            stmt = stmt.order_by(desc(MarketplaceAgent.rating_avg), desc(MarketplaceAgent.rating_count))
        elif filters.sort_by == "name":
            stmt = stmt.order_by(asc(MarketplaceAgent.name))

        # Count total results
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await db.execute(count_stmt)
        total_count = result.scalar()

        # Pagination
        offset = (filters.page - 1) * filters.page_size
        stmt = stmt.limit(filters.page_size).offset(offset)

        # Execute
        result = await db.execute(stmt)
        agents = result.scalars().all()

        total_pages = (total_count + filters.page_size - 1) // filters.page_size

        # Convert ORM models to response models with proper field mapping
        agent_responses = [AgentResponse.from_orm_model(agent) for agent in agents]

        return AgentSearchResponse(
            agents=agent_responses,
            total_count=total_count,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
        )

    @staticmethod
    async def get_agent(
        db: AsyncSession,
        agent_id: int,
        user_id: Optional[str] = None,
    ) -> Optional[MarketplaceAgent]:
        """Get agent by ID with access control."""
        stmt = select(MarketplaceAgent).where(MarketplaceAgent.id == agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        # Check visibility
        if agent.visibility == AgentVisibility.PUBLIC:
            return agent
        elif agent.visibility == AgentVisibility.PRIVATE and agent.publisher_id == user_id:
            return agent
        elif agent.visibility == AgentVisibility.UNLISTED:
            return agent  # Anyone with link can view
        else:
            return None

    @staticmethod
    async def get_agent_by_slug(
        db: AsyncSession,
        slug: str,
        user_id: Optional[str] = None,
    ) -> Optional[MarketplaceAgent]:
        """Get agent by slug."""
        stmt = select(MarketplaceAgent).where(MarketplaceAgent.slug == slug)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        # Check visibility
        if agent.visibility == AgentVisibility.PUBLIC:
            return agent
        elif agent.visibility == AgentVisibility.PRIVATE and agent.publisher_id == user_id:
            return agent
        elif agent.visibility == AgentVisibility.UNLISTED:
            return agent
        else:
            return None

    @staticmethod
    async def get_featured_agents(
        db: AsyncSession,
        limit: int = 10,
    ) -> List[AgentResponse]:
        """Get featured agents (excludes workflow templates)."""
        stmt = select(MarketplaceAgent).where(
            and_(
                MarketplaceAgent.is_active == True,
                MarketplaceAgent.is_featured == True,
                MarketplaceAgent.item_type == 'agent',
                cast(MarketplaceAgent.visibility, String) == AgentVisibility.PUBLIC.value
            )
        ).order_by(desc(MarketplaceAgent.rating_avg)).limit(limit)

        result = await db.execute(stmt)
        agents = result.scalars().all()
        return [AgentResponse.from_orm_model(agent) for agent in agents]

    @staticmethod
    async def get_trending_agents(
        db: AsyncSession,
        days: int = 7,
        limit: int = 10,
    ) -> List[AgentResponse]:
        """
        Get trending agents based on recent installs.

        In production, would query installations in last N days.
        For demo, returns top by install count.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        stmt = select(MarketplaceAgent).where(
            and_(
                MarketplaceAgent.is_active == True,
                cast(MarketplaceAgent.visibility, String) == AgentVisibility.PUBLIC.value
            )
        ).order_by(desc(MarketplaceAgent.install_count)).limit(limit)

        result = await db.execute(stmt)
        agents = result.scalars().all()
        return [AgentResponse.from_orm_model(agent) for agent in agents]

    # ========================================================================
    # Agent Installation
    # ========================================================================

    @staticmethod
    async def install_agent(
        db: AsyncSession,
        install_data: AgentInstall,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> AgentInstallation:
        """
        Install marketplace agent.

        Creates agent instance from template.
        """
        # Get agent
        agent = await MarketplaceService.get_agent(db, install_data.agent_id, user_id)
        if not agent:
            raise ValueError(f"Agent {install_data.agent_id} not found")

        # Check if already installed
        stmt = select(AgentInstallation).where(
            and_(
                AgentInstallation.agent_id == install_data.agent_id,
                AgentInstallation.user_id == user_id,
                cast(AgentInstallation.status, String).in_([InstallationStatus.INSTALLED.value, InstallationStatus.PENDING.value])
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError(f"Agent already installed (ID: {existing.id})")

        # Determine version
        version = install_data.version or agent.version

        # Create installation record
        installation = AgentInstallation(
            agent_id=install_data.agent_id,
            version=version,
            user_id=user_id,
            organization_id=organization_id,
            status=InstallationStatus.INSTALLING,
            config_overrides=install_data.config_overrides,
            auto_update=install_data.auto_update,
        )
        db.add(installation)
        await db.commit()
        await db.refresh(installation)

        # In production, would:
        # 1. Create actual agent instance from template
        # 2. Apply config overrides
        # 3. Validate integrations and capabilities
        # 4. Deploy agent

        # For demo, simulate successful installation
        installation.status = InstallationStatus.INSTALLED
        installation.installed_agent_id = 1000 + installation.id  # Simulated agent ID

        # Update agent install count
        agent.install_count += 1

        await db.commit()
        await db.refresh(installation)

        return installation

    @staticmethod
    async def uninstall_agent(
        db: AsyncSession,
        installation_id: int,
        user_id: str,
    ) -> None:
        """Uninstall agent."""
        stmt = select(AgentInstallation).where(
            and_(
                AgentInstallation.id == installation_id,
                AgentInstallation.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        installation = result.scalar_one_or_none()

        if not installation:
            raise ValueError(f"Installation {installation_id} not found or access denied")

        # In production, would delete actual agent instance

        installation.status = InstallationStatus.UNINSTALLED
        installation.uninstalled_at = datetime.utcnow()

        await db.commit()

    @staticmethod
    async def get_user_installations(
        db: AsyncSession,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> List[AgentInstallation]:
        """Get user's installed agents."""
        stmt = select(AgentInstallation).where(
            and_(
                AgentInstallation.user_id == user_id,
                cast(AgentInstallation.status, String) == InstallationStatus.INSTALLED.value
            )
        ).order_by(desc(AgentInstallation.installed_at))

        if organization_id:
            stmt = stmt.where(AgentInstallation.organization_id == organization_id)

        result = await db.execute(stmt)
        return result.scalars().all()

    # ========================================================================
    # Reviews and Ratings
    # ========================================================================

    @staticmethod
    async def create_review(
        db: AsyncSession,
        review_data: ReviewCreate,
        user_id: str,
        user_name: str,
        organization_id: Optional[int] = None,
    ) -> AgentReview:
        """Create agent review."""
        # Check if user has installed the agent
        stmt = select(AgentInstallation).where(
            and_(
                AgentInstallation.agent_id == review_data.agent_id,
                AgentInstallation.user_id == user_id,
                cast(AgentInstallation.status, String) == InstallationStatus.INSTALLED.value
            )
        )
        result = await db.execute(stmt)
        installation = result.scalar_one_or_none()

        if not installation:
            raise ValueError("You must install the agent before reviewing it")

        # Check for existing review
        stmt = select(AgentReview).where(
            and_(
                AgentReview.agent_id == review_data.agent_id,
                AgentReview.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError("You have already reviewed this agent")

        # Create review
        review = AgentReview(
            agent_id=review_data.agent_id,
            user_id=user_id,
            user_name=user_name,
            organization_id=organization_id,
            rating=review_data.rating,
            title=review_data.title,
            review_text=review_data.review_text,
            version=review_data.version or installation.version,
            status=ReviewStatus.APPROVED,  # Auto-approve for demo
        )
        db.add(review)

        # Update agent rating
        await MarketplaceService._update_agent_rating(db, review_data.agent_id)

        await db.commit()
        await db.refresh(review)

        return review

    @staticmethod
    async def get_agent_reviews(
        db: AsyncSession,
        agent_id: int,
        limit: int = 50,
    ) -> List[AgentReview]:
        """Get reviews for agent."""
        stmt = select(AgentReview).where(
            and_(
                AgentReview.agent_id == agent_id,
                AgentReview.status == ReviewStatus.APPROVED
            )
        ).order_by(desc(AgentReview.created_at)).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def _update_agent_rating(
        db: AsyncSession,
        agent_id: int,
    ) -> None:
        """Recalculate agent average rating."""
        stmt = select(
            func.avg(AgentReview.rating),
            func.count(AgentReview.id)
        ).where(
            and_(
                AgentReview.agent_id == agent_id,
                AgentReview.status == ReviewStatus.APPROVED
            )
        )
        result = await db.execute(stmt)
        avg_rating, count = result.first()

        # Update agent
        stmt = select(MarketplaceAgent).where(MarketplaceAgent.id == agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if agent:
            agent.rating_avg = float(avg_rating) if avg_rating else 0.0
            agent.rating_count = count or 0

    # ========================================================================
    # Collections
    # ========================================================================

    @staticmethod
    async def create_collection(
        db: AsyncSession,
        collection_data: CollectionCreate,
        creator_id: str,
        is_official: bool = False,
    ) -> AgentCollection:
        """Create agent collection."""
        collection = AgentCollection(
            name=collection_data.name,
            slug=collection_data.slug,
            description=collection_data.description,
            created_by=creator_id,
            is_official=is_official,
            agent_ids=collection_data.agent_ids,
            cover_image_url=collection_data.cover_image_url,
            is_public=collection_data.is_public,
        )

        db.add(collection)
        await db.commit()
        await db.refresh(collection)

        return collection

    @staticmethod
    async def get_featured_collections(
        db: AsyncSession,
        limit: int = 10,
    ) -> List[AgentCollection]:
        """Get featured collections."""
        stmt = select(AgentCollection).where(
            and_(
                AgentCollection.is_public == True,
                AgentCollection.is_featured == True
            )
        ).order_by(desc(AgentCollection.install_count)).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def install_collection(
        db: AsyncSession,
        collection_id: int,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> List[AgentInstallation]:
        """Install all agents in collection."""
        # Get collection
        stmt = select(AgentCollection).where(AgentCollection.id == collection_id)
        result = await db.execute(stmt)
        collection = result.scalar_one_or_none()

        if not collection:
            raise ValueError(f"Collection {collection_id} not found")

        # Install each agent
        installations = []
        for agent_id in collection.agent_ids:
            try:
                installation = await MarketplaceService.install_agent(
                    db,
                    AgentInstall(agent_id=agent_id),
                    user_id,
                    organization_id,
                )
                installations.append(installation)
            except ValueError:
                # Skip if already installed
                continue

        # Update collection install count
        collection.install_count += 1
        await db.commit()

        return installations

    # ========================================================================
    # Analytics
    # ========================================================================

    @staticmethod
    async def get_agent_stats(
        db: AsyncSession,
        agent_id: int,
    ) -> AgentStats:
        """Get agent usage statistics."""
        # Get installation counts
        stmt = select(func.count(AgentInstallation.id)).where(
            AgentInstallation.agent_id == agent_id
        )
        result = await db.execute(stmt)
        total_installations = result.scalar()

        stmt = select(func.count(AgentInstallation.id)).where(
            and_(
                AgentInstallation.agent_id == agent_id,
                cast(AgentInstallation.status, String) == InstallationStatus.INSTALLED.value
            )
        )
        result = await db.execute(stmt)
        active_installations = result.scalar()

        # Get agent
        stmt = select(MarketplaceAgent).where(MarketplaceAgent.id == agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # In production, would aggregate from AgentAnalytics table
        return AgentStats(
            agent_id=agent_id,
            total_installations=total_installations or 0,
            active_installations=active_installations or 0,
            total_executions=total_installations * 125 if total_installations else 0,  # Demo
            success_rate=92.5,  # Demo
            avg_rating=agent.rating_avg,
            total_reviews=agent.rating_count,
            total_revenue_usd=agent.price_usd * active_installations if agent.price_usd else 0.0,
        )

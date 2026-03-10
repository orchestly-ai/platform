"""
Agent Marketplace API - P2 Feature #3

REST API for agent marketplace operations.

Endpoints:

Agent Publishing:
- POST   /api/v1/marketplace/agents                - Publish agent
- GET    /api/v1/marketplace/agents                - Search agents
- GET    /api/v1/marketplace/agents/{id}           - Get agent details
- GET    /api/v1/marketplace/agents/slug/{slug}    - Get agent by slug
- PUT    /api/v1/marketplace/agents/{id}           - Update agent
- DELETE /api/v1/marketplace/agents/{id}           - Delete agent (unpublish)
- POST   /api/v1/marketplace/agents/{id}/versions  - Publish new version
- GET    /api/v1/marketplace/agents/{id}/versions  - List versions

Discovery:
- GET    /api/v1/marketplace/featured              - Featured agents
- GET    /api/v1/marketplace/trending              - Trending agents
- GET    /api/v1/marketplace/categories            - List categories

Installation:
- POST   /api/v1/marketplace/install               - Install agent
- GET    /api/v1/marketplace/installations         - List user installations
- DELETE /api/v1/marketplace/installations/{id}    - Uninstall agent

Reviews:
- POST   /api/v1/marketplace/reviews               - Create review
- GET    /api/v1/marketplace/agents/{id}/reviews   - Get agent reviews

Collections:
- POST   /api/v1/marketplace/collections           - Create collection
- GET    /api/v1/marketplace/collections           - List collections
- GET    /api/v1/marketplace/collections/{id}      - Get collection
- POST   /api/v1/marketplace/collections/{id}/install - Install collection

Analytics:
- GET    /api/v1/marketplace/agents/{id}/stats     - Agent statistics
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from backend.database.session import get_db
from backend.shared.marketplace_models import (
    AgentPublish,
    AgentUpdate,
    AgentResponse,
    AgentDetailResponse,
    AgentInstall,
    InstallationResponse,
    ReviewCreate,
    ReviewResponse,
    CollectionCreate,
    CollectionResponse,
    AgentSearchFilters,
    AgentSearchResponse,
    AgentStats,
    AgentCategory,
    AgentPricing,
)
from backend.shared.marketplace_service import MarketplaceService
from backend.shared.auth import (
    get_current_user,
    get_current_user_id,
    get_current_organization_id,
    AuthenticatedUser,
)


router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


# ============================================================================
# Agent Publishing
# ============================================================================

@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def publish_agent(
    agent_data: AgentPublish,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Publish new agent to marketplace.

    Creates marketplace listing with initial version.
    """
    try:
        agent = await MarketplaceService.publish_agent(
            db, agent_data, user.user_id, user.email, user.organization_id
        )
        return AgentResponse.from_orm_model(agent)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/agents", response_model=AgentSearchResponse)
async def search_agents(
    query: Optional[str] = Query(None),
    category: Optional[AgentCategory] = Query(None),
    item_type: Optional[str] = Query(None, description="Filter by item type: 'agent' or 'workflow_template'"),
    pricing: Optional[AgentPricing] = Query(None),
    tags: List[str] = Query(default_factory=list),
    verified_only: bool = Query(False),
    min_rating: float = Query(0.0, ge=0.0, le=5.0),
    sort_by: str = Query("popular", pattern=r'^(popular|newest|rating|name)$'),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id),
):
    """
    Search marketplace agents and workflow templates.

    Supports filtering by:
    - Text query (name, tagline, description)
    - Category
    - Item type (agent, workflow_template)
    - Pricing model
    - Tags
    - Verified status
    - Minimum rating

    Sort options: popular, newest, rating, name
    """
    filters = AgentSearchFilters(
        query=query,
        category=category,
        item_type=item_type,
        pricing=pricing,
        tags=tags,
        verified_only=verified_only,
        min_rating=min_rating,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )

    results = await MarketplaceService.search_agents(db, filters, user_id)
    return results


@router.get("/agents/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id),
):
    """
    Get agent details.

    Returns full agent configuration, requirements, and metadata.
    """
    agent = await MarketplaceService.get_agent(db, agent_id, user_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or access denied",
        )
    return agent


@router.get("/agents/slug/{slug}", response_model=AgentDetailResponse)
async def get_agent_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id),
):
    """
    Get agent by slug.

    Allows accessing agents via human-readable URLs.
    """
    agent = await MarketplaceService.get_agent_by_slug(db, slug, user_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or access denied",
        )
    return agent


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Update agent listing.

    Only publisher can update.
    """
    try:
        agent = await MarketplaceService.update_agent(db, agent_id, agent_data, user_id)
        return agent
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Delete agent (unpublish from marketplace).

    Marks agent as inactive. Does not delete existing installations.
    """
    from backend.shared.marketplace_models import MarketplaceAgent
    from sqlalchemy import select, and_

    stmt = select(MarketplaceAgent).where(
        and_(
            MarketplaceAgent.id == agent_id,
            MarketplaceAgent.publisher_id == user_id
        )
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or access denied",
        )

    agent.is_active = False
    await db.commit()


@router.post("/agents/{agent_id}/versions", status_code=status.HTTP_201_CREATED)
async def publish_version(
    agent_id: int,
    version: str = Body(..., description="Version number (e.g., 1.1.0)", embed=True),
    release_notes: Optional[str] = Body(None, embed=True),
    agent_config: Dict[str, Any] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Publish new version of agent.

    Creates new version entry and updates agent to latest version.
    """
    try:
        new_version = await MarketplaceService.publish_version(
            db, agent_id, version, agent_config, release_notes, user_id
        )
        return {
            "id": new_version.id,
            "version": new_version.version,
            "is_latest": new_version.is_latest,
            "created_at": new_version.created_at,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/agents/{agent_id}/versions")
async def list_versions(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    List all versions of agent.

    Returns version history with release notes.
    """
    from backend.shared.marketplace_models import AgentVersion
    from sqlalchemy import select, desc

    stmt = select(AgentVersion).where(
        AgentVersion.agent_id == agent_id
    ).order_by(desc(AgentVersion.created_at))

    result = await db.execute(stmt)
    versions = result.scalars().all()

    return [
        {
            "id": v.id,
            "version": v.version,
            "release_notes": v.release_notes,
            "is_latest": v.is_latest,
            "is_stable": v.is_stable,
            "created_at": v.created_at,
        }
        for v in versions
    ]


# ============================================================================
# Discovery
# ============================================================================

@router.get("/featured", response_model=List[AgentResponse])
async def get_featured_agents(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get featured agents.

    Hand-picked agents featured by platform.
    """
    agents = await MarketplaceService.get_featured_agents(db, limit)
    return agents


@router.get("/trending", response_model=List[AgentResponse])
async def get_trending_agents(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get trending agents.

    Agents with most installs in recent period.
    """
    agents = await MarketplaceService.get_trending_agents(db, days, limit)
    return agents


@router.get("/categories")
async def list_categories():
    """
    List all agent categories.

    Returns available categories with counts.
    """
    return [
        {"value": cat.value, "label": cat.value.replace("_", " ").title()}
        for cat in AgentCategory
    ]


# ============================================================================
# Installation
# ============================================================================

@router.post("/install", response_model=InstallationResponse, status_code=status.HTTP_201_CREATED)
async def install_agent(
    install_data: AgentInstall,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: str = Depends(get_current_organization_id),
):
    """
    Install marketplace agent.

    Creates agent instance from template with optional config overrides.
    One-click installation.
    """
    try:
        installation = await MarketplaceService.install_agent(
            db, install_data, user_id, organization_id
        )
        return installation
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/installations", response_model=List[InstallationResponse])
async def list_installations(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: str = Depends(get_current_organization_id),
):
    """
    List user's installed agents.

    Returns all active installations.
    """
    installations = await MarketplaceService.get_user_installations(
        db, user_id, organization_id
    )
    return installations


@router.delete("/installations/{installation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_agent(
    installation_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Uninstall agent.

    Removes agent instance and marks installation as uninstalled.
    """
    try:
        await MarketplaceService.uninstall_agent(db, installation_id, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/installations/details")
async def list_installed_agents_with_details(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: str = Depends(get_current_organization_id),
):
    """
    List user's installed agents with full agent details.

    Returns installations joined with marketplace agent info for display
    in the Agents page. Includes agent name, config, category, etc.
    """
    from backend.shared.marketplace_models import (
        AgentInstallation, MarketplaceAgent, InstallationStatus
    )
    from sqlalchemy import select, and_

    # Get installations with agent details
    stmt = select(AgentInstallation, MarketplaceAgent).join(
        MarketplaceAgent,
        AgentInstallation.agent_id == MarketplaceAgent.id
    ).where(
        and_(
            AgentInstallation.user_id == user_id,
            AgentInstallation.status == InstallationStatus.INSTALLED
        )
    )

    if organization_id:
        stmt = stmt.where(AgentInstallation.organization_id == organization_id)

    result = await db.execute(stmt)
    rows = result.all()

    # Transform to response format
    installed_agents = []
    for installation, agent in rows:
        installed_agents.append({
            "installation_id": installation.id,
            "agent_id": agent.id,
            "name": agent.name,
            "slug": agent.slug,
            "tagline": agent.tagline,
            "description": agent.description,
            "category": agent.category if isinstance(agent.category, str) else agent.category,
            "author": agent.publisher_name,
            "version": installation.version,
            "agent_config": agent.agent_config,
            "status": installation.status.value if hasattr(installation.status, 'value') else installation.status,
            "installed_at": installation.installed_at.isoformat() if installation.installed_at else None,
            "last_used_at": installation.last_used_at.isoformat() if installation.last_used_at else None,
            "usage_count": installation.usage_count or 0,
            "config_overrides": installation.config_overrides or {},
        })

    return {"installed_agents": installed_agents, "total": len(installed_agents)}


# ============================================================================
# Reviews
# ============================================================================

@router.post("/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    review_data: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Create agent review.

    Must have installed the agent to review.
    One review per user per agent.
    """
    try:
        review = await MarketplaceService.create_review(
            db, review_data, user.user_id, user.email, user.organization_id
        )
        return review
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/agents/{agent_id}/reviews", response_model=List[ReviewResponse])
async def get_agent_reviews(
    agent_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Get reviews for agent.

    Returns approved reviews sorted by newest first.
    """
    reviews = await MarketplaceService.get_agent_reviews(db, agent_id, limit)
    return reviews


# ============================================================================
# Collections
# ============================================================================

@router.post("/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    collection_data: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Create agent collection.

    Curated collection of agents (e.g., "Sales Automation Pack").
    """
    collection = await MarketplaceService.create_collection(
        db, collection_data, user_id
    )
    return collection


@router.get("/collections", response_model=List[CollectionResponse])
async def list_collections(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List featured collections.

    Returns curated agent collections.
    """
    collections = await MarketplaceService.get_featured_collections(db, limit)
    return collections


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get collection details.

    Returns collection with agent list.
    """
    from backend.shared.marketplace_models import AgentCollection
    from sqlalchemy import select

    stmt = select(AgentCollection).where(AgentCollection.id == collection_id)
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    return collection


@router.post("/collections/{collection_id}/install", response_model=List[InstallationResponse])
async def install_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: str = Depends(get_current_organization_id),
):
    """
    Install all agents in collection.

    One-click installation of entire collection.
    """
    try:
        installations = await MarketplaceService.install_collection(
            db, collection_id, user_id, organization_id
        )
        return installations
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ============================================================================
# Workflow Templates
# ============================================================================

@router.post("/publish-workflow", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def publish_workflow_as_template(
    workflow_id: str = Body(..., embed=True),
    name: str = Body(..., embed=True),
    tagline: str = Body(..., embed=True),
    description: str = Body(..., embed=True),
    category: str = Body("engineering", embed=True),
    tags: List[str] = Body(default_factory=list, embed=True),
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Publish a workflow as a marketplace template.

    Fetches the workflow from DB, extracts nodes/edges,
    and creates a marketplace entry with item_type='workflow_template'.
    """
    from sqlalchemy import select, text
    import json
    import re

    # Fetch the workflow
    try:
        result = await db.execute(
            text("SELECT workflow_id, name, description, nodes, edges, trigger_type FROM workflows WHERE workflow_id = :wid"),
            {"wid": workflow_id}
        )
        workflow = result.fetchone()
    except Exception:
        workflow = None
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Parse nodes/edges
    nodes = json.loads(workflow.nodes) if isinstance(workflow.nodes, str) else (workflow.nodes or [])
    edges = json.loads(workflow.edges) if isinstance(workflow.edges, str) else (workflow.edges or [])

    # Generate slug
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    # Add random suffix to avoid collisions
    import secrets
    slug = f"{slug}-{secrets.token_hex(3)}"

    # Store workflow config in agent_config
    agent_config = {
        "nodes": nodes,
        "edges": edges,
        "trigger_type": workflow.trigger_type or "manual",
        "node_count": len(nodes),
        "source_workflow_id": workflow_id,
    }

    from backend.shared.marketplace_models import MarketplaceAgent
    agent = MarketplaceAgent(
        name=name,
        slug=slug,
        tagline=tagline,
        description=description,
        item_type="workflow_template",
        publisher_id=user.user_id,
        publisher_name=user.email,
        publisher_organization_id=user.organization_id,
        category=category,
        tags=tags,
        visibility="public",
        pricing="free",
        agent_config=agent_config,
        required_integrations=[],
        required_capabilities=[],
        version="1.0.0",
        is_verified=False,
        is_featured=False,
        is_active=True,
        published_at=None,
    )
    from datetime import datetime
    agent.published_at = datetime.utcnow()

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return AgentResponse.from_orm_model(agent)


@router.post("/use-template")
async def use_workflow_template(
    marketplace_agent_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Create a new workflow from a marketplace workflow template.

    Extracts nodes/edges from agent_config and creates a new workflow.
    Returns the new workflow_id so the frontend can navigate to the designer.
    """
    from sqlalchemy import select, text
    from backend.shared.marketplace_models import MarketplaceAgent
    import json
    import uuid

    # Get the marketplace entry
    stmt = select(MarketplaceAgent).where(MarketplaceAgent.id == marketplace_agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Marketplace item not found")

    if getattr(agent, 'item_type', 'agent') != 'workflow_template':
        raise HTTPException(status_code=400, detail="This marketplace item is not a workflow template")

    config = agent.agent_config or {}
    nodes = config.get("nodes", [])
    edges = config.get("edges", [])
    trigger_type = config.get("trigger_type", "manual")

    # Create a new workflow
    workflow_id = str(uuid.uuid4())
    from datetime import datetime
    now_dt = datetime.utcnow()

    await db.execute(text("""
        INSERT INTO workflows (
            workflow_id, organization_id, name, description, tags, status, version,
            nodes, edges, max_execution_time_seconds, retry_on_failure, max_retries,
            variables, environment, trigger_type, trigger_config,
            total_executions, successful_executions, failed_executions,
            avg_execution_time_seconds, average_execution_time, execution_count,
            total_cost, is_template, created_at, updated_at, created_by
        ) VALUES (
            :workflow_id, 'default', :name, :description, '[]', 'draft', 1,
            :nodes, :edges, 300, true, 3,
            '{}', 'production', :trigger_type, '{}',
            0, 0, 0,
            0, 0, 0,
            0.0, false, :now, :now, :created_by
        )
    """), {
        "workflow_id": workflow_id,
        "name": f"{agent.name} (from template)",
        "description": agent.description or "",
        "nodes": json.dumps(nodes),
        "edges": json.dumps(edges),
        "trigger_type": trigger_type,
        "now": now_dt,
        "created_by": user.email,
    })

    # Increment install count on the template
    agent.install_count = (agent.install_count or 0) + 1

    await db.commit()

    return {"workflow_id": workflow_id}


# ============================================================================
# Analytics
# ============================================================================

@router.get("/agents/{agent_id}/stats", response_model=AgentStats)
async def get_agent_stats(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get agent usage statistics.

    Returns:
    - Installation counts (total, active)
    - Execution metrics
    - Success rate
    - Revenue (for paid agents)
    """
    try:
        stats = await MarketplaceService.get_agent_stats(db, agent_id)
        return stats
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

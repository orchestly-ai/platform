"""
Agent Marketplace Models - P2 Feature #3

Data models for agent marketplace, publishing, discovery, and installation.

Enables:
- Pre-built agent templates
- Community agent sharing
- Agent discovery and search
- One-click agent installation
- Rating and reviews
- Version management
- Usage analytics
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, JSON, Float,
    ForeignKey, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


from backend.database.base import Base


# ============================================================================
# Enums
# ============================================================================

class AgentVisibility(str, Enum):
    """Agent visibility in marketplace."""
    PUBLIC = "public"  # Visible to everyone
    PRIVATE = "private"  # Only visible to creator
    ORGANIZATION = "organization"  # Visible within organization
    UNLISTED = "unlisted"  # Not in search, but accessible via link


class AgentCategory(str, Enum):
    """Agent categories for organization."""
    DATA_PROCESSING = "data_processing"
    CUSTOMER_SERVICE = "customer_service"
    SALES_AUTOMATION = "sales_automation"
    MARKETING = "marketing"
    HR_RECRUITING = "hr_recruiting"
    FINANCE_ACCOUNTING = "finance_accounting"
    LEGAL = "legal"
    ENGINEERING = "engineering"
    ANALYTICS = "analytics"
    INTEGRATION = "integration"
    COMMUNICATION = "communication"
    PRODUCTIVITY = "productivity"
    OTHER = "other"


class AgentPricing(str, Enum):
    """Agent pricing model."""
    FREE = "free"
    FREEMIUM = "freemium"  # Free with premium features
    PAID = "paid"
    ENTERPRISE = "enterprise"  # Contact sales


class InstallationStatus(str, Enum):
    """Agent installation status."""
    PENDING = "pending"
    INSTALLING = "installing"
    INSTALLED = "installed"
    FAILED = "failed"
    UNINSTALLED = "uninstalled"


class ReviewStatus(str, Enum):
    """Review moderation status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"


# ============================================================================
# Database Models
# ============================================================================

class MarketplaceAgent(Base):
    """
    Agent in marketplace.

    Pre-built agent templates that can be installed by users.
    """
    __tablename__ = "marketplace_agents"

    id = Column(Integer, primary_key=True, index=True)

    # Item type: 'agent' or 'workflow_template'
    item_type = Column(String(50), default='agent', nullable=False, index=True)

    # Basic info
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    tagline = Column(String(500), nullable=False)  # Short description
    description = Column(Text, nullable=False)  # Full description (markdown)

    # Publisher
    publisher_id = Column(String(255), nullable=False, index=True)
    publisher_name = Column(String(255), nullable=False)
    publisher_organization_id = Column(String(255), nullable=True, index=True)

    # Classification
    category = Column(String(50), nullable=False, index=True)
    tags = Column(JSON, default=list)  # Searchable tags

    # Visibility
    visibility = Column(String(50), default='PUBLIC', nullable=False, index=True)

    # Pricing
    pricing = Column(String(50), default='FREE', nullable=False, index=True)
    price_usd = Column(Float, nullable=True)  # Monthly price if paid

    # Agent configuration
    agent_config = Column(JSON, nullable=False)  # Full agent definition
    required_integrations = Column(JSON, default=list)  # Required integration IDs
    required_capabilities = Column(JSON, default=list)  # Required LLM capabilities

    # Media
    icon_url = Column(String(500), nullable=True)
    screenshots = Column(JSON, default=list)  # List of screenshot URLs
    video_url = Column(String(500), nullable=True)

    # Documentation
    documentation_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    support_url = Column(String(500), nullable=True)

    # Metadata
    version = Column(String(50), nullable=False, index=True)
    changelog = Column(Text, nullable=True)

    # Verification
    is_verified = Column(Boolean, default=False, nullable=False, index=True)  # Verified by platform
    is_featured = Column(Boolean, default=False, nullable=False, index=True)  # Featured in marketplace

    # Stats (updated periodically)
    install_count = Column(Integer, default=0, index=True)
    rating_avg = Column(Float, default=0.0, index=True)
    rating_count = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_deprecated = Column(Boolean, default=False, nullable=False)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime, nullable=True, index=True)

    # Relationships
    versions = relationship("AgentVersion", back_populates="agent", cascade="all, delete-orphan")
    installations = relationship("AgentInstallation", back_populates="agent", cascade="all, delete-orphan")
    reviews = relationship("AgentReview", back_populates="agent", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_marketplace_category_rating", "category", "rating_avg"),
        Index("ix_marketplace_featured", "is_featured", "rating_avg"),
        Index("ix_marketplace_installs", "install_count"),
        Index("ix_marketplace_search", "name", "category", "visibility"),
    )


class AgentVersion(Base):
    """
    Agent version history.

    Tracks all versions of a marketplace agent.
    """
    __tablename__ = "agent_versions"

    id = Column(Integer, primary_key=True, index=True)

    # Agent
    agent_id = Column(Integer, ForeignKey("marketplace_agents.id", ondelete="CASCADE"), nullable=False, index=True)

    # Version
    version = Column(String(50), nullable=False, index=True)
    release_notes = Column(Text, nullable=True)

    # Configuration
    agent_config = Column(JSON, nullable=False)

    # Compatibility
    min_platform_version = Column(String(50), nullable=True)
    breaking_changes = Column(Boolean, default=False, nullable=False)

    # Status
    is_latest = Column(Boolean, default=False, nullable=False, index=True)
    is_stable = Column(Boolean, default=True, nullable=False)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    created_by = Column(String(255), nullable=False)

    # Relationships
    agent = relationship("MarketplaceAgent", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_version"),
        Index("ix_version_agent_latest", "agent_id", "is_latest"),
    )


class AgentInstallation(Base):
    """
    Agent installation record.

    Tracks which users/orgs have installed which agents.
    """
    __tablename__ = "agent_installations"

    id = Column(Integer, primary_key=True, index=True)

    # Agent
    agent_id = Column(Integer, ForeignKey("marketplace_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(50), nullable=False)

    # Installer
    user_id = Column(String(255), nullable=False, index=True)
    organization_id = Column(String(255), nullable=True, index=True)

    # Installation - use native PostgreSQL enum type with lowercase values
    status = Column(
        SQLEnum(
            InstallationStatus,
            name='installationstatus',
            native_enum=True,
            create_type=False,
            values_callable=lambda x: [e.value for e in x]  # Use .value (lowercase) not .name (uppercase)
        ),
        default=InstallationStatus.PENDING,
        nullable=False,
        index=True
    )

    # Installed agent ID (reference to actual agent instance)
    installed_agent_id = Column(Integer, nullable=True, index=True)

    # Configuration overrides
    config_overrides = Column(JSON, default=dict)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Usage tracking
    last_used_at = Column(DateTime, nullable=True, index=True)
    usage_count = Column(Integer, default=0)

    # Auto-update
    auto_update = Column(Boolean, default=True, nullable=False)

    # Audit
    installed_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    uninstalled_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    agent = relationship("MarketplaceAgent", back_populates="installations")

    __table_args__ = (
        Index("ix_install_user_agent", "user_id", "agent_id"),
        Index("ix_install_org_agent", "organization_id", "agent_id"),
        Index("ix_install_status", "status"),
    )


class AgentReview(Base):
    """
    Agent review and rating.

    User reviews for marketplace agents.
    """
    __tablename__ = "agent_reviews"

    id = Column(Integer, primary_key=True, index=True)

    # Agent
    agent_id = Column(Integer, ForeignKey("marketplace_agents.id", ondelete="CASCADE"), nullable=False, index=True)

    # Reviewer
    user_id = Column(String(255), nullable=False, index=True)
    user_name = Column(String(255), nullable=False)
    organization_id = Column(Integer, nullable=True)

    # Review
    rating = Column(Integer, nullable=False, index=True)  # 1-5 stars
    title = Column(String(255), nullable=True)
    review_text = Column(Text, nullable=True)

    # Version reviewed
    version = Column(String(50), nullable=True)

    # Moderation
    status = Column(String(50), default='PENDING', nullable=False, index=True)
    moderation_notes = Column(Text, nullable=True)

    # Helpfulness
    helpful_count = Column(Integer, default=0)
    unhelpful_count = Column(Integer, default=0)

    # Response from publisher
    publisher_response = Column(Text, nullable=True)
    publisher_response_at = Column(DateTime, nullable=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    agent = relationship("MarketplaceAgent", back_populates="reviews")

    __table_args__ = (
        UniqueConstraint("agent_id", "user_id", name="uq_agent_user_review"),
        Index("ix_review_agent_rating", "agent_id", "rating"),
        Index("ix_review_status", "status"),
    )


class AgentCollection(Base):
    """
    Curated collection of agents.

    Featured collections like "Sales Automation Pack", "Customer Service Suite".
    """
    __tablename__ = "agent_collections"

    id = Column(Integer, primary_key=True, index=True)

    # Collection info
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)

    # Creator
    created_by = Column(String(255), nullable=False, index=True)
    is_official = Column(Boolean, default=False, nullable=False, index=True)

    # Agents in collection
    agent_ids = Column(JSON, default=list)  # List of agent IDs

    # Media
    cover_image_url = Column(String(500), nullable=True)

    # Visibility
    is_public = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False, index=True)

    # Stats
    install_count = Column(Integer, default=0)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_collection_featured", "is_featured", "install_count"),
    )


class AgentAnalytics(Base):
    """
    Agent usage analytics.

    Tracks agent performance and usage metrics.
    """
    __tablename__ = "agent_analytics"

    id = Column(Integer, primary_key=True, index=True)

    # Agent
    marketplace_agent_id = Column(Integer, ForeignKey("marketplace_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    installation_id = Column(Integer, ForeignKey("agent_installations.id", ondelete="CASCADE"), nullable=True, index=True)

    # Metrics
    date = Column(DateTime, nullable=False, index=True)
    executions = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    avg_duration_seconds = Column(Float, default=0.0)
    total_cost_usd = Column(Float, default=0.0)

    # User feedback
    positive_feedback = Column(Integer, default=0)
    negative_feedback = Column(Integer, default=0)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_analytics_agent_date", "marketplace_agent_id", "date"),
        Index("ix_analytics_install_date", "installation_id", "date"),
    )


# ============================================================================
# Pydantic Models (API Schemas)
# ============================================================================

class AgentPublish(BaseModel):
    """Publish new agent to marketplace."""
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern=r'^[a-z0-9-]+$')
    tagline: str = Field(..., max_length=500)
    description: str
    category: AgentCategory
    item_type: str = "agent"  # 'agent' or 'workflow_template'
    tags: List[str] = Field(default_factory=list)
    visibility: AgentVisibility = AgentVisibility.PUBLIC
    pricing: AgentPricing = AgentPricing.FREE
    price_usd: Optional[float] = None
    agent_config: Dict[str, Any]
    workflow_config: Optional[Dict[str, Any]] = None  # nodes/edges for workflow templates
    required_integrations: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    icon_url: Optional[str] = None
    screenshots: List[str] = Field(default_factory=list)
    video_url: Optional[str] = None
    documentation_url: Optional[str] = None
    github_url: Optional[str] = None
    support_url: Optional[str] = None
    version: str = "1.0.0"
    changelog: Optional[str] = None

    @validator('price_usd')
    def validate_price(cls, v, values):
        if values.get('pricing') == AgentPricing.PAID and v is None:
            raise ValueError('price_usd required for paid agents')
        return v


class AgentUpdate(BaseModel):
    """Update marketplace agent."""
    name: Optional[str] = Field(None, max_length=255)
    tagline: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    category: Optional[AgentCategory] = None
    tags: Optional[List[str]] = None
    visibility: Optional[AgentVisibility] = None
    pricing: Optional[AgentPricing] = None
    price_usd: Optional[float] = None
    icon_url: Optional[str] = None
    screenshots: Optional[List[str]] = None
    video_url: Optional[str] = None
    documentation_url: Optional[str] = None
    github_url: Optional[str] = None
    support_url: Optional[str] = None
    is_active: Optional[bool] = None


class AgentResponse(BaseModel):
    """Marketplace agent response - matches frontend expectations."""
    id: int
    name: str
    slug: str
    tagline: str
    description: str
    item_type: str = "agent"  # 'agent' or 'workflow_template'
    publisher_id: str
    author: str  # Mapped from publisher_name
    category: str  # Return as string
    tags: List[str]
    visibility: str  # Return as string
    pricing: str  # Return as string
    price_usd: Optional[float] = None
    icon_url: Optional[str] = None
    screenshots: List[str] = []
    version: str
    verified: bool  # Mapped from is_verified
    is_featured: bool
    install_count: int
    avg_rating: float  # Mapped from rating_avg
    rating_count: int
    agent_config: Optional[Dict[str, Any]] = None  # Included for workflow templates
    created_at: datetime
    published_at: Optional[datetime] = None

    @classmethod
    def from_orm_model(cls, obj) -> "AgentResponse":
        """Create from SQLAlchemy ORM model with field mapping."""
        item_type = getattr(obj, 'item_type', 'agent') or 'agent'
        return cls(
            id=obj.id,
            name=obj.name,
            slug=obj.slug,
            tagline=obj.tagline,
            description=obj.description,
            item_type=item_type,
            publisher_id=obj.publisher_id,
            author=obj.publisher_name,  # Map publisher_name -> author
            category=obj.category if isinstance(obj.category, str) else obj.category,
            tags=obj.tags or [],
            visibility=obj.visibility if isinstance(obj.visibility, str) else obj.visibility,
            pricing=obj.pricing if isinstance(obj.pricing, str) else obj.pricing,
            price_usd=obj.price_usd,
            icon_url=obj.icon_url,
            screenshots=obj.screenshots or [],
            version=obj.version,
            verified=obj.is_verified,  # Map is_verified -> verified
            is_featured=obj.is_featured,
            install_count=obj.install_count or 0,
            avg_rating=obj.rating_avg or 0.0,  # Map rating_avg -> avg_rating
            rating_count=obj.rating_count or 0,
            agent_config=obj.agent_config if item_type == 'workflow_template' else None,
            created_at=obj.created_at,
            published_at=obj.published_at,
        )


class AgentDetailResponse(AgentResponse):
    """Detailed agent response."""
    agent_config: Dict[str, Any]
    required_integrations: List[str]
    required_capabilities: List[str]
    video_url: Optional[str]
    documentation_url: Optional[str]
    github_url: Optional[str]
    support_url: Optional[str]
    changelog: Optional[str]
    is_deprecated: bool

    class Config:
        from_attributes = True


class AgentInstall(BaseModel):
    """Install agent."""
    agent_id: int
    version: Optional[str] = None  # Latest if not specified
    config_overrides: Dict[str, Any] = Field(default_factory=dict)
    auto_update: bool = True


class InstallationResponse(BaseModel):
    """Installation response."""
    id: int
    agent_id: int
    version: str
    status: InstallationStatus
    installed_agent_id: Optional[int]
    error_message: Optional[str]
    installed_at: datetime
    auto_update: bool

    class Config:
        from_attributes = True


class ReviewCreate(BaseModel):
    """Create review."""
    agent_id: int
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    review_text: Optional[str] = None
    version: Optional[str] = None


class ReviewResponse(BaseModel):
    """Review response."""
    id: int
    agent_id: int
    user_id: str
    user_name: str
    rating: int
    title: Optional[str]
    review_text: Optional[str]
    version: Optional[str]
    status: ReviewStatus
    helpful_count: int
    unhelpful_count: int
    publisher_response: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CollectionCreate(BaseModel):
    """Create agent collection."""
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern=r'^[a-z0-9-]+$')
    description: str
    agent_ids: List[int]
    cover_image_url: Optional[str] = None
    is_public: bool = True


class CollectionResponse(BaseModel):
    """Collection response."""
    id: int
    name: str
    slug: str
    description: str
    created_by: str
    is_official: bool
    agent_ids: List[int]
    cover_image_url: Optional[str]
    is_featured: bool
    install_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class AgentSearchFilters(BaseModel):
    """Search filters for marketplace."""
    query: Optional[str] = None
    category: Optional[AgentCategory] = None
    item_type: Optional[str] = None  # 'agent', 'workflow_template', or None for all
    pricing: Optional[AgentPricing] = None
    tags: List[str] = Field(default_factory=list)
    verified_only: bool = False
    min_rating: float = Field(0.0, ge=0.0, le=5.0)
    sort_by: str = Field("popular", pattern=r'^(popular|newest|rating|name)$')
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class AgentSearchResponse(BaseModel):
    """Search results."""
    agents: List[AgentResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class AgentStats(BaseModel):
    """Agent usage statistics."""
    agent_id: int
    total_installations: int
    active_installations: int
    total_executions: int
    success_rate: float
    avg_rating: float
    total_reviews: int
    total_revenue_usd: Optional[float]

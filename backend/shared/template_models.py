"""
Workflow Template Models - P1 Feature #2

Data models for the workflow template marketplace.
Supports template creation, versioning, categorization, and community sharing.

Key Features:
- Template catalog with categories and tags
- Version control for templates
- Usage analytics and ratings
- Import/export capabilities
- Community sharing and verification
- Template parameters and customization
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float, JSON,
    ForeignKey, Index, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from backend.database.base import Base


# Enums
class TemplateCategory(str, Enum):
    """Template categories for organization."""
    SALES = "sales"
    MARKETING = "marketing"
    CUSTOMER_SUPPORT = "customer_support"
    DEVOPS = "devops"
    DATA_PROCESSING = "data_processing"
    FINANCE = "finance"
    HR = "hr"
    LEGAL = "legal"
    OPERATIONS = "operations"
    ANALYTICS = "analytics"
    SECURITY = "security"
    AUTOMATION = "automation"
    INTEGRATION = "integration"
    OTHER = "other"


class TemplateVisibility(str, Enum):
    """Template visibility settings."""
    PRIVATE = "private"           # Only creator can see
    ORGANIZATION = "organization"  # Organization members can see
    PUBLIC = "public"              # Everyone can see
    VERIFIED = "verified"          # Public + verified by platform team


class TemplateDifficulty(str, Enum):
    """Template complexity level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


# Database Models
class WorkflowTemplate(Base):
    """
    Workflow template with versioning and metadata.

    Templates are reusable workflow definitions that can be imported
    and customized by users.
    """
    __tablename__ = "workflow_templates"

    id = Column(Integer, primary_key=True, index=True)

    # Identity
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=False)

    # Categorization
    category = Column(String(50), nullable=False, index=True)
    tags = Column(JSON, default=list)  # List of searchable tags
    difficulty = Column(String(50), default=TemplateDifficulty.BEGINNER)

    # Ownership
    created_by_user_id = Column(String(255), index=True)
    organization_id = Column(Integer, nullable=True, index=True)  # FK to organizations.id
    visibility = Column(String(50), default=TemplateVisibility.PRIVATE, index=True)

    # Template Definition
    workflow_definition = Column(JSON, nullable=False)  # DAG structure
    parameters = Column(JSON, default=dict)  # Customizable parameters
    required_integrations = Column(JSON, default=list)  # Required integration names

    # Metadata
    icon = Column(String(255), nullable=True)  # Emoji or URL
    cover_image_url = Column(String(500), nullable=True)
    documentation = Column(Text, nullable=True)  # Markdown documentation
    use_cases = Column(JSON, default=list)  # List of use case descriptions

    # Analytics
    usage_count = Column(Integer, default=0, index=True)
    view_count = Column(Integer, default=0)
    favorite_count = Column(Integer, default=0, index=True)
    average_rating = Column(Float, default=0.0, index=True)
    rating_count = Column(Integer, default=0)

    # Verification
    is_verified = Column(Boolean, default=False, index=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by_user_id = Column(String(255), nullable=True)

    # Version Control
    current_version_id = Column(Integer, ForeignKey("template_versions.id"), nullable=True)
    version_count = Column(Integer, default=1)

    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_featured = Column(Boolean, default=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True, index=True)

    # Relationships
    versions = relationship("TemplateVersion", back_populates="template", foreign_keys="TemplateVersion.template_id")
    ratings = relationship("TemplateRating", back_populates="template")
    favorites = relationship("TemplateFavorite", back_populates="template")
    usage_logs = relationship("TemplateUsageLog", back_populates="template")

    __table_args__ = (
        Index("ix_templates_category_visibility", "category", "visibility"),
        Index("ix_templates_featured_active", "is_featured", "is_active"),
        Index("ix_templates_verified_active", "is_verified", "is_active"),
        Index("ix_templates_created_at_desc", "created_at"),
        {'extend_existing': True}
    )


class TemplateVersion(Base):
    """
    Version history for workflow templates.

    Each template can have multiple versions, allowing users to
    roll back or upgrade templates.
    """
    __tablename__ = "template_versions"

    id = Column(Integer, primary_key=True, index=True)

    # Template reference
    template_id = Column(Integer, ForeignKey("workflow_templates.id"), nullable=False, index=True)

    # Version info
    version = Column(String(50), nullable=False)  # e.g., "1.0.0", "1.1.0"
    version_number = Column(Integer, nullable=False)  # Sequential number

    # Version content
    workflow_definition = Column(JSON, nullable=False)
    parameters = Column(JSON, default=dict)
    required_integrations = Column(JSON, default=list)

    # Change information
    changelog = Column(Text, nullable=True)
    breaking_changes = Column(Boolean, default=False)

    # Metadata
    created_by_user_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Relationships
    template = relationship("WorkflowTemplate", back_populates="versions", foreign_keys=[template_id])

    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_template_version"),
        Index("ix_template_versions_template_id_version", "template_id", "version_number"),
    )


class TemplateRating(Base):
    """
    User ratings for templates.
    """
    __tablename__ = "template_ratings"

    id = Column(Integer, primary_key=True, index=True)

    # References
    template_id = Column(Integer, ForeignKey("workflow_templates.id"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)

    # Rating
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    template = relationship("WorkflowTemplate", back_populates="ratings")

    __table_args__ = (
        UniqueConstraint("template_id", "user_id", name="uq_template_user_rating"),
        Index("ix_template_ratings_template_rating", "template_id", "rating"),
    )


class TemplateFavorite(Base):
    """
    User favorites for templates.
    """
    __tablename__ = "template_favorites"

    id = Column(Integer, primary_key=True, index=True)

    # References
    template_id = Column(Integer, ForeignKey("workflow_templates.id"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    template = relationship("WorkflowTemplate", back_populates="favorites")

    __table_args__ = (
        UniqueConstraint("template_id", "user_id", name="uq_template_user_favorite"),
    )


class TemplateUsageLog(Base):
    """
    Track template usage for analytics.
    """
    __tablename__ = "template_usage_logs"

    id = Column(Integer, primary_key=True, index=True)

    # References
    template_id = Column(Integer, ForeignKey("workflow_templates.id"), nullable=False, index=True)
    version_id = Column(Integer, ForeignKey("template_versions.id"), nullable=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    organization_id = Column(Integer, nullable=True, index=True)

    # Usage details
    action = Column(String(50), nullable=False)  # "viewed", "imported", "deployed", "forked"
    workflow_id = Column(Integer, nullable=True)  # Created workflow ID

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    template = relationship("WorkflowTemplate", back_populates="usage_logs")

    __table_args__ = (
        Index("ix_template_usage_template_action", "template_id", "action"),
    )


# Pydantic Models for API
class TemplateParameter(BaseModel):
    """Template parameter definition."""
    name: str
    type: str  # "string", "integer", "boolean", "select", etc.
    description: str
    default: Optional[Any] = None
    required: bool = True
    options: Optional[List[Any]] = None  # For select type


class TemplateCreate(BaseModel):
    """Create new template."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=10)
    category: TemplateCategory
    tags: List[str] = Field(default_factory=list)
    difficulty: TemplateDifficulty = TemplateDifficulty.BEGINNER
    visibility: TemplateVisibility = TemplateVisibility.PRIVATE
    workflow_definition: Dict[str, Any]
    parameters: Dict[str, TemplateParameter] = Field(default_factory=dict)
    required_integrations: List[str] = Field(default_factory=list)
    icon: Optional[str] = None
    documentation: Optional[str] = None
    use_cases: List[str] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    """Update existing template."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    category: Optional[TemplateCategory] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[TemplateDifficulty] = None
    visibility: Optional[TemplateVisibility] = None
    workflow_definition: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, TemplateParameter]] = None
    required_integrations: Optional[List[str]] = None
    icon: Optional[str] = None
    documentation: Optional[str] = None
    use_cases: Optional[List[str]] = None


class TemplateResponse(BaseModel):
    """Template response."""
    id: int
    name: str
    slug: str
    description: str
    category: TemplateCategory
    tags: List[str]
    difficulty: TemplateDifficulty
    visibility: TemplateVisibility
    created_by_user_id: str
    organization_id: Optional[int]
    workflow_definition: Dict[str, Any]
    parameters: Dict[str, Any]
    required_integrations: List[str]
    icon: Optional[str]
    cover_image_url: Optional[str]
    documentation: Optional[str]
    use_cases: List[str]
    usage_count: int
    view_count: int
    favorite_count: int
    average_rating: float
    rating_count: int
    is_verified: bool
    verified_at: Optional[datetime]
    current_version_id: Optional[int]
    version_count: int
    is_active: bool
    is_featured: bool
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]

    class Config:
        from_attributes = True


class TemplateListItem(BaseModel):
    """Template list item (summary)."""
    id: int
    name: str
    slug: str
    description: str
    category: TemplateCategory
    tags: List[str]
    difficulty: TemplateDifficulty
    icon: Optional[str]
    usage_count: int
    favorite_count: int
    average_rating: float
    rating_count: int
    is_verified: bool
    is_featured: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateVersionCreate(BaseModel):
    """Create new template version."""
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")  # Semantic versioning
    workflow_definition: Dict[str, Any]
    parameters: Dict[str, TemplateParameter] = Field(default_factory=dict)
    required_integrations: List[str] = Field(default_factory=list)
    changelog: Optional[str] = None
    breaking_changes: bool = False


class TemplateVersionResponse(BaseModel):
    """Template version response."""
    id: int
    template_id: int
    version: str
    version_number: int
    workflow_definition: Dict[str, Any]
    parameters: Dict[str, Any]
    required_integrations: List[str]
    changelog: Optional[str]
    breaking_changes: bool
    created_by_user_id: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class TemplateRatingCreate(BaseModel):
    """Create/update template rating."""
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None


class TemplateRatingResponse(BaseModel):
    """Template rating response."""
    id: int
    template_id: int
    user_id: str
    rating: int
    review: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateImportRequest(BaseModel):
    """Import template from JSON."""
    template_data: Dict[str, Any]
    customize_parameters: Optional[Dict[str, Any]] = None


class TemplateSearchFilters(BaseModel):
    """Search filters for templates."""
    category: Optional[TemplateCategory] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[TemplateDifficulty] = None
    visibility: Optional[TemplateVisibility] = None
    is_verified: Optional[bool] = None
    is_featured: Optional[bool] = None
    min_rating: Optional[float] = None
    search_query: Optional[str] = None
    sort_by: str = "created_at"  # created_at, usage_count, average_rating, favorite_count
    sort_order: str = "desc"
    limit: int = Field(default=20, le=100)
    offset: int = 0

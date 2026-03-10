"""
Prompt Registry - Models

Centralized prompt management with versioning:
- Prompt templates with semantic versioning
- Variable substitution support
- Usage tracking and analytics
- Multi-model optimization hints

Similar to Docker Hub for container images, but for AI prompts.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

import os
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer,
    ForeignKey, Index, Float, TypeDecorator, Date
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship

from backend.database.session import Base

# Database-agnostic UUID type that works with both PostgreSQL and SQLite
USE_SQLITE = os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes")


class UniversalUUID(TypeDecorator):
    """
    Platform-independent UUID type.
    Uses native UUID for PostgreSQL and String(36) for SQLite.
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            return str(value) if value else None

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            from uuid import UUID as PyUUID
            return PyUUID(value) if isinstance(value, str) else value


class UniversalJSON(TypeDecorator):
    """
    Platform-independent JSON type.
    Uses JSONB for PostgreSQL (supports indexing) and JSON for SQLite.
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        else:
            from sqlalchemy import JSON
            return dialect.type_descriptor(JSON())


class PromptCategory(str, Enum):
    """Prompt template categories"""
    CLASSIFICATION = "classification"
    GENERATION = "generation"
    EXTRACTION = "extraction"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    CONVERSATION = "conversation"
    CODE = "code"
    ANALYSIS = "analysis"
    OTHER = "other"


# =============================================================================
# DATABASE MODELS
# =============================================================================


class PromptTemplateModel(Base):
    """
    Prompt Template database model.

    Stores prompt metadata and references to versions.
    """
    __tablename__ = "prompt_templates"

    # Primary key
    id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Organization reference
    organization_id = Column(UniversalUUID(), nullable=False, index=True)

    # Template identification
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)

    # Default version
    default_version_id = Column(UniversalUUID(), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UniversalUUID(), nullable=True)

    # Relationships
    versions = relationship("PromptVersionModel", back_populates="template", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_prompt_template_org_slug', 'organization_id', 'slug', unique=True),
        Index('idx_prompt_template_category', 'category'),
        Index('idx_prompt_template_active', 'is_active'),
    )

    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, slug={self.slug})>"


class PromptVersionModel(Base):
    """
    Prompt Version database model.

    Stores prompt content with semantic versioning.
    """
    __tablename__ = "prompt_versions"

    # Primary key
    id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Template reference
    template_id = Column(UniversalUUID(), ForeignKey("prompt_templates.id"), nullable=False, index=True)

    # Version info
    version = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)

    # Variables (JSON array of variable names)
    variables = Column(UniversalJSON(), nullable=False, default=list)

    # Model hint
    model_hint = Column(String(100), nullable=True)

    # Metadata (renamed to extra_metadata to avoid conflict with SQLAlchemy's metadata)
    extra_metadata = Column(UniversalJSON(), nullable=True, default=dict)

    # Publishing status
    is_published = Column(Boolean, nullable=False, default=False, index=True)
    published_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(UniversalUUID(), nullable=True)

    # Relationships
    template = relationship("PromptTemplateModel", back_populates="versions")
    usage_stats = relationship("PromptUsageStatsModel", back_populates="version", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_prompt_version_template_version', 'template_id', 'version', unique=True),
        Index('idx_prompt_version_published', 'is_published'),
    )

    def __repr__(self):
        return f"<PromptVersion(id={self.id}, version={self.version})>"


class PromptUsageStatsModel(Base):
    """
    Prompt Usage Statistics database model.

    Tracks daily usage metrics for each prompt version.
    """
    __tablename__ = "prompt_usage_stats"

    # Primary key
    id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Version reference
    version_id = Column(UniversalUUID(), ForeignKey("prompt_versions.id"), nullable=False, index=True)

    # Date for aggregation
    date = Column(Date, nullable=False, index=True)

    # Usage metrics
    invocations = Column(Integer, nullable=False, default=0)
    avg_latency_ms = Column(Float, nullable=True)
    avg_tokens = Column(Integer, nullable=True)
    success_rate = Column(Float, nullable=True)

    # Relationships
    version = relationship("PromptVersionModel", back_populates="usage_stats")

    # Indexes
    __table_args__ = (
        Index('idx_prompt_usage_version_date', 'version_id', 'date', unique=True),
    )

    def __repr__(self):
        return f"<PromptUsageStats(version_id={self.version_id}, date={self.date})>"


# =============================================================================
# PYDANTIC MODELS (API Request/Response)
# =============================================================================


@dataclass
class PromptTemplate:
    """Prompt template data model"""
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    category: Optional[str] = None
    default_version_id: Optional[UUID] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[UUID] = None


@dataclass
class PromptVersion:
    """Prompt version data model"""
    id: UUID
    template_id: UUID
    version: str
    content: str
    variables: List[str] = field(default_factory=list)
    model_hint: Optional[str] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)
    is_published: bool = False
    published_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[UUID] = None


@dataclass
class PromptUsageStats:
    """Prompt usage statistics data model"""
    id: UUID
    version_id: UUID
    date: datetime
    invocations: int = 0
    avg_latency_ms: Optional[float] = None
    avg_tokens: Optional[int] = None
    success_rate: Optional[float] = None


@dataclass
class RenderedPrompt:
    """Rendered prompt with variables substituted"""
    template_id: UUID
    version_id: UUID
    version: str
    content: str
    rendered_content: str
    variables: Dict[str, Any]
    model_hint: Optional[str] = None

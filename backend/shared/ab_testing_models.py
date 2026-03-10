"""
A/B Testing Framework - P1 Feature #2

Data models for agent A/B testing and experimentation.

Enables:
- Running multiple agent versions in parallel
- Traffic splitting and random assignment
- Statistical significance testing
- Performance metrics comparison
- Automatic winner promotion
- Gradual rollout (canary deployments)
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, JSON,
    ForeignKey, Enum as SQLEnum, Index, CheckConstraint
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

class ExperimentStatus(str, Enum):
    """Status of A/B test experiment."""
    DRAFT = "draft"  # Being configured
    RUNNING = "running"  # Actively testing
    PAUSED = "paused"  # Temporarily stopped
    COMPLETED = "completed"  # Finished, results available
    CANCELLED = "cancelled"  # Stopped before completion


class VariantType(str, Enum):
    """Type of variant in experiment."""
    CONTROL = "control"  # Baseline version (A)
    TREATMENT = "treatment"  # New version being tested (B, C, etc.)


class TrafficSplitStrategy(str, Enum):
    """How to split traffic between variants."""
    RANDOM = "random"  # Random assignment
    WEIGHTED = "weighted"  # Weighted by traffic_percentage
    USER_HASH = "user_hash"  # Consistent per user
    ROUND_ROBIN = "round_robin"  # Rotate through variants


class MetricType(str, Enum):
    """Type of metric to track."""
    SUCCESS_RATE = "success_rate"  # % of successful executions
    LATENCY = "latency"  # Response time (ms)
    COST = "cost"  # $ per execution
    ERROR_RATE = "error_rate"  # % of errors
    USER_SATISFACTION = "user_satisfaction"  # Rating (1-5)
    CUSTOM = "custom"  # Custom metric


class WinnerSelectionCriteria(str, Enum):
    """Criteria for selecting winner."""
    HIGHEST_SUCCESS_RATE = "highest_success_rate"
    LOWEST_LATENCY = "lowest_latency"
    LOWEST_COST = "lowest_cost"
    HIGHEST_SATISFACTION = "highest_satisfaction"
    COMPOSITE_SCORE = "composite_score"  # Weighted combination


# ============================================================================
# Database Models
# ============================================================================

class ABExperiment(Base):
    """
    A/B test experiment definition.

    Represents a test comparing multiple agent variants.
    """
    __tablename__ = "ab_experiments"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Identification
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # What's being tested
    agent_id = Column(Integer, nullable=True, index=True)  # If testing specific agent
    workflow_id = Column(Integer, nullable=True, index=True)  # If testing workflow
    task_type = Column(String(100), nullable=True, index=True)  # General task category

    # Organization
    organization_id = Column(Integer, nullable=True, index=True)
    created_by_user_id = Column(String(255), nullable=False)

    # Traffic configuration
    traffic_split_strategy = Column(SQLEnum(TrafficSplitStrategy, name='trafficsplit', create_type=False, values_callable=lambda x: [e.value for e in x]), default=TrafficSplitStrategy.RANDOM, nullable=False, index=True)
    total_traffic_percentage = Column(Float, default=100.0)  # % of total traffic to include in experiment

    # Experiment parameters
    hypothesis = Column(Text, nullable=True)  # What we're testing
    success_criteria = Column(JSON, default=dict)  # What defines success
    minimum_sample_size = Column(Integer, default=100)  # Min samples per variant
    confidence_level = Column(Float, default=0.95)  # 95% confidence
    minimum_effect_size = Column(Float, default=0.05)  # 5% improvement needed

    # Winner selection
    winner_selection_criteria = Column(SQLEnum(WinnerSelectionCriteria, name='winnercriteria', create_type=False, values_callable=lambda x: [e.value for e in x]), default=WinnerSelectionCriteria.COMPOSITE_SCORE, nullable=False, index=True)
    winner_variant_id = Column(Integer, nullable=True, index=True)
    winner_confidence = Column(Float, nullable=True)  # Confidence in winner (0-1)

    # Status
    status = Column(SQLEnum(ExperimentStatus, name='experimentstatus', create_type=False, values_callable=lambda x: [e.value for e in x]), default=ExperimentStatus.DRAFT, nullable=False, index=True)

    # Timing
    started_at = Column(DateTime, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True)
    scheduled_end_date = Column(DateTime, nullable=True)

    # Results
    total_samples = Column(Integer, default=0)
    is_statistically_significant = Column(Boolean, default=False)
    p_value = Column(Float, nullable=True)  # Statistical significance

    # Auto-promotion
    auto_promote_winner = Column(Boolean, default=False)  # Automatically promote winner
    promoted_at = Column(DateTime, nullable=True)

    # Metadata
    tags = Column(JSON, default=list)
    extra_metadata = Column(JSON, default=dict)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    variants = relationship("ABVariant", back_populates="experiment", cascade="all, delete-orphan")
    assignments = relationship("ABAssignment", back_populates="experiment", cascade="all, delete-orphan")
    metrics = relationship("ABMetric", back_populates="experiment", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_ab_experiments_status_started", "status", "started_at"),
        Index("ix_ab_experiments_org_status", "organization_id", "status"),
        CheckConstraint("confidence_level >= 0.5 AND confidence_level <= 1.0", name="ck_confidence_level"),
        CheckConstraint("total_traffic_percentage > 0 AND total_traffic_percentage <= 100", name="ck_traffic_percentage"),
    )


class ABVariant(Base):
    """
    Variant in A/B test (version A, B, C, etc.).

    Each variant represents a different version being tested.
    """
    __tablename__ = "ab_variants"

    id = Column(Integer, primary_key=True, index=True)

    # Reference
    experiment_id = Column(Integer, ForeignKey("ab_experiments.id", ondelete="CASCADE"), nullable=False, index=True)

    # Identification
    name = Column(String(255), nullable=False)  # e.g., "Control", "Treatment A", "Treatment B"
    variant_key = Column(String(100), nullable=False)  # e.g., "control", "treatment_a"
    variant_type = Column(SQLEnum(VariantType, name='varianttype', create_type=False, values_callable=lambda x: [e.value for e in x]), default=VariantType.TREATMENT, nullable=False, index=True)

    # Configuration
    description = Column(Text, nullable=True)
    config = Column(JSON, default=dict)  # Variant-specific configuration
    traffic_percentage = Column(Float, nullable=False)  # % of traffic this variant receives

    # What's different in this variant
    agent_config_id = Column(Integer, nullable=True)  # Different agent configuration
    workflow_definition = Column(JSON, nullable=True)  # Different workflow
    prompt_template = Column(Text, nullable=True)  # Different prompt
    model_name = Column(String(255), nullable=True)  # Different LLM model

    # Performance tracking
    sample_count = Column(Integer, default=0)  # Number of samples
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    total_latency_ms = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)

    # Calculated metrics
    success_rate = Column(Float, default=0.0)  # % successful
    avg_latency_ms = Column(Float, default=0.0)  # Average latency
    avg_cost = Column(Float, default=0.0)  # Average cost per execution
    error_rate = Column(Float, default=0.0)  # % errors

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_winner = Column(Boolean, default=False)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    experiment = relationship("ABExperiment", back_populates="variants")
    assignments = relationship("ABAssignment", back_populates="variant", cascade="all, delete-orphan")
    metrics = relationship("ABMetric", back_populates="variant", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_ab_variants_experiment_active", "experiment_id", "is_active"),
        Index("ix_ab_variants_variant_key", "experiment_id", "variant_key", unique=True),
        CheckConstraint("traffic_percentage >= 0 AND traffic_percentage <= 100", name="ck_variant_traffic"),
    )


class ABAssignment(Base):
    """
    User/execution assignment to variant.

    Tracks which variant was assigned to each execution.
    """
    __tablename__ = "ab_assignments"

    id = Column(Integer, primary_key=True, index=True)

    # Reference
    experiment_id = Column(Integer, ForeignKey("ab_experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("ab_variants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Assignment target
    user_id = Column(String(255), nullable=True, index=True)  # User assigned to variant
    session_id = Column(String(255), nullable=True, index=True)  # Session assigned
    execution_id = Column(Integer, nullable=True, index=True)  # Workflow execution ID

    # Assignment metadata
    assignment_hash = Column(String(64), nullable=True)  # Hash for consistent assignment
    assignment_reason = Column(String(100), nullable=True)  # Why this variant was chosen

    # Outcome
    completed = Column(Boolean, default=False, nullable=False)
    success = Column(Boolean, nullable=True)
    latency_ms = Column(Float, nullable=True)
    cost = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)

    # Custom metrics
    custom_metrics = Column(JSON, default=dict)

    # Audit
    assigned_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    experiment = relationship("ABExperiment", back_populates="assignments")
    variant = relationship("ABVariant", back_populates="assignments")

    __table_args__ = (
        Index("ix_ab_assignments_experiment_variant", "experiment_id", "variant_id"),
        Index("ix_ab_assignments_user_experiment", "user_id", "experiment_id"),
        Index("ix_ab_assignments_completed", "completed", "assigned_at"),
    )


class ABMetric(Base):
    """
    Metrics collected during A/B test.

    Stores detailed metrics for analysis.
    """
    __tablename__ = "ab_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Reference
    experiment_id = Column(Integer, ForeignKey("ab_experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("ab_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("ab_assignments.id", ondelete="CASCADE"), nullable=True, index=True)

    # Metric details
    metric_type = Column(SQLEnum(MetricType, name='metrictype', create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    metric_name = Column(String(255), nullable=False)  # e.g., "task_completion_time"
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(50), nullable=True)  # e.g., "ms", "$", "%"

    # Context
    context = Column(JSON, default=dict)  # Additional context

    # Audit
    recorded_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationships
    experiment = relationship("ABExperiment", back_populates="metrics")
    variant = relationship("ABVariant", back_populates="metrics")

    __table_args__ = (
        Index("ix_ab_metrics_experiment_type", "experiment_id", "metric_type"),
        Index("ix_ab_metrics_variant_type", "variant_id", "metric_type"),
    )


# ============================================================================
# Pydantic Models (API Schemas)
# ============================================================================

class ABVariantCreate(BaseModel):
    """Create A/B test variant."""
    name: str = Field(..., max_length=255)
    variant_key: str = Field(..., max_length=100, pattern="^[a-z0-9_]+$")
    variant_type: VariantType = VariantType.TREATMENT
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    traffic_percentage: float = Field(..., ge=0, le=100)
    agent_config_id: Optional[int] = None
    workflow_definition: Optional[Dict[str, Any]] = None
    prompt_template: Optional[str] = None
    model_name: Optional[str] = None


class ABExperimentCreate(BaseModel):
    """Create A/B test experiment."""
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern="^[a-z0-9-]+$")
    description: Optional[str] = None
    agent_id: Optional[int] = None
    workflow_id: Optional[int] = None
    task_type: Optional[str] = None
    traffic_split_strategy: TrafficSplitStrategy = TrafficSplitStrategy.RANDOM
    total_traffic_percentage: float = Field(default=100.0, ge=0, le=100)
    hypothesis: Optional[str] = None
    success_criteria: Dict[str, Any] = Field(default_factory=dict)
    minimum_sample_size: int = Field(default=100, ge=10)
    confidence_level: float = Field(default=0.95, ge=0.5, le=1.0)
    minimum_effect_size: float = Field(default=0.05, ge=0.01, le=1.0)
    winner_selection_criteria: WinnerSelectionCriteria = WinnerSelectionCriteria.COMPOSITE_SCORE
    auto_promote_winner: bool = False
    scheduled_end_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    variants: List[ABVariantCreate] = Field(..., min_items=2, max_items=10)

    @validator("variants")
    def validate_traffic_split(cls, variants):
        total = sum(v.traffic_percentage for v in variants)
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Variant traffic percentages must sum to 100%, got {total}%")
        return variants


class ABVariantResponse(BaseModel):
    """A/B test variant with metrics."""
    id: int
    experiment_id: int
    name: str
    variant_key: str
    variant_type: str = "treatment"  # Use str to avoid enum issues
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    traffic_percentage: float = 0.0
    agent_config_id: Optional[int] = None
    workflow_definition: Optional[Dict[str, Any]] = None
    prompt_template: Optional[str] = None
    model_name: Optional[str] = None
    sample_count: int = 0
    success_count: int = 0
    error_count: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    avg_cost: float = 0.0
    error_rate: float = 0.0
    is_active: bool = True
    is_winner: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ABExperimentResponse(BaseModel):
    """A/B test experiment with results."""
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    agent_id: Optional[int] = None
    workflow_id: Optional[int] = None
    task_type: Optional[str] = None
    organization_id: Optional[int] = None
    created_by_user_id: str
    traffic_split_strategy: str = "random"  # Use str to avoid enum issues
    total_traffic_percentage: float = 100.0
    hypothesis: Optional[str] = None
    success_criteria: Dict[str, Any] = Field(default_factory=dict)
    minimum_sample_size: int = 100
    confidence_level: float = 0.95
    minimum_effect_size: float = 0.05
    winner_selection_criteria: str = "composite_score"  # Use str
    winner_variant_id: Optional[int] = None
    winner_confidence: Optional[float] = None
    status: str = "draft"  # Use str to avoid enum issues
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    scheduled_end_date: Optional[datetime] = None
    total_samples: int = 0
    is_statistically_significant: bool = False
    p_value: Optional[float] = None
    auto_promote_winner: bool = False
    promoted_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    variants: List[ABVariantResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ABAssignmentCreate(BaseModel):
    """Create variant assignment."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    execution_id: Optional[int] = None


class ABAssignmentResponse(BaseModel):
    """Variant assignment result."""
    id: int
    experiment_id: int
    variant_id: int
    variant_key: str
    variant_name: str
    user_id: Optional[str]
    session_id: Optional[str]
    execution_id: Optional[int]
    assigned_at: datetime


class ABMetricCreate(BaseModel):
    """Record experiment metric."""
    assignment_id: int
    metric_type: MetricType
    metric_name: str
    metric_value: float
    metric_unit: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class ABExperimentResults(BaseModel):
    """Experiment results and statistical analysis."""
    experiment_id: int
    experiment_name: str
    status: ExperimentStatus
    total_samples: int
    is_statistically_significant: bool
    p_value: Optional[float]
    confidence_level: float
    winner_variant_id: Optional[int]
    winner_confidence: Optional[float]
    variants: List[Dict[str, Any]]  # Variant results with stats
    recommendation: str  # Action to take
    insights: List[str]  # Key insights from test


class ABCompletionRequest(BaseModel):
    """Request to record experiment completion."""
    assignment_id: int
    success: bool
    latency_ms: Optional[float] = None
    cost: Optional[float] = None
    error_message: Optional[str] = None
    custom_metrics: Dict[str, float] = Field(default_factory=dict)


class ABFeedbackRequest(BaseModel):
    """
    Request to record user feedback on an A/B experiment execution.

    This is how you track whether users responded positively to the LLM output.
    The feedback updates the variant's conversion metrics.
    """
    assignment_id: int
    positive: bool  # True = thumbs up, False = thumbs down
    rating: Optional[int] = Field(None, ge=1, le=5)  # Optional 1-5 star rating
    comment: Optional[str] = None  # Optional feedback comment
    feedback_type: str = Field(default="user_rating", max_length=50)  # Type of feedback


class ABFeedbackResponse(BaseModel):
    """Response after recording feedback."""
    assignment_id: int
    experiment_id: int
    variant_id: int
    variant_name: str
    positive: bool
    recorded: bool
    message: str

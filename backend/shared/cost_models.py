"""
Cost Tracking and Forecasting Models

AI-powered cost prediction and budget management.
Addresses #2 production pain point: cost runaway ($10K+ surprise bills).
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Float, DateTime, JSON, ForeignKey,
    Index, Date, Integer, Boolean
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from backend.database.session import Base


class CostPeriod(Enum):
    """Time periods for cost tracking"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BudgetPeriod(Enum):
    """Budget period types"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class AlertSeverity(Enum):
    """Cost alert severity levels"""
    INFO = "info"           # 50% of budget
    WARNING = "warning"     # 75% of budget
    CRITICAL = "critical"   # 90% of budget
    EXCEEDED = "exceeded"   # 100%+ of budget


class CostCategory(Enum):
    """Categories of costs"""
    LLM_INFERENCE = "llm_inference"           # LLM API calls
    LLM_EMBEDDING = "llm_embedding"           # Embedding generation
    STORAGE = "storage"                       # Database storage
    COMPUTE = "compute"                       # Agent execution
    DATA_TRANSFER = "data_transfer"           # Network egress
    EXTERNAL_API = "external_api"             # Third-party APIs
    OTHER = "other"


class CostEventModel(Base):
    """
    Individual cost event (real-time tracking).

    High-volume table optimized for time-series queries.
    Will be converted to TimescaleDB hypertable.
    """
    __tablename__ = "cost_events"

    # Primary key
    event_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Time (partition key for TimescaleDB)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Organization/user attribution
    organization_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)

    # Resource attribution
    agent_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    task_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    workflow_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)

    # Cost details
    category = Column(String(50), nullable=False, index=True)
    amount = Column(Float, nullable=False)  # USD
    currency = Column(String(3), nullable=False, default="USD")

    # Provider details (for LLM costs)
    provider = Column(String(50), nullable=True)  # openai, anthropic, deepseek
    model = Column(String(100), nullable=True)    # gpt-4, claude-3, etc.

    # Usage metrics
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Additional metadata
    extra_metadata = Column("metadata", JSON, nullable=True)  # Maps to DB column 'metadata'

    # Indexes
    __table_args__ = (
        Index('idx_cost_timestamp', 'timestamp'),
        Index('idx_cost_org_time', 'organization_id', 'timestamp'),
        Index('idx_cost_agent_time', 'agent_id', 'timestamp'),
        Index('idx_cost_category_time', 'category', 'timestamp'),
        Index('idx_cost_provider', 'provider', 'timestamp'),
    )

    def __repr__(self):
        return f"<CostEvent(id={self.event_id}, amount=${self.amount}, category={self.category})>"


class CostAggregateModel(Base):
    """
    Pre-aggregated cost data for fast queries.

    Populated by periodic rollup jobs.
    """
    __tablename__ = "cost_aggregates"

    # Composite primary key
    aggregate_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Time period
    period = Column(String(20), nullable=False, index=True)  # hourly, daily, weekly, monthly
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)

    # Attribution
    organization_id = Column(String(255), nullable=False, index=True)
    agent_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    category = Column(String(50), nullable=True, index=True)

    # Aggregated metrics
    total_cost = Column(Float, nullable=False)
    event_count = Column(Integer, nullable=False)
    avg_cost_per_event = Column(Float, nullable=False)

    # Token usage (if applicable)
    total_input_tokens = Column(Integer, nullable=True)
    total_output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Provider breakdown (JSON)
    provider_breakdown = Column(JSON, nullable=True)  # {provider: cost}
    model_breakdown = Column(JSON, nullable=True)      # {model: cost}

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_agg_period_start', 'period', 'period_start'),
        Index('idx_agg_org_period', 'organization_id', 'period', 'period_start'),
        Index('idx_agg_agent_period', 'agent_id', 'period_start'),
    )

    def __repr__(self):
        return f"<CostAggregate(period={self.period}, cost=${self.total_cost})>"


class BudgetModel(Base):
    """
    Budget limits and alerts.
    """
    __tablename__ = "budgets"

    # Primary key
    budget_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Budget details
    name = Column(String(255), nullable=False)
    period = Column(String(20), nullable=False)  # daily, weekly, monthly, quarterly, yearly
    amount = Column(Float, nullable=False)  # USD
    currency = Column(String(3), nullable=False, default="USD")

    # Scope (what does this budget apply to?)
    scope_type = Column(String(50), nullable=True)  # agent, category, organization
    scope_id = Column(String(255), nullable=True)

    # Alert thresholds (percentages)
    alert_threshold_info = Column(Float, nullable=False, default=50.0)      # 50%
    alert_threshold_warning = Column(Float, nullable=False, default=75.0)   # 75%
    alert_threshold_critical = Column(Float, nullable=False, default=90.0)  # 90%

    # Actions
    auto_disable_on_exceeded = Column(Boolean, nullable=False, default=False)  # Auto-disable agents

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(255), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_budget_org', 'organization_id'),
        Index('idx_budget_active', 'is_active'),
        Index('idx_budget_scope', 'scope_type', 'scope_id'),
    )

    def __repr__(self):
        return f"<Budget(id={self.budget_id}, name={self.name}, amount=${self.amount})>"


class CostForecastModel(Base):
    """
    AI-generated cost forecasts.
    """
    __tablename__ = "cost_forecasts"

    # Primary key
    forecast_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Forecast details
    forecast_date = Column(Date, nullable=False, index=True)  # Date this forecast was generated
    forecast_period_start = Column(Date, nullable=False)
    forecast_period_end = Column(Date, nullable=False)

    # Predictions
    predicted_cost = Column(Float, nullable=False)
    confidence_lower = Column(Float, nullable=False)  # Lower bound (95% CI)
    confidence_upper = Column(Float, nullable=False)  # Upper bound (95% CI)
    confidence_interval = Column(Float, nullable=False, default=95.0)  # 95%

    # Scope
    scope_type = Column(String(50), nullable=True)  # agent, category, organization
    scope_id = Column(String(255), nullable=True)

    # Model details
    model_type = Column(String(50), nullable=False)  # prophet, arima, linear
    model_version = Column(String(50), nullable=False)
    training_data_points = Column(Integer, nullable=False)

    # Anomalies detected
    anomalies_detected = Column(JSON, nullable=True)  # List of anomaly timestamps

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_forecast_org_date', 'organization_id', 'forecast_date'),
        Index('idx_forecast_period', 'forecast_period_start', 'forecast_period_end'),
    )

    def __repr__(self):
        return f"<CostForecast(id={self.forecast_id}, predicted=${self.predicted_cost})>"


# Dataclasses for application logic

@dataclass
class CostEvent:
    """Cost event data structure"""
    timestamp: datetime
    organization_id: str
    category: CostCategory
    amount: float

    user_id: Optional[str] = None
    agent_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    workflow_id: Optional[UUID] = None

    provider: Optional[str] = None
    model: Optional[str] = None

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    metadata: Optional[Dict[str, Any]] = None
    currency: str = "USD"
    event_id: UUID = field(default_factory=uuid4)


@dataclass
class CostSummary:
    """Summary of costs for a period"""
    period_start: datetime
    period_end: datetime
    total_cost: float
    event_count: int
    avg_cost_per_event: float

    # Breakdown by category
    category_breakdown: Dict[str, float]

    # Breakdown by provider
    provider_breakdown: Dict[str, float]

    # Breakdown by model (gpt-4, claude-3, etc.)
    model_breakdown: Dict[str, float] = field(default_factory=dict)

    # Top expensive items
    top_agents: List[tuple[str, float]] = field(default_factory=list)
    top_workflows: List[tuple[str, float]] = field(default_factory=list)
    top_users: List[tuple[str, float]] = field(default_factory=list)

    # Trend
    vs_previous_period_percent: Optional[float] = None


@dataclass
class ForecastAnomaly:
    """Anomaly detected during forecast analysis"""
    timestamp: datetime
    expected_cost: float
    actual_cost: float
    deviation_percent: float
    severity: str  # low, medium, high


@dataclass
class CostForecast:
    """Cost forecast data structure"""
    forecast_period_start: date
    forecast_period_end: date
    predicted_cost: float
    confidence_lower: float
    confidence_upper: float
    confidence_interval: float = 95.0

    # Trend indicators
    trend: str = "stable"  # increasing, decreasing, stable
    anomalies_detected: List[ForecastAnomaly] = field(default_factory=list)

    # Model info
    model_type: str = "prophet"
    accuracy_score: Optional[float] = None


@dataclass
class BudgetStatus:
    """Current budget status"""
    budget_id: UUID
    budget_name: str
    period: BudgetPeriod
    limit: float
    spent: float
    remaining: float
    percent_used: float

    # Alerts
    alert_level: Optional[AlertSeverity] = None
    days_until_period_end: Optional[int] = None
    projected_spend: Optional[float] = None
    projected_overage: Optional[float] = None

    # Recommendations
    recommended_actions: List[str] = field(default_factory=list)


@dataclass
class CostAnomaly:
    """Detected cost anomaly"""
    timestamp: datetime
    expected_cost: float
    actual_cost: float
    deviation_percent: float
    severity: str  # low, medium, high

    # Attribution
    category: Optional[str] = None
    agent_id: Optional[UUID] = None

    # Context
    description: str = ""
    potential_causes: List[str] = field(default_factory=list)


@dataclass
class Budget:
    """Budget definition"""
    organization_id: str
    name: str
    period: BudgetPeriod
    amount: float
    budget_id: UUID = field(default_factory=uuid4)
    currency: str = "USD"

    # Scope filters (what does this budget apply to?)
    scope_type: Optional[str] = None  # agent, category, organization
    scope_id: Optional[str] = None

    # Alert thresholds (percent)
    alert_threshold_info: float = 50.0
    alert_threshold_warning: float = 75.0
    alert_threshold_critical: float = 90.0
    auto_disable_on_exceeded: bool = False

    # Status
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class BudgetAlert:
    """Budget alert notification"""
    alert_id: UUID
    budget_id: UUID
    severity: AlertSeverity
    message: str

    # Current state
    percent_used: float
    amount_spent: float
    amount_limit: float

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None

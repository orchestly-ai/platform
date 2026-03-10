"""
Advanced Analytics & BI Dashboard Models - P2 Feature #1

Data models for analytics dashboards, widgets, metrics, and reports.

Enables:
- Custom drag-and-drop dashboards
- Pre-built BI reports
- Agent performance analytics
- Cost analytics and attribution
- Usage trends and patterns
- ROI calculator
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, JSON, Float,
    ForeignKey, Enum as SQLEnum, Index, Numeric
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum


from backend.database.base import Base


# ============================================================================
# Enums
# ============================================================================

class DashboardType(str, Enum):
    """Dashboard types."""
    CUSTOM = "custom"  # User-created
    TEMPLATE = "template"  # Pre-built template
    SYSTEM = "system"  # System-generated


class WidgetType(str, Enum):
    """Widget visualization types."""
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    AREA_CHART = "area_chart"
    SCATTER_PLOT = "scatter_plot"
    HEATMAP = "heatmap"
    TABLE = "table"
    METRIC_CARD = "metric_card"  # Single number with trend
    GAUGE = "gauge"
    FUNNEL = "funnel"


class MetricType(str, Enum):
    """Metric categories."""
    # Performance
    WORKFLOW_SUCCESS_RATE = "workflow_success_rate"
    WORKFLOW_DURATION = "workflow_duration"
    TASK_COMPLETION_TIME = "task_completion_time"
    AGENT_RESPONSE_TIME = "agent_response_time"

    # Cost
    TOTAL_COST = "total_cost"
    COST_PER_WORKFLOW = "cost_per_workflow"
    COST_PER_AGENT = "cost_per_agent"
    LLM_COST_BY_PROVIDER = "llm_cost_by_provider"

    # Usage
    WORKFLOW_EXECUTIONS = "workflow_executions"
    ACTIVE_USERS = "active_users"
    API_REQUESTS = "api_requests"
    AGENT_INVOCATIONS = "agent_invocations"

    # Quality
    ERROR_RATE = "error_rate"
    RETRY_RATE = "retry_rate"
    APPROVAL_TIME = "approval_time"
    AB_TEST_PERFORMANCE = "ab_test_performance"

    # Business
    ROI = "roi"
    TIME_SAVED = "time_saved"
    AUTOMATION_RATE = "automation_rate"


class AggregationType(str, Enum):
    """Data aggregation types."""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    PERCENTILE_50 = "p50"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"


class TimeGranularity(str, Enum):
    """Time series granularity."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class ReportFormat(str, Enum):
    """Report output formats."""
    PDF = "pdf"
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"


class ReportSchedule(str, Enum):
    """Report scheduling frequency."""
    NONE = "none"  # On-demand only
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# ============================================================================
# Database Models
# ============================================================================

class Dashboard(Base):
    """
    Analytics dashboard.

    Contains widgets and layout configuration.
    """
    __tablename__ = "dashboards"

    id = Column(Integer, primary_key=True, index=True)

    # Dashboard metadata
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    dashboard_type = Column(String(50), default='custom', nullable=False, index=True)

    # Owner
    created_by = Column(String(255), nullable=False, index=True)
    organization_id = Column(Integer, nullable=True, index=True)

    # Layout configuration
    layout = Column(JSON, default=dict)  # Grid layout positions

    # Settings
    is_public = Column(Boolean, default=False, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    # Sharing (JSONB for PostgreSQL @> operator support)
    shared_with_users = Column(JSONB, default=list)  # List of user_ids
    shared_with_teams = Column(JSONB, default=list)  # List of team_ids

    # Metadata
    extra_metadata = Column(JSON, default=dict)
    tags = Column(JSON, default=list)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_viewed_at = Column(DateTime, nullable=True)
    view_count = Column(Integer, default=0)

    # Relationships
    widgets = relationship("DashboardWidget", back_populates="dashboard", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_dashboard_owner", "created_by", "organization_id"),
        Index("ix_dashboard_type_public", "dashboard_type", "is_public"),
    )


class DashboardWidget(Base):
    """
    Widget on a dashboard.

    Displays a specific metric or visualization.
    """
    __tablename__ = "dashboard_widgets"

    id = Column(Integer, primary_key=True, index=True)

    # Dashboard
    dashboard_id = Column(Integer, ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True)

    # Widget metadata
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    widget_type = Column(String(50), nullable=False, index=True)

    # Position & size
    position_x = Column(Integer, default=0)
    position_y = Column(Integer, default=0)
    width = Column(Integer, default=4)  # Grid columns
    height = Column(Integer, default=3)  # Grid rows

    # Data source
    metric_type = Column(String(50), nullable=False, index=True)
    aggregation_type = Column(String(50), default='avg')
    time_granularity = Column(String(50), default='day')

    # Filters
    filters = Column(JSON, default=dict)  # Where clauses
    time_range_days = Column(Integer, default=30)  # Last N days

    # Display configuration
    config = Column(JSON, default=dict)  # Chart options, colors, etc.

    # Data cache
    cached_data = Column(JSON, default=dict)
    cache_updated_at = Column(DateTime, nullable=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    dashboard = relationship("Dashboard", back_populates="widgets")

    __table_args__ = (
        Index("ix_widget_dashboard_type", "dashboard_id", "widget_type"),
        Index("ix_widget_metric", "metric_type"),
    )


class MetricSnapshot(Base):
    """
    Pre-calculated metric snapshot.

    Stores aggregated metrics for fast dashboard loading.
    """
    __tablename__ = "metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    # Metric
    metric_type = Column(String(50), nullable=False, index=True)

    # Dimensions
    organization_id = Column(Integer, nullable=True, index=True)
    workflow_id = Column(Integer, nullable=True, index=True)
    agent_id = Column(Integer, nullable=True, index=True)
    user_id = Column(String(255), nullable=True, index=True)

    # Time
    timestamp = Column(DateTime, nullable=False, index=True)
    granularity = Column(String(50), nullable=False, index=True)

    # Value
    value_numeric = Column(Numeric(precision=20, scale=6), nullable=True)
    value_json = Column(JSON, nullable=True)  # For complex metrics

    # Metadata
    extra_metadata = Column(JSON, default=dict)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_metric_type_time", "metric_type", "timestamp", "granularity"),
        Index("ix_metric_org_time", "organization_id", "timestamp"),
        Index("ix_metric_workflow", "workflow_id", "timestamp"),
    )


class Report(Base):
    """
    Saved report configuration.

    Can be scheduled for automatic generation.
    """
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)

    # Report metadata
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Owner
    created_by = Column(String(255), nullable=False, index=True)
    organization_id = Column(Integer, nullable=True, index=True)

    # Report configuration
    report_type = Column(String(100), nullable=False, index=True)  # executive_summary, cost_analysis, etc.
    metrics = Column(JSON, default=list)  # List of metric types to include
    filters = Column(JSON, default=dict)
    time_range_days = Column(Integer, default=30)

    # Output
    format = Column(String(50), default='pdf', nullable=False)

    # Scheduling
    schedule = Column(String(50), default='none', nullable=False, index=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    recipients = Column(JSON, default=list)  # Email addresses

    # Settings
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_generated_at = Column(DateTime, nullable=True)

    # Relationships
    executions = relationship("ReportExecution", back_populates="report", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_report_owner", "created_by", "organization_id"),
        Index("ix_report_schedule", "schedule", "next_run_at", "is_active"),
    )


class ReportExecution(Base):
    """
    Report execution record.

    Tracks each time a report is generated.
    """
    __tablename__ = "report_executions"

    id = Column(Integer, primary_key=True, index=True)

    # Report
    report_id = Column(Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)

    # Execution
    status = Column(String(50), nullable=False, index=True)  # running, completed, failed
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Output
    output_url = Column(String(500), nullable=True)  # S3 URL or file path
    output_size_bytes = Column(Integer, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)

    # Metrics
    rows_processed = Column(Integer, default=0)
    generation_time_ms = Column(Integer, nullable=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationships
    report = relationship("Report", back_populates="executions")

    __table_args__ = (
        Index("ix_report_exec_status", "report_id", "status"),
        Index("ix_report_exec_time", "started_at"),
    )


class CustomMetric(Base):
    """
    User-defined custom metric.

    Allows users to create their own calculated metrics.
    """
    __tablename__ = "custom_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Metric metadata
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Owner
    created_by = Column(String(255), nullable=False, index=True)
    organization_id = Column(Integer, nullable=True, index=True)

    # Calculation
    formula = Column(Text, nullable=False)  # SQL expression or calculation
    base_metrics = Column(JSON, default=list)  # Metrics this depends on

    # Output
    unit = Column(String(50), nullable=True)  # $, %, seconds, etc.
    format_string = Column(String(100), nullable=True)  # Display format

    # Settings
    is_public = Column(Boolean, default=False, nullable=False)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_custom_metric_owner", "created_by", "organization_id"),
    )


# ============================================================================
# Pydantic Models (API Schemas)
# ============================================================================

class DashboardCreate(BaseModel):
    """Create dashboard."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    dashboard_type: DashboardType = DashboardType.CUSTOM
    layout: Dict[str, Any] = Field(default_factory=dict)
    is_public: bool = False
    tags: List[str] = Field(default_factory=list)


class DashboardUpdate(BaseModel):
    """Update dashboard."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    is_default: Optional[bool] = None
    tags: Optional[List[str]] = None


class DashboardResponse(BaseModel):
    """Dashboard response."""
    id: int
    name: str
    description: Optional[str]
    dashboard_type: DashboardType
    created_by: str
    organization_id: Optional[int]
    layout: Dict[str, Any]
    is_public: bool
    is_default: bool
    view_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    last_viewed_at: Optional[datetime]

    class Config:
        from_attributes = True


class WidgetCreate(BaseModel):
    """Create widget."""
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    widget_type: WidgetType
    metric_type: MetricType
    aggregation_type: AggregationType = AggregationType.AVG
    time_granularity: TimeGranularity = TimeGranularity.DAY
    position_x: int = 0
    position_y: int = 0
    width: int = 4
    height: int = 3
    filters: Dict[str, Any] = Field(default_factory=dict)
    time_range_days: int = 30
    config: Dict[str, Any] = Field(default_factory=dict)


class WidgetUpdate(BaseModel):
    """Update widget."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None
    time_range_days: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


class WidgetResponse(BaseModel):
    """Widget response."""
    id: int
    dashboard_id: int
    title: str
    description: Optional[str]
    widget_type: WidgetType
    metric_type: MetricType
    aggregation_type: AggregationType
    time_granularity: TimeGranularity
    position_x: int
    position_y: int
    width: int
    height: int
    filters: Dict[str, Any]
    time_range_days: int
    config: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class WidgetDataResponse(BaseModel):
    """Widget data response."""
    widget_id: int
    metric_type: MetricType
    data: List[Dict[str, Any]]
    aggregation_type: AggregationType
    time_range_start: datetime
    time_range_end: datetime
    cached: bool
    generated_at: datetime


class MetricQuery(BaseModel):
    """Query metrics."""
    metric_type: MetricType
    aggregation_type: AggregationType = AggregationType.AVG
    time_granularity: TimeGranularity = TimeGranularity.DAY
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    filters: Dict[str, Any] = Field(default_factory=dict)


class MetricValue(BaseModel):
    """Metric value point."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetricResponse(BaseModel):
    """Metric response."""
    metric_type: MetricType
    values: List[MetricValue]
    aggregation_type: AggregationType
    time_granularity: TimeGranularity
    total_count: int


class ReportCreate(BaseModel):
    """Create report."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    report_type: str
    metrics: List[MetricType]
    filters: Dict[str, Any] = Field(default_factory=dict)
    time_range_days: int = 30
    format: ReportFormat = ReportFormat.PDF
    schedule: ReportSchedule = ReportSchedule.NONE
    recipients: List[str] = Field(default_factory=list)


class ReportUpdate(BaseModel):
    """Update report."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    metrics: Optional[List[MetricType]] = None
    filters: Optional[Dict[str, Any]] = None
    time_range_days: Optional[int] = None
    schedule: Optional[ReportSchedule] = None
    recipients: Optional[List[str]] = None
    is_active: Optional[bool] = None


class ReportResponse(BaseModel):
    """Report response."""
    id: int
    name: str
    description: Optional[str]
    report_type: str
    created_by: str
    organization_id: Optional[int]
    metrics: List[str]
    format: ReportFormat
    schedule: ReportSchedule
    next_run_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    last_generated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReportExecutionResponse(BaseModel):
    """Report execution response."""
    id: int
    report_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    output_url: Optional[str]
    output_size_bytes: Optional[int]
    error_message: Optional[str]
    generation_time_ms: Optional[int]

    class Config:
        from_attributes = True


class ROICalculation(BaseModel):
    """ROI calculation result."""
    time_period_days: int
    total_workflows: int
    successful_workflows: int
    total_cost_usd: float
    time_saved_hours: float
    labor_cost_saved_usd: float
    roi_percentage: float
    payback_period_days: Optional[int]
    automation_rate: float


class PerformanceMetrics(BaseModel):
    """Agent performance metrics."""
    agent_id: Optional[int] = None
    workflow_id: Optional[int] = None
    time_period_days: int
    total_executions: int
    success_rate: float
    avg_duration_seconds: float
    p50_duration_seconds: float
    p95_duration_seconds: float
    p99_duration_seconds: float
    error_rate: float
    total_cost_usd: float
    cost_per_execution_usd: float


class CostBreakdown(BaseModel):
    """Cost breakdown analysis."""
    time_period_days: int
    total_cost_usd: float
    by_provider: Dict[str, float]
    by_workflow: Dict[str, float]
    by_agent: Dict[str, float]
    by_model: Dict[str, float]
    top_cost_drivers: List[Dict[str, Any]]

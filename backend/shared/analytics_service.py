"""
Advanced Analytics & BI Dashboard Service - P2 Feature #1

Business logic for analytics dashboards, metrics calculation, and reporting.

Key Features:
- Dashboard and widget management
- Real-time metric calculation
- Pre-calculated metric snapshots
- Report generation and scheduling
- ROI calculator
- Cost analytics
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text, literal_column
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import json


def _json_array_contains(column, value: str):
    """
    Create a database-agnostic JSON array contains condition.

    Works with both PostgreSQL (JSONB) and SQLite (JSON).
    For PostgreSQL: Uses @> operator
    For SQLite: Uses json_each to check if value exists in array
    """
    # Use raw SQL that works for PostgreSQL's JSONB
    # Cast parameter to jsonb for @> operator
    return text(f"({column.key} @> (:json_val)::jsonb OR {column.key} IS NULL)").bindparams(
        json_val=json.dumps([value])
    )

from backend.shared.analytics_models import (
    Dashboard,
    DashboardWidget,
    MetricSnapshot,
    Report,
    ReportExecution,
    CustomMetric,
    DashboardCreate,
    DashboardUpdate,
    WidgetCreate,
    WidgetUpdate,
    ReportCreate,
    ReportUpdate,
    MetricQuery,
    MetricValue,
    ROICalculation,
    PerformanceMetrics,
    CostBreakdown,
    DashboardType,
    WidgetType,
    MetricType,
    AggregationType,
    TimeGranularity,
    ReportFormat,
    ReportSchedule,
)


class AnalyticsService:
    """Service for analytics dashboards and metrics."""

    # ========================================================================
    # Dashboard Management
    # ========================================================================

    @staticmethod
    async def create_dashboard(
        db: AsyncSession,
        dashboard_data: DashboardCreate,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> Dashboard:
        """
        Create new dashboard.

        Args:
            db: Database session
            dashboard_data: Dashboard creation data
            user_id: Creator user ID
            organization_id: Organization ID

        Returns:
            Created dashboard
        """
        # Convert dashboard_type enum to string
        dashboard_type_val = dashboard_data.dashboard_type if isinstance(dashboard_data.dashboard_type, str) else dashboard_data.dashboard_type.value

        dashboard = Dashboard(
            name=dashboard_data.name,
            description=dashboard_data.description,
            dashboard_type=dashboard_type_val,
            layout=dashboard_data.layout,
            is_public=dashboard_data.is_public,
            tags=dashboard_data.tags,
            created_by=user_id,
            organization_id=organization_id,
        )

        db.add(dashboard)
        await db.commit()
        await db.refresh(dashboard)

        return dashboard

    @staticmethod
    async def get_dashboard(
        db: AsyncSession,
        dashboard_id: int,
        user_id: str,
    ) -> Optional[Dashboard]:
        """Get dashboard by ID with access control."""
        # Build the JSON contains condition for shared_with_users
        # Cast parameter to jsonb for @> operator (column is already JSONB)
        shared_with_condition = text(
            "(shared_with_users @> (:user_json)::jsonb OR shared_with_users IS NULL)"
        ).bindparams(user_json=json.dumps([user_id]))

        stmt = select(Dashboard).where(
            and_(
                Dashboard.id == dashboard_id,
                or_(
                    Dashboard.created_by == user_id,
                    Dashboard.is_public == True,
                    shared_with_condition
                )
            )
        )
        result = await db.execute(stmt)
        dashboard = result.scalar_one_or_none()

        if dashboard:
            # Update view tracking
            dashboard.last_viewed_at = datetime.utcnow()
            dashboard.view_count += 1
            await db.commit()

        return dashboard

    @staticmethod
    async def list_dashboards(
        db: AsyncSession,
        user_id: str,
        organization_id: Optional[int] = None,
        dashboard_type: Optional[DashboardType] = None,
        limit: int = 50,
    ) -> List[Dashboard]:
        """List dashboards accessible to user."""
        stmt = select(Dashboard).where(
            or_(
                Dashboard.created_by == user_id,
                Dashboard.is_public == True,
                Dashboard.shared_with_users.op('@>')(func.cast([user_id], JSONB))
            )
        )

        if organization_id:
            stmt = stmt.where(Dashboard.organization_id == organization_id)

        if dashboard_type:
            stmt = stmt.where(Dashboard.dashboard_type == dashboard_type)

        stmt = stmt.order_by(desc(Dashboard.last_viewed_at)).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def update_dashboard(
        db: AsyncSession,
        dashboard_id: int,
        user_id: str,
        dashboard_data: DashboardUpdate,
    ) -> Dashboard:
        """Update dashboard."""
        stmt = select(Dashboard).where(
            and_(
                Dashboard.id == dashboard_id,
                Dashboard.created_by == user_id
            )
        )
        result = await db.execute(stmt)
        dashboard = result.scalar_one_or_none()

        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found or access denied")

        # Update fields
        if dashboard_data.name is not None:
            dashboard.name = dashboard_data.name
        if dashboard_data.description is not None:
            dashboard.description = dashboard_data.description
        if dashboard_data.layout is not None:
            dashboard.layout = dashboard_data.layout
        if dashboard_data.is_public is not None:
            dashboard.is_public = dashboard_data.is_public
        if dashboard_data.is_default is not None:
            dashboard.is_default = dashboard_data.is_default
        if dashboard_data.tags is not None:
            dashboard.tags = dashboard_data.tags

        await db.commit()
        await db.refresh(dashboard)

        return dashboard

    @staticmethod
    async def delete_dashboard(
        db: AsyncSession,
        dashboard_id: int,
        user_id: str,
    ) -> None:
        """Delete dashboard."""
        stmt = select(Dashboard).where(
            and_(
                Dashboard.id == dashboard_id,
                Dashboard.created_by == user_id
            )
        )
        result = await db.execute(stmt)
        dashboard = result.scalar_one_or_none()

        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found or access denied")

        await db.delete(dashboard)
        await db.commit()

    # ========================================================================
    # Widget Management
    # ========================================================================

    @staticmethod
    async def add_widget(
        db: AsyncSession,
        dashboard_id: int,
        widget_data: WidgetCreate,
        user_id: str,
    ) -> DashboardWidget:
        """Add widget to dashboard."""
        # Verify dashboard access
        dashboard = await AnalyticsService.get_dashboard(db, dashboard_id, user_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found or access denied")

        # Convert enums to string values
        widget_type_val = widget_data.widget_type if isinstance(widget_data.widget_type, str) else widget_data.widget_type.value
        metric_type_val = widget_data.metric_type if isinstance(widget_data.metric_type, str) else widget_data.metric_type.value
        aggregation_type_val = widget_data.aggregation_type if isinstance(widget_data.aggregation_type, str) else widget_data.aggregation_type.value
        time_granularity_val = widget_data.time_granularity if isinstance(widget_data.time_granularity, str) else widget_data.time_granularity.value

        widget = DashboardWidget(
            dashboard_id=dashboard_id,
            title=widget_data.title,
            description=widget_data.description,
            widget_type=widget_type_val,
            metric_type=metric_type_val,
            aggregation_type=aggregation_type_val,
            time_granularity=time_granularity_val,
            position_x=widget_data.position_x,
            position_y=widget_data.position_y,
            width=widget_data.width,
            height=widget_data.height,
            filters=widget_data.filters,
            time_range_days=widget_data.time_range_days,
            config=widget_data.config,
        )

        db.add(widget)
        await db.commit()
        await db.refresh(widget)

        return widget

    @staticmethod
    async def update_widget(
        db: AsyncSession,
        widget_id: int,
        widget_data: WidgetUpdate,
        user_id: str,
    ) -> DashboardWidget:
        """Update widget."""
        stmt = select(DashboardWidget).join(Dashboard).where(
            and_(
                DashboardWidget.id == widget_id,
                Dashboard.created_by == user_id
            )
        )
        result = await db.execute(stmt)
        widget = result.scalar_one_or_none()

        if not widget:
            raise ValueError(f"Widget {widget_id} not found or access denied")

        # Update fields
        if widget_data.title is not None:
            widget.title = widget_data.title
        if widget_data.description is not None:
            widget.description = widget_data.description
        if widget_data.position_x is not None:
            widget.position_x = widget_data.position_x
        if widget_data.position_y is not None:
            widget.position_y = widget_data.position_y
        if widget_data.width is not None:
            widget.width = widget_data.width
        if widget_data.height is not None:
            widget.height = widget_data.height
        if widget_data.filters is not None:
            widget.filters = widget_data.filters
        if widget_data.time_range_days is not None:
            widget.time_range_days = widget_data.time_range_days
        if widget_data.config is not None:
            widget.config = widget_data.config

        await db.commit()
        await db.refresh(widget)

        return widget

    @staticmethod
    async def delete_widget(
        db: AsyncSession,
        widget_id: int,
        user_id: str,
    ) -> None:
        """Delete widget."""
        stmt = select(DashboardWidget).join(Dashboard).where(
            and_(
                DashboardWidget.id == widget_id,
                Dashboard.created_by == user_id
            )
        )
        result = await db.execute(stmt)
        widget = result.scalar_one_or_none()

        if not widget:
            raise ValueError(f"Widget {widget_id} not found or access denied")

        await db.delete(widget)
        await db.commit()

    @staticmethod
    async def get_widget_data(
        db: AsyncSession,
        widget_id: int,
        user_id: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Get data for widget.

        Returns cached data if available and fresh, otherwise calculates new data.
        """
        stmt = select(DashboardWidget).join(Dashboard).where(
            and_(
                DashboardWidget.id == widget_id,
                or_(
                    Dashboard.created_by == user_id,
                    Dashboard.is_public == True
                )
            )
        )
        result = await db.execute(stmt)
        widget = result.scalar_one_or_none()

        if not widget:
            raise ValueError(f"Widget {widget_id} not found or access denied")

        # Check cache (5 minute TTL)
        cache_valid = (
            not force_refresh
            and widget.cached_data
            and widget.cache_updated_at
            and (datetime.utcnow() - widget.cache_updated_at) < timedelta(minutes=5)
        )

        if cache_valid:
            return {
                "widget_id": widget_id,
                "metric_type": widget.metric_type,
                "data": widget.cached_data,
                "cached": True,
                "generated_at": widget.cache_updated_at,
            }

        # Calculate new data
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=widget.time_range_days)

        query = MetricQuery(
            metric_type=widget.metric_type,
            aggregation_type=widget.aggregation_type,
            time_granularity=widget.time_granularity,
            start_date=start_date,
            end_date=end_date,
            filters=widget.filters,
        )

        data = await AnalyticsService.query_metric(db, query, user_id)

        # Update cache
        widget.cached_data = [
            {
                "timestamp": v.timestamp.isoformat(),
                "value": v.value,
                "metadata": v.metadata,
            }
            for v in data
        ]
        widget.cache_updated_at = datetime.utcnow()
        await db.commit()

        return {
            "widget_id": widget_id,
            "metric_type": widget.metric_type,
            "data": widget.cached_data,
            "cached": False,
            "generated_at": widget.cache_updated_at,
        }

    # ========================================================================
    # Metric Calculation
    # ========================================================================

    @staticmethod
    async def query_metric(
        db: AsyncSession,
        query: MetricQuery,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> List[MetricValue]:
        """
        Query metric data.

        This is the core metric calculation engine.
        """
        # Set default time range
        end_date = query.end_date or datetime.utcnow()
        start_date = query.start_date or (end_date - timedelta(days=30))

        # Try to use pre-calculated snapshots first
        values = await AnalyticsService._query_metric_snapshots(
            db, query.metric_type, query.aggregation_type, query.time_granularity,
            start_date, end_date, query.filters, organization_id
        )

        if values:
            return values

        # Fall back to calculating from raw data
        values = await AnalyticsService._calculate_metric_from_raw(
            db, query.metric_type, query.aggregation_type, query.time_granularity,
            start_date, end_date, query.filters, organization_id
        )

        return values

    @staticmethod
    async def _query_metric_snapshots(
        db: AsyncSession,
        metric_type: MetricType,
        aggregation_type: AggregationType,
        time_granularity: TimeGranularity,
        start_date: datetime,
        end_date: datetime,
        filters: Dict[str, Any],
        organization_id: Optional[int],
    ) -> List[MetricValue]:
        """Query pre-calculated metric snapshots."""
        stmt = select(MetricSnapshot).where(
            and_(
                MetricSnapshot.metric_type == metric_type,
                MetricSnapshot.granularity == time_granularity,
                MetricSnapshot.timestamp >= start_date,
                MetricSnapshot.timestamp <= end_date,
            )
        )

        if organization_id:
            stmt = stmt.where(MetricSnapshot.organization_id == organization_id)

        # Apply filters
        if filters.get("workflow_id"):
            stmt = stmt.where(MetricSnapshot.workflow_id == filters["workflow_id"])
        if filters.get("agent_id"):
            stmt = stmt.where(MetricSnapshot.agent_id == filters["agent_id"])

        stmt = stmt.order_by(MetricSnapshot.timestamp)

        result = await db.execute(stmt)
        snapshots = result.scalars().all()

        if not snapshots:
            return []

        return [
            MetricValue(
                timestamp=s.timestamp,
                value=float(s.value_numeric) if s.value_numeric else 0.0,
                metadata=s.metadata or {},
            )
            for s in snapshots
        ]

    @staticmethod
    async def _calculate_metric_from_raw(
        db: AsyncSession,
        metric_type: MetricType,
        aggregation_type: AggregationType,
        time_granularity: TimeGranularity,
        start_date: datetime,
        end_date: datetime,
        filters: Dict[str, Any],
        organization_id: Optional[int],
    ) -> List[MetricValue]:
        """
        Calculate metric from raw workflow execution data.

        In production, this would query actual workflow_executions table.
        For demo, returns synthetic data.
        """
        # Generate time buckets
        buckets = AnalyticsService._generate_time_buckets(
            start_date, end_date, time_granularity
        )

        # For demo, return synthetic data
        # In production, this would query workflow_executions, llm_requests, etc.
        values = []
        for i, timestamp in enumerate(buckets):
            # Synthetic value based on metric type
            if metric_type == MetricType.WORKFLOW_SUCCESS_RATE:
                value = 85.0 + (i % 10)
            elif metric_type == MetricType.TOTAL_COST:
                value = 100.0 + (i * 5.5)
            elif metric_type == MetricType.WORKFLOW_EXECUTIONS:
                value = 50 + (i * 3)
            elif metric_type == MetricType.WORKFLOW_DURATION:
                value = 45.2 + (i % 20)
            elif metric_type == MetricType.ERROR_RATE:
                value = 2.5 - (i % 3) * 0.3
            else:
                value = 100.0 * (1 + i * 0.1)

            values.append(
                MetricValue(
                    timestamp=timestamp,
                    value=value,
                    metadata={"synthetic": True}
                )
            )

        return values

    @staticmethod
    def _generate_time_buckets(
        start_date: datetime,
        end_date: datetime,
        granularity: TimeGranularity,
    ) -> List[datetime]:
        """Generate time bucket timestamps."""
        buckets = []
        current = start_date

        if granularity == TimeGranularity.HOUR:
            delta = timedelta(hours=1)
        elif granularity == TimeGranularity.DAY:
            delta = timedelta(days=1)
        elif granularity == TimeGranularity.WEEK:
            delta = timedelta(weeks=1)
        elif granularity == TimeGranularity.MONTH:
            delta = timedelta(days=30)
        else:
            delta = timedelta(days=1)

        while current <= end_date:
            buckets.append(current)
            current += delta

        return buckets

    # ========================================================================
    # Pre-calculated Snapshots
    # ========================================================================

    @staticmethod
    async def create_metric_snapshot(
        db: AsyncSession,
        metric_type: MetricType,
        value: float,
        timestamp: datetime,
        granularity: TimeGranularity,
        organization_id: Optional[int] = None,
        workflow_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MetricSnapshot:
        """Create metric snapshot for fast querying."""
        snapshot = MetricSnapshot(
            metric_type=metric_type,
            organization_id=organization_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
            timestamp=timestamp,
            granularity=granularity,
            value_numeric=value,
            metadata=metadata or {},
        )

        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)

        return snapshot

    # ========================================================================
    # ROI & Business Metrics
    # ========================================================================

    @staticmethod
    async def calculate_roi(
        db: AsyncSession,
        organization_id: Optional[int],
        time_period_days: int = 30,
        hourly_labor_cost: float = 50.0,
    ) -> ROICalculation:
        """
        Calculate ROI for agent automation.

        In production, queries real workflow execution data.
        For demo, returns synthetic calculation.
        """
        # Demo values
        total_workflows = 1250
        successful_workflows = 1150
        total_cost_usd = 450.75
        avg_time_saved_per_workflow = 0.5  # hours
        time_saved_hours = successful_workflows * avg_time_saved_per_workflow
        labor_cost_saved_usd = time_saved_hours * hourly_labor_cost

        # Calculate ROI
        roi_percentage = ((labor_cost_saved_usd - total_cost_usd) / total_cost_usd) * 100
        automation_rate = (successful_workflows / total_workflows) * 100

        # Payback period (days to break even)
        daily_cost = total_cost_usd / time_period_days
        daily_savings = labor_cost_saved_usd / time_period_days
        payback_period_days = int(total_cost_usd / daily_savings) if daily_savings > 0 else None

        return ROICalculation(
            time_period_days=time_period_days,
            total_workflows=total_workflows,
            successful_workflows=successful_workflows,
            total_cost_usd=total_cost_usd,
            time_saved_hours=time_saved_hours,
            labor_cost_saved_usd=labor_cost_saved_usd,
            roi_percentage=roi_percentage,
            payback_period_days=payback_period_days,
            automation_rate=automation_rate,
        )

    @staticmethod
    async def get_performance_metrics(
        db: AsyncSession,
        organization_id: Optional[int] = None,
        workflow_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        time_period_days: int = 30,
    ) -> PerformanceMetrics:
        """
        Get performance metrics for agent/workflow.

        In production, aggregates from workflow_executions.
        For demo, returns synthetic metrics.
        """
        return PerformanceMetrics(
            agent_id=agent_id,
            workflow_id=workflow_id,
            time_period_days=time_period_days,
            total_executions=1250,
            success_rate=92.0,
            avg_duration_seconds=45.6,
            p50_duration_seconds=38.2,
            p95_duration_seconds=89.5,
            p99_duration_seconds=125.3,
            error_rate=8.0,
            total_cost_usd=450.75,
            cost_per_execution_usd=0.36,
        )

    @staticmethod
    async def get_cost_breakdown(
        db: AsyncSession,
        organization_id: Optional[int] = None,
        time_period_days: int = 30,
    ) -> CostBreakdown:
        """
        Get cost breakdown analysis.

        In production, aggregates from llm_requests and workflow_executions.
        For demo, returns synthetic breakdown.
        """
        total_cost = 450.75

        return CostBreakdown(
            time_period_days=time_period_days,
            total_cost_usd=total_cost,
            by_provider={
                "openai": 245.30,
                "anthropic": 125.45,
                "google": 50.00,
                "aws_bedrock": 30.00,
            },
            by_workflow={
                "Customer Onboarding": 180.25,
                "Data Processing": 120.50,
                "Report Generation": 90.00,
                "Email Automation": 60.00,
            },
            by_agent={
                "gpt-4": 200.00,
                "claude-3-opus": 125.45,
                "gpt-3.5-turbo": 75.30,
                "gemini-pro": 50.00,
            },
            by_model={
                "gpt-4": 200.00,
                "claude-3-opus": 125.45,
                "gpt-3.5-turbo": 75.30,
                "gemini-pro": 50.00,
            },
            top_cost_drivers=[
                {"name": "gpt-4", "cost": 200.00, "percentage": 44.4},
                {"name": "claude-3-opus", "cost": 125.45, "percentage": 27.8},
                {"name": "gpt-3.5-turbo", "cost": 75.30, "percentage": 16.7},
            ],
        )

    # ========================================================================
    # Report Management
    # ========================================================================

    @staticmethod
    async def create_report(
        db: AsyncSession,
        report_data: ReportCreate,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> Report:
        """Create report configuration."""
        # Calculate next run time if scheduled
        next_run_at = None
        if report_data.schedule != ReportSchedule.NONE:
            next_run_at = AnalyticsService._calculate_next_run(
                datetime.utcnow(), report_data.schedule
            )

        report = Report(
            name=report_data.name,
            description=report_data.description,
            report_type=report_data.report_type,
            metrics=[m if isinstance(m, str) else m.value for m in report_data.metrics],
            filters=report_data.filters,
            time_range_days=report_data.time_range_days,
            format=report_data.format,
            schedule=report_data.schedule,
            next_run_at=next_run_at,
            recipients=report_data.recipients,
            created_by=user_id,
            organization_id=organization_id,
        )

        db.add(report)
        await db.commit()
        await db.refresh(report)

        return report

    @staticmethod
    async def generate_report(
        db: AsyncSession,
        report_id: int,
        user_id: str,
    ) -> ReportExecution:
        """
        Generate report.

        In production, would generate PDF/CSV/Excel.
        For demo, creates execution record.
        """
        stmt = select(Report).where(
            and_(
                Report.id == report_id,
                Report.created_by == user_id
            )
        )
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()

        if not report:
            raise ValueError(f"Report {report_id} not found or access denied")

        # Create execution record
        execution = ReportExecution(
            report_id=report_id,
            status="running",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        # Simulate report generation
        # In production, would:
        # 1. Query all metrics
        # 2. Generate charts
        # 3. Render PDF/CSV/Excel
        # 4. Upload to S3
        # 5. Send email to recipients

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_url = f"s3://reports/{report_id}/{execution.id}.pdf"
        execution.output_size_bytes = 524288  # 512 KB
        execution.generation_time_ms = 3500
        execution.rows_processed = 1250

        report.last_generated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(execution)

        return execution

    @staticmethod
    def _calculate_next_run(
        current_time: datetime,
        schedule: ReportSchedule,
    ) -> datetime:
        """Calculate next scheduled run time."""
        if schedule == ReportSchedule.DAILY:
            return current_time + timedelta(days=1)
        elif schedule == ReportSchedule.WEEKLY:
            return current_time + timedelta(weeks=1)
        elif schedule == ReportSchedule.MONTHLY:
            return current_time + timedelta(days=30)
        elif schedule == ReportSchedule.QUARTERLY:
            return current_time + timedelta(days=90)
        else:
            return current_time

    # ========================================================================
    # Template Dashboards
    # ========================================================================

    @staticmethod
    async def create_template_dashboard(
        db: AsyncSession,
        template_name: str,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> Dashboard:
        """
        Create dashboard from template.

        Pre-built dashboards:
        - executive_summary: High-level KPIs
        - cost_analysis: Cost breakdown and trends
        - performance_monitoring: Agent/workflow performance
        - usage_analytics: Usage patterns and trends
        """
        templates = {
            "executive_summary": {
                "name": "Executive Summary",
                "description": "High-level KPIs and business metrics",
                "widgets": [
                    {
                        "title": "Total Workflows",
                        "widget_type": WidgetType.METRIC_CARD,
                        "metric_type": MetricType.WORKFLOW_EXECUTIONS,
                        "aggregation_type": AggregationType.SUM,
                        "position_x": 0, "position_y": 0, "width": 3, "height": 2,
                    },
                    {
                        "title": "Success Rate",
                        "widget_type": WidgetType.METRIC_CARD,
                        "metric_type": MetricType.WORKFLOW_SUCCESS_RATE,
                        "aggregation_type": AggregationType.AVG,
                        "position_x": 3, "position_y": 0, "width": 3, "height": 2,
                    },
                    {
                        "title": "Total Cost",
                        "widget_type": WidgetType.METRIC_CARD,
                        "metric_type": MetricType.TOTAL_COST,
                        "aggregation_type": AggregationType.SUM,
                        "position_x": 6, "position_y": 0, "width": 3, "height": 2,
                    },
                    {
                        "title": "ROI",
                        "widget_type": WidgetType.METRIC_CARD,
                        "metric_type": MetricType.ROI,
                        "aggregation_type": AggregationType.AVG,
                        "position_x": 9, "position_y": 0, "width": 3, "height": 2,
                    },
                    {
                        "title": "Workflow Trends",
                        "widget_type": WidgetType.LINE_CHART,
                        "metric_type": MetricType.WORKFLOW_EXECUTIONS,
                        "aggregation_type": AggregationType.COUNT,
                        "position_x": 0, "position_y": 2, "width": 6, "height": 4,
                    },
                    {
                        "title": "Cost Trends",
                        "widget_type": WidgetType.AREA_CHART,
                        "metric_type": MetricType.TOTAL_COST,
                        "aggregation_type": AggregationType.SUM,
                        "position_x": 6, "position_y": 2, "width": 6, "height": 4,
                    },
                ],
            },
            "cost_analysis": {
                "name": "Cost Analysis",
                "description": "Detailed cost breakdown and attribution",
                "widgets": [
                    {
                        "title": "Cost by Provider",
                        "widget_type": WidgetType.PIE_CHART,
                        "metric_type": MetricType.LLM_COST_BY_PROVIDER,
                        "aggregation_type": AggregationType.SUM,
                        "position_x": 0, "position_y": 0, "width": 6, "height": 4,
                    },
                    {
                        "title": "Cost Trends",
                        "widget_type": WidgetType.LINE_CHART,
                        "metric_type": MetricType.TOTAL_COST,
                        "aggregation_type": AggregationType.SUM,
                        "position_x": 6, "position_y": 0, "width": 6, "height": 4,
                    },
                    {
                        "title": "Cost per Workflow",
                        "widget_type": WidgetType.BAR_CHART,
                        "metric_type": MetricType.COST_PER_WORKFLOW,
                        "aggregation_type": AggregationType.AVG,
                        "position_x": 0, "position_y": 4, "width": 12, "height": 4,
                    },
                ],
            },
        }

        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")

        template = templates[template_name]

        # Create dashboard
        dashboard = Dashboard(
            name=template["name"],
            description=template["description"],
            dashboard_type=DashboardType.TEMPLATE,
            created_by=user_id,
            organization_id=organization_id,
        )
        db.add(dashboard)
        await db.commit()
        await db.refresh(dashboard)

        # Add widgets
        for widget_config in template["widgets"]:
            widget = DashboardWidget(
                dashboard_id=dashboard.id,
                **widget_config
            )
            db.add(widget)

        await db.commit()

        # Eager load widgets to prevent lazy loading
        await db.refresh(dashboard, ["widgets"])

        return dashboard

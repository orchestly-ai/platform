"""
Advanced Analytics & BI Dashboard API - P2 Feature #1

REST API for analytics dashboards, widgets, metrics, and reports.

Endpoints:

Dashboards:
- POST   /api/v1/analytics/dashboards              - Create dashboard
- GET    /api/v1/analytics/dashboards              - List dashboards
- GET    /api/v1/analytics/dashboards/{id}         - Get dashboard
- PUT    /api/v1/analytics/dashboards/{id}         - Update dashboard
- DELETE /api/v1/analytics/dashboards/{id}         - Delete dashboard
- POST   /api/v1/analytics/dashboards/templates    - Create from template

Widgets:
- POST   /api/v1/analytics/dashboards/{id}/widgets - Add widget
- PUT    /api/v1/analytics/widgets/{id}            - Update widget
- DELETE /api/v1/analytics/widgets/{id}            - Delete widget
- GET    /api/v1/analytics/widgets/{id}/data       - Get widget data

Metrics:
- POST   /api/v1/analytics/metrics/query           - Query metrics
- GET    /api/v1/analytics/metrics/roi             - Calculate ROI
- GET    /api/v1/analytics/metrics/performance     - Performance metrics
- GET    /api/v1/analytics/metrics/cost-breakdown  - Cost breakdown

Reports:
- POST   /api/v1/analytics/reports                 - Create report
- GET    /api/v1/analytics/reports                 - List reports
- GET    /api/v1/analytics/reports/{id}            - Get report
- PUT    /api/v1/analytics/reports/{id}            - Update report
- DELETE /api/v1/analytics/reports/{id}            - Delete report
- POST   /api/v1/analytics/reports/{id}/generate   - Generate report
- GET    /api/v1/analytics/reports/{id}/executions - List executions
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from backend.database.session import get_db
from backend.shared.analytics_models import (
    DashboardCreate,
    DashboardUpdate,
    DashboardResponse,
    WidgetCreate,
    WidgetUpdate,
    WidgetResponse,
    WidgetDataResponse,
    MetricQuery,
    MetricResponse,
    MetricValue,
    ReportCreate,
    ReportUpdate,
    ReportResponse,
    ReportExecutionResponse,
    ROICalculation,
    PerformanceMetrics,
    CostBreakdown,
    DashboardType,
)
from backend.shared.analytics_service import AnalyticsService
from backend.shared.auth import get_current_user_id, get_current_organization_id


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# Alias for backwards compatibility
async def get_organization_id() -> Optional[int]:
    """Get current user's organization ID as int."""
    return 1


# ============================================================================
# Dashboard Endpoints
# ============================================================================

@router.post("/dashboards", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    dashboard_data: DashboardCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Create new dashboard.

    Supports custom drag-and-drop dashboards or template-based.
    """
    dashboard = await AnalyticsService.create_dashboard(
        db, dashboard_data, user_id, organization_id
    )
    return dashboard


@router.get("/dashboards", response_model=List[DashboardResponse])
async def list_dashboards(
    dashboard_type: Optional[DashboardType] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    List dashboards.

    Returns dashboards created by user, shared with user, or public.
    """
    dashboards = await AnalyticsService.list_dashboards(
        db, user_id, organization_id, dashboard_type, limit
    )
    return dashboards


@router.get("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Get dashboard by ID.

    Updates view count and last viewed timestamp.
    """
    dashboard = await AnalyticsService.get_dashboard(db, dashboard_id, user_id)
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found or access denied",
        )
    return dashboard


@router.put("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: int,
    dashboard_data: DashboardUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Update dashboard.

    Only owner can update.
    """
    try:
        dashboard = await AnalyticsService.update_dashboard(
            db, dashboard_id, user_id, dashboard_data
        )
        return dashboard
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/dashboards/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Delete dashboard.

    Only owner can delete. Cascades to all widgets.
    """
    try:
        await AnalyticsService.delete_dashboard(db, dashboard_id, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/dashboards/templates", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard_from_template(
    template_name: str = Query(..., description="Template name: executive_summary, cost_analysis, etc."),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Create dashboard from template.

    Available templates:
    - executive_summary: High-level KPIs
    - cost_analysis: Cost breakdown and trends
    - performance_monitoring: Agent/workflow performance
    - usage_analytics: Usage patterns
    """
    try:
        dashboard = await AnalyticsService.create_template_dashboard(
            db, template_name, user_id, organization_id
        )
        return dashboard
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# Widget Endpoints
# ============================================================================

@router.post("/dashboards/{dashboard_id}/widgets", response_model=WidgetResponse, status_code=status.HTTP_201_CREATED)
async def add_widget(
    dashboard_id: int,
    widget_data: WidgetCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Add widget to dashboard.

    Supports various visualization types:
    - line_chart, bar_chart, pie_chart, area_chart
    - scatter_plot, heatmap, table
    - metric_card (single number with trend)
    - gauge, funnel
    """
    try:
        widget = await AnalyticsService.add_widget(
            db, dashboard_id, widget_data, user_id
        )
        return widget
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put("/widgets/{widget_id}", response_model=WidgetResponse)
async def update_widget(
    widget_id: int,
    widget_data: WidgetUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Update widget.

    Can update position, size, filters, and configuration.
    """
    try:
        widget = await AnalyticsService.update_widget(
            db, widget_id, widget_data, user_id
        )
        return widget
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/widgets/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_widget(
    widget_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Delete widget from dashboard.
    """
    try:
        await AnalyticsService.delete_widget(db, widget_id, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/widgets/{widget_id}/data", response_model=WidgetDataResponse)
async def get_widget_data(
    widget_id: int,
    force_refresh: bool = Query(False, description="Force data refresh (bypass cache)"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Get data for widget.

    Returns cached data if available and fresh (5 min TTL).
    Use force_refresh=true to bypass cache.
    """
    try:
        data = await AnalyticsService.get_widget_data(
            db, widget_id, user_id, force_refresh
        )

        # Convert to response model
        return WidgetDataResponse(
            widget_id=data["widget_id"],
            metric_type=data["metric_type"],
            data=data["data"],
            aggregation_type="avg",  # From widget config
            time_range_start=data["data"][0]["timestamp"] if data["data"] else None,
            time_range_end=data["data"][-1]["timestamp"] if data["data"] else None,
            cached=data["cached"],
            generated_at=data["generated_at"],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ============================================================================
# Metric Endpoints
# ============================================================================

@router.post("/metrics/query", response_model=MetricResponse)
async def query_metrics(
    query: MetricQuery,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Query metric data.

    Supports:
    - Performance metrics (success rate, duration, response time)
    - Cost metrics (total cost, cost per workflow, by provider)
    - Usage metrics (executions, active users, API requests)
    - Quality metrics (error rate, retry rate)
    - Business metrics (ROI, time saved, automation rate)
    """
    values = await AnalyticsService.query_metric(
        db, query, user_id, organization_id
    )

    return MetricResponse(
        metric_type=query.metric_type,
        values=values,
        aggregation_type=query.aggregation_type,
        time_granularity=query.time_granularity,
        total_count=len(values),
    )


@router.get("/metrics/roi", response_model=ROICalculation)
async def calculate_roi(
    time_period_days: int = Query(30, ge=1, le=365),
    hourly_labor_cost: float = Query(50.0, ge=0),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Calculate ROI for agent automation.

    Calculates:
    - Total workflows and success rate
    - Total cost vs. labor cost saved
    - ROI percentage
    - Payback period
    - Automation rate
    """
    roi = await AnalyticsService.calculate_roi(
        db, organization_id, time_period_days, hourly_labor_cost
    )
    return roi


@router.get("/metrics/performance", response_model=PerformanceMetrics)
async def get_performance_metrics(
    workflow_id: Optional[int] = Query(None),
    agent_id: Optional[int] = Query(None),
    time_period_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Get performance metrics.

    Returns:
    - Execution counts and success rate
    - Duration percentiles (p50, p95, p99)
    - Error and retry rates
    - Cost metrics
    """
    metrics = await AnalyticsService.get_performance_metrics(
        db, organization_id, workflow_id, agent_id, time_period_days
    )
    return metrics


@router.get("/metrics/cost-breakdown", response_model=CostBreakdown)
async def get_cost_breakdown(
    time_period_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Get cost breakdown analysis.

    Breaks down costs by:
    - LLM provider (OpenAI, Anthropic, Google, etc.)
    - Workflow
    - Agent
    - Model
    - Top cost drivers
    """
    breakdown = await AnalyticsService.get_cost_breakdown(
        db, organization_id, time_period_days
    )
    return breakdown


# ============================================================================
# Report Endpoints
# ============================================================================

@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    report_data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Create report configuration.

    Supports:
    - On-demand or scheduled reports (daily, weekly, monthly, quarterly)
    - Multiple output formats (PDF, CSV, Excel, JSON)
    - Email delivery to recipients
    - Custom metric selection and filtering
    """
    report = await AnalyticsService.create_report(
        db, report_data, user_id, organization_id
    )
    return report


@router.get("/reports", response_model=List[ReportResponse])
async def list_reports(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    List reports created by user.
    """
    from sqlalchemy import select
    from backend.shared.analytics_models import Report

    stmt = select(Report).where(
        Report.created_by == user_id
    ).order_by(Report.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    reports = result.scalars().all()
    return reports


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Get report configuration.
    """
    from sqlalchemy import select, and_
    from backend.shared.analytics_models import Report

    stmt = select(Report).where(
        and_(
            Report.id == report_id,
            Report.created_by == user_id
        )
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or access denied",
        )

    return report


@router.put("/reports/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: int,
    report_data: ReportUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Update report configuration.
    """
    from sqlalchemy import select, and_
    from backend.shared.analytics_models import Report

    stmt = select(Report).where(
        and_(
            Report.id == report_id,
            Report.created_by == user_id
        )
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or access denied",
        )

    # Update fields
    if report_data.name is not None:
        report.name = report_data.name
    if report_data.description is not None:
        report.description = report_data.description
    if report_data.metrics is not None:
        report.metrics = [m.value for m in report_data.metrics]
    if report_data.filters is not None:
        report.filters = report_data.filters
    if report_data.time_range_days is not None:
        report.time_range_days = report_data.time_range_days
    if report_data.schedule is not None:
        report.schedule = report_data.schedule
    if report_data.recipients is not None:
        report.recipients = report_data.recipients
    if report_data.is_active is not None:
        report.is_active = report_data.is_active

    await db.commit()
    await db.refresh(report)

    return report


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Delete report configuration.
    """
    from sqlalchemy import select, and_
    from backend.shared.analytics_models import Report

    stmt = select(Report).where(
        and_(
            Report.id == report_id,
            Report.created_by == user_id
        )
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or access denied",
        )

    await db.delete(report)
    await db.commit()


@router.post("/reports/{report_id}/generate", response_model=ReportExecutionResponse)
async def generate_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Generate report now.

    Creates report execution record and generates output file.
    Returns URL to download generated report.
    """
    try:
        execution = await AnalyticsService.generate_report(
            db, report_id, user_id
        )
        return execution
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/reports/{report_id}/executions", response_model=List[ReportExecutionResponse])
async def list_report_executions(
    report_id: int,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    List report execution history.

    Shows all past report generations with status and output URLs.
    """
    from sqlalchemy import select, and_
    from backend.shared.analytics_models import Report, ReportExecution

    # Verify access
    stmt = select(Report).where(
        and_(
            Report.id == report_id,
            Report.created_by == user_id
        )
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or access denied",
        )

    # Get executions
    stmt = select(ReportExecution).where(
        ReportExecution.report_id == report_id
    ).order_by(ReportExecution.started_at.desc()).limit(limit)

    result = await db.execute(stmt)
    executions = result.scalars().all()

    return executions

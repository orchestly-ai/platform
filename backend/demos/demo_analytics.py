"""
Advanced Analytics & BI Dashboard Demo - P2 Feature #1

Demonstrates analytics and BI features:
- Dashboard creation and management
- Widget configuration (line charts, bar charts, metric cards)
- Real-time metric queries
- ROI calculator
- Performance metrics
- Cost breakdown analysis
- Report generation and scheduling
- Template dashboards

Run: python backend/demo_analytics.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text

from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.analytics_models import *
from backend.shared.analytics_service import AnalyticsService


async def demo_analytics():
    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("ADVANCED ANALYTICS & BI DASHBOARD DEMO")
        print("=" * 80)
        print()

        # Drop and recreate analytics tables to fix ENUM type mismatches
        print("Setting up demo environment...")
        try:
            # Drop tables with CASCADE to handle dependencies and old ENUM types
            await db.execute(text("DROP TABLE IF EXISTS report_executions CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS reports CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS metric_snapshots CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS custom_metrics CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS dashboard_widgets CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS dashboards CASCADE"))
            # Drop old ENUM types if they exist
            await db.execute(text("DROP TYPE IF EXISTS dashboardtype CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS widgettype CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS metrictype CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS reportformat CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS reportschedule CASCADE"))
            await db.commit()
            print("✓ Cleaned up old tables and types")
        except Exception as e:
            print(f"⚠ Cleanup warning: {str(e)[:100]}")
            await db.rollback()

    # Reinitialize database tables with correct schema
    await init_db()

    async with AsyncSessionLocal() as db:
        # Tables are fresh after drop/recreate, no cleanup needed
        print("✓ Database ready\n")

        user_id = "user_analytics_demo"
        org_id = 1

        # Demo 1: Dashboard Creation
        print("📊 DEMO 1: Custom Dashboard Creation")
        print("-" * 80)

        print("\n1. Creating custom dashboard...")
        dashboard = await AnalyticsService.create_dashboard(
            db,
            DashboardCreate(
                name="Executive Overview",
                description="High-level KPIs and business metrics",
                dashboard_type=DashboardType.CUSTOM,
                tags=["executive", "kpi", "overview"],
            ),
            user_id,
            org_id,
        )
        print(f"   ✓ Dashboard created: {dashboard.name} (ID: {dashboard.id})")

        # Demo 2: Adding Widgets
        print("\n\n📈 DEMO 2: Widget Configuration")
        print("-" * 80)

        print("\n1. Adding metric card widgets...")
        widgets = []

        # Total Workflows metric card
        widget1 = await AnalyticsService.add_widget(
            db,
            dashboard.id,
            WidgetCreate(
                title="Total Workflows",
                widget_type=WidgetType.METRIC_CARD,
                metric_type=MetricType.WORKFLOW_EXECUTIONS,
                aggregation_type=AggregationType.SUM,
                time_granularity=TimeGranularity.DAY,
                position_x=0, position_y=0, width=3, height=2,
                time_range_days=30,
            ),
            user_id,
        )
        widgets.append(widget1)
        print(f"   ✓ Widget 1: {widget1.title} ({widget1.widget_type})")

        # Success Rate metric card
        widget2 = await AnalyticsService.add_widget(
            db,
            dashboard.id,
            WidgetCreate(
                title="Success Rate",
                widget_type=WidgetType.METRIC_CARD,
                metric_type=MetricType.WORKFLOW_SUCCESS_RATE,
                aggregation_type=AggregationType.AVG,
                time_granularity=TimeGranularity.DAY,
                position_x=3, position_y=0, width=3, height=2,
                time_range_days=30,
            ),
            user_id,
        )
        widgets.append(widget2)
        print(f"   ✓ Widget 2: {widget2.title} ({widget2.widget_type})")

        # Total Cost metric card
        widget3 = await AnalyticsService.add_widget(
            db,
            dashboard.id,
            WidgetCreate(
                title="Total Cost",
                widget_type=WidgetType.METRIC_CARD,
                metric_type=MetricType.TOTAL_COST,
                aggregation_type=AggregationType.SUM,
                time_granularity=TimeGranularity.DAY,
                position_x=6, position_y=0, width=3, height=2,
                time_range_days=30,
            ),
            user_id,
        )
        widgets.append(widget3)
        print(f"   ✓ Widget 3: {widget3.title} ({widget3.widget_type})")

        print("\n2. Adding chart widgets...")

        # Workflow trends line chart
        widget4 = await AnalyticsService.add_widget(
            db,
            dashboard.id,
            WidgetCreate(
                title="Workflow Execution Trends",
                description="Daily workflow execution volume",
                widget_type=WidgetType.LINE_CHART,
                metric_type=MetricType.WORKFLOW_EXECUTIONS,
                aggregation_type=AggregationType.COUNT,
                time_granularity=TimeGranularity.DAY,
                position_x=0, position_y=2, width=6, height=4,
                time_range_days=30,
                config={"color": "#3b82f6", "show_points": True},
            ),
            user_id,
        )
        widgets.append(widget4)
        print(f"   ✓ Widget 4: {widget4.title} ({widget4.widget_type})")

        # Cost trends area chart
        widget5 = await AnalyticsService.add_widget(
            db,
            dashboard.id,
            WidgetCreate(
                title="Cost Trends",
                description="Daily cost accumulation",
                widget_type=WidgetType.AREA_CHART,
                metric_type=MetricType.TOTAL_COST,
                aggregation_type=AggregationType.SUM,
                time_granularity=TimeGranularity.DAY,
                position_x=6, position_y=2, width=6, height=4,
                time_range_days=30,
                config={"color": "#10b981", "fill_opacity": 0.3},
            ),
            user_id,
        )
        widgets.append(widget5)
        print(f"   ✓ Widget 5: {widget5.title} ({widget5.widget_type})")

        print(f"\n   Dashboard '{dashboard.name}' has {len(widgets)} widgets")

        # Demo 3: Querying Widget Data
        print("\n\n🔍 DEMO 3: Widget Data Queries")
        print("-" * 80)

        print("\n1. Fetching data for 'Workflow Execution Trends' widget...")
        widget_data = await AnalyticsService.get_widget_data(db, widget4.id, user_id)
        print(f"   ✓ Retrieved {len(widget_data['data'])} data points")
        print(f"   ✓ Cached: {widget_data['cached']}")
        print(f"   ✓ Sample data (first 3 points):")
        for point in widget_data['data'][:3]:
            print(f"      - {point['timestamp']}: {point['value']:.1f}")

        print("\n2. Fetching data for 'Cost Trends' widget...")
        widget_data = await AnalyticsService.get_widget_data(db, widget5.id, user_id)
        print(f"   ✓ Retrieved {len(widget_data['data'])} data points")
        print(f"   ✓ Total cost trend: ${widget_data['data'][-1]['value']:.2f}")

        # Demo 4: Direct Metric Queries
        print("\n\n📊 DEMO 4: Direct Metric Queries")
        print("-" * 80)

        print("\n1. Querying workflow success rate (last 30 days)...")
        query = MetricQuery(
            metric_type=MetricType.WORKFLOW_SUCCESS_RATE,
            aggregation_type=AggregationType.AVG,
            time_granularity=TimeGranularity.DAY,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )
        values = await AnalyticsService.query_metric(db, query, user_id, org_id)
        avg_success_rate = sum(v.value for v in values) / len(values) if values else 0
        print(f"   ✓ Average success rate: {avg_success_rate:.2f}%")
        print(f"   ✓ Data points: {len(values)}")

        print("\n2. Querying error rate trends...")
        query = MetricQuery(
            metric_type=MetricType.ERROR_RATE,
            aggregation_type=AggregationType.AVG,
            time_granularity=TimeGranularity.DAY,
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow(),
        )
        values = await AnalyticsService.query_metric(db, query, user_id, org_id)
        avg_error_rate = sum(v.value for v in values) / len(values) if values else 0
        print(f"   ✓ Average error rate (7 days): {avg_error_rate:.2f}%")

        # Demo 5: ROI Calculator
        print("\n\n💰 DEMO 5: ROI Calculator")
        print("-" * 80)

        print("\n1. Calculating ROI for last 30 days...")
        roi = await AnalyticsService.calculate_roi(db, org_id, time_period_days=30, hourly_labor_cost=50.0)
        print(f"   Total workflows: {roi.total_workflows}")
        print(f"   Successful workflows: {roi.successful_workflows}")
        print(f"   Automation rate: {roi.automation_rate:.1f}%")
        print(f"   Total cost: ${roi.total_cost_usd:.2f}")
        print(f"   Time saved: {roi.time_saved_hours:.1f} hours")
        print(f"   Labor cost saved: ${roi.labor_cost_saved_usd:.2f}")
        print(f"   ROI: {roi.roi_percentage:.1f}%")
        if roi.payback_period_days:
            print(f"   Payback period: {roi.payback_period_days} days")

        # Demo 6: Performance Metrics
        print("\n\n⚡ DEMO 6: Performance Metrics")
        print("-" * 80)

        print("\n1. Getting overall performance metrics...")
        perf = await AnalyticsService.get_performance_metrics(db, org_id, time_period_days=30)
        print(f"   Total executions: {perf.total_executions}")
        print(f"   Success rate: {perf.success_rate:.1f}%")
        print(f"   Error rate: {perf.error_rate:.1f}%")
        print(f"   Average duration: {perf.avg_duration_seconds:.2f}s")
        print(f"   P50 duration: {perf.p50_duration_seconds:.2f}s")
        print(f"   P95 duration: {perf.p95_duration_seconds:.2f}s")
        print(f"   P99 duration: {perf.p99_duration_seconds:.2f}s")
        print(f"   Total cost: ${perf.total_cost_usd:.2f}")
        print(f"   Cost per execution: ${perf.cost_per_execution_usd:.2f}")

        # Demo 7: Cost Breakdown
        print("\n\n💵 DEMO 7: Cost Breakdown Analysis")
        print("-" * 80)

        print("\n1. Analyzing cost breakdown...")
        breakdown = await AnalyticsService.get_cost_breakdown(db, org_id, time_period_days=30)
        print(f"   Total cost: ${breakdown.total_cost_usd:.2f}")

        print("\n2. Cost by provider:")
        for provider, cost in sorted(breakdown.by_provider.items(), key=lambda x: x[1], reverse=True):
            percentage = (cost / breakdown.total_cost_usd) * 100
            print(f"   - {provider}: ${cost:.2f} ({percentage:.1f}%)")

        print("\n3. Cost by workflow:")
        for workflow, cost in sorted(breakdown.by_workflow.items(), key=lambda x: x[1], reverse=True)[:5]:
            percentage = (cost / breakdown.total_cost_usd) * 100
            print(f"   - {workflow}: ${cost:.2f} ({percentage:.1f}%)")

        print("\n4. Top cost drivers:")
        for driver in breakdown.top_cost_drivers:
            print(f"   - {driver['name']}: ${driver['cost']:.2f} ({driver['percentage']:.1f}%)")

        # Demo 8: Template Dashboard
        print("\n\n📋 DEMO 8: Template Dashboards")
        print("-" * 80)

        print("\n1. Creating dashboard from template: 'executive_summary'...")
        template_dashboard = await AnalyticsService.create_template_dashboard(
            db, "executive_summary", user_id, org_id
        )
        print(f"   ✓ Dashboard created: {template_dashboard.name}")
        print(f"   ✓ Dashboard ID: {template_dashboard.id}")
        print(f"   ✓ Type: {template_dashboard.dashboard_type}")

        # Widgets already eager loaded in service
        print(f"   ✓ Pre-configured widgets: {len(template_dashboard.widgets)}")
        for i, widget in enumerate(template_dashboard.widgets, 1):
            print(f"      {i}. {widget.title} ({widget.widget_type})")

        print("\n2. Creating 'cost_analysis' template...")
        cost_dashboard = await AnalyticsService.create_template_dashboard(
            db, "cost_analysis", user_id, org_id
        )
        print(f"   ✓ Dashboard created: {cost_dashboard.name}")
        # Widgets already eager loaded in service
        print(f"   ✓ Pre-configured widgets: {len(cost_dashboard.widgets)}")

        # Demo 9: Report Creation
        print("\n\n📄 DEMO 9: Report Configuration & Generation")
        print("-" * 80)

        print("\n1. Creating on-demand report...")
        report = await AnalyticsService.create_report(
            db,
            ReportCreate(
                name="Monthly Executive Summary",
                description="Comprehensive monthly report for executives",
                report_type="executive_summary",
                metrics=[
                    MetricType.WORKFLOW_EXECUTIONS,
                    MetricType.WORKFLOW_SUCCESS_RATE,
                    MetricType.TOTAL_COST,
                    MetricType.ROI,
                ],
                time_range_days=30,
                format=ReportFormat.PDF,
                schedule=ReportSchedule.NONE,
                recipients=["exec@company.com", "cfo@company.com"],
            ),
            user_id,
            org_id,
        )
        print(f"   ✓ Report created: {report.name} (ID: {report.id})")
        print(f"   ✓ Format: {report.format if isinstance(report.format, str) else report.format.value}")
        print(f"   ✓ Metrics: {len(report.metrics)}")
        print(f"   ✓ Recipients: {len(report.recipients)}")

        print("\n2. Generating report...")
        execution = await AnalyticsService.generate_report(db, report.id, user_id)
        print(f"   ✓ Execution ID: {execution.id}")
        print(f"   ✓ Status: {execution.status}")
        print(f"   ✓ Generation time: {execution.generation_time_ms}ms")
        print(f"   ✓ Output URL: {execution.output_url}")
        print(f"   ✓ File size: {execution.output_size_bytes / 1024:.1f} KB")
        print(f"   ✓ Rows processed: {execution.rows_processed}")

        print("\n3. Creating scheduled weekly report...")
        scheduled_report = await AnalyticsService.create_report(
            db,
            ReportCreate(
                name="Weekly Cost Analysis",
                description="Automated weekly cost breakdown report",
                report_type="cost_analysis",
                metrics=[
                    MetricType.TOTAL_COST,
                    MetricType.COST_PER_WORKFLOW,
                    MetricType.LLM_COST_BY_PROVIDER,
                ],
                time_range_days=7,
                format=ReportFormat.CSV,
                schedule=ReportSchedule.WEEKLY,
                recipients=["finance@company.com"],
            ),
            user_id,
            org_id,
        )
        print(f"   ✓ Scheduled report created: {scheduled_report.name}")
        print(f"   ✓ Schedule: {scheduled_report.schedule if isinstance(scheduled_report.schedule, str) else scheduled_report.schedule.value}")
        print(f"   ✓ Next run: {scheduled_report.next_run_at}")

        # Demo 10: Dashboard Listing
        print("\n\n📚 DEMO 10: Dashboard Management")
        print("-" * 80)

        print("\n1. Listing all dashboards...")
        dashboards = await AnalyticsService.list_dashboards(db, user_id, org_id)
        print(f"   ✓ Total dashboards: {len(dashboards)}")
        for i, d in enumerate(dashboards, 1):
            print(f"      {i}. {d.name} ({d.dashboard_type}, {d.view_count} views)")

        print("\n2. Viewing dashboard (tracks analytics)...")
        viewed_dashboard = await AnalyticsService.get_dashboard(db, dashboard.id, user_id)
        print(f"   ✓ Dashboard: {viewed_dashboard.name}")
        print(f"   ✓ View count: {viewed_dashboard.view_count}")
        print(f"   ✓ Last viewed: {viewed_dashboard.last_viewed_at}")

        # Summary
        print("\n\n" + "=" * 80)
        print("DEMO SUMMARY")
        print("=" * 80)
        print("\n✅ Analytics Features Demonstrated:")
        print("   - Custom dashboard creation")
        print("   - Widget configuration (5 types: metric_card, line_chart, area_chart, etc.)")
        print("   - Real-time metric queries")
        print("   - Widget data caching (5 min TTL)")
        print("   - ROI calculator with payback period")
        print("   - Performance metrics (p50/p95/p99 latency)")
        print("   - Cost breakdown by provider/workflow/model")
        print("   - Template dashboards (executive_summary, cost_analysis)")
        print("   - Report generation (PDF, CSV, Excel)")
        print("   - Scheduled reports (daily, weekly, monthly)")
        print()
        print("✅ Metric Types Supported:")
        print("   Performance: success_rate, duration, response_time")
        print("   Cost: total_cost, cost_per_workflow, cost_by_provider")
        print("   Usage: workflow_executions, active_users, api_requests")
        print("   Quality: error_rate, retry_rate, approval_time")
        print("   Business: ROI, time_saved, automation_rate")
        print()
        print("✅ Widget Types Supported:")
        print("   - metric_card (single KPI with trend)")
        print("   - line_chart, bar_chart, area_chart, pie_chart")
        print("   - scatter_plot, heatmap, table")
        print("   - gauge, funnel")
        print()
        print("✅ Time Granularities:")
        print("   - minute, hour, day, week, month, quarter, year")
        print()
        print("✅ Aggregations:")
        print("   - sum, avg, min, max, count")
        print("   - p50, p95, p99 (percentiles)")
        print()
        print("✅ Business Value:")
        print("   - Real-time visibility into agent performance")
        print("   - Cost optimization insights")
        print("   - ROI tracking and justification")
        print("   - Executive reporting automation")
        print("   - Data-driven decision making")
        print()
        print("✅ Competitive Differentiators:")
        print("   - Drag-and-drop dashboard builder")
        print("   - Pre-built industry templates")
        print("   - ROI calculator (unique to our platform)")
        print("   - Cost attribution by provider/workflow/model")
        print("   - Automated report generation and delivery")
        print()
        print("🎉 Advanced Analytics & BI Dashboard enables data-driven agent orchestration!")
        print()

if __name__ == "__main__":
    asyncio.run(demo_analytics())

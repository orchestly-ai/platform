#!/usr/bin/env python3
"""
Audit Logging Demo

Demonstrates the comprehensive audit logging system.
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from backend.shared.audit_models import (
    AuditEvent, AuditEventType, AuditSeverity,
    AuditQuery, AuditReport
)


def main():
    """Main demo function."""
    print("=" * 80)
    print("🔍 AUDIT LOGGING SYSTEM DEMONSTRATION")
    print("=" * 80)
    print()

    print("✅ Comprehensive Audit Logging Features:")
    print()

    print("1. EVENT TYPES (60+ Categories):")
    print("   • Authentication Events: login, logout, token operations")
    print("   • User Management: user CRUD, role changes, password resets")
    print("   • Agent Lifecycle: registration, updates, start/stop")
    print("   • Task Lifecycle: creation, assignment, completion, failures")
    print("   • Workflow Operations: CRUD, execution, import/export")
    print("   • Cost & Billing: limits, warnings, budget changes")
    print("   • Configuration: updates, imports, exports")
    print("   • Data Access: reads, exports, deletions")
    print("   • System Events: startup, shutdown, errors, alerts")
    print("   • Security Events: access denied, policy violations, key rotation")
    print()

    print("2. SEVERITY LEVELS:")
    print("   • DEBUG: Verbose debugging information")
    print("   • INFO: Normal operations")
    print("   • NOTICE: Significant events")
    print("   • WARNING: Potentially problematic")
    print("   • ERROR: Errors requiring attention")
    print("   • CRITICAL: Critical security/compliance events")
    print()

    print("3. COMPLIANCE FEATURES:")
    print("   • SOC 2 Compliance: Sensitive action tracking")
    print("   • HIPAA Compliance: PII access logging")
    print("   • GDPR Compliance: Data access auditing")
    print("   • 7-year retention: Default 2,555 days")
    print("   • Tamper-proof: Immutable audit trail")
    print()

    print("4. TRACKING CAPABILITIES:")
    print("   • Who: User ID, email, role")
    print("   • What: Resource type, ID, action, changes")
    print("   • When: Precise timestamps")
    print("   • Where: IP address, user agent")
    print("   • Why: Description, correlation IDs")
    print("   • How: Request/response data")
    print("   • Outcome: Success/failure, error messages")
    print("   • Cost: Financial impact tracking")
    print()

    print("5. QUERY & REPORTING:")
    print("   • Time-series queries (indexed)")
    print("   • User activity tracking")
    print("   • Resource access patterns")
    print("   • Security event analysis")
    print("   • Compliance reporting")
    print("   • CSV export for audits")
    print("   • Correlation tracing")
    print()

    print("6. PERFORMANCE OPTIMIZATIONS:")
    print("   • 25+ specialized indexes")
    print("   • GIN index for tags (fast JSON queries)")
    print("   • Async writes (non-blocking)")
    print("   • Context enrichment (automatic)")
    print("   • Batch query support")
    print()

    print("=" * 80)
    print("📊 SAMPLE AUDIT EVENTS")
    print("=" * 80)
    print()

    # Sample authentication event
    auth_event = AuditEvent(
        event_type=AuditEventType.AUTH_LOGIN,
        action="authenticate",
        description="User logged in successfully",
        severity=AuditSeverity.INFO,
        user_id="user_12345",
        user_email="john.doe@company.com",
        user_role="admin",
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        success=True,
        sensitive_action=True,
        session_id=str(uuid4())
    )

    print("1. AUTHENTICATION EVENT:")
    print(f"   Type: {auth_event.event_type.value}")
    print(f"   User: {auth_event.user_email} ({auth_event.user_role})")
    print(f"   IP: {auth_event.ip_address}")
    print(f"   Success: {auth_event.success}")
    print(f"   Sensitive: {auth_event.sensitive_action}")
    print()

    # Sample agent registration
    agent_event = AuditEvent(
        event_type=AuditEventType.AGENT_REGISTERED,
        action="create",
        description="New agent registered: DataAnalysisAgent",
        severity=AuditSeverity.INFO,
        user_id="user_12345",
        resource_type="agent",
        resource_id="agent_98765",
        resource_name="DataAnalysisAgent",
        request_data={
            "name": "DataAnalysisAgent",
            "framework": "CrewAI",
            "capabilities": ["data_analysis", "report_generation"],
            "max_concurrent_tasks": 10
        },
        success=True
    )

    print("2. AGENT REGISTRATION EVENT:")
    print(f"   Type: {agent_event.event_type.value}")
    print(f"   Resource: {agent_event.resource_type}/{agent_event.resource_id}")
    print(f"   Name: {agent_event.resource_name}")
    print(f"   Capabilities: {agent_event.request_data['capabilities']}")
    print()

    # Sample cost warning
    cost_event = AuditEvent(
        event_type=AuditEventType.COST_LIMIT_WARNING,
        action="cost_tracking",
        description="Agent approaching daily cost limit: $85/$100",
        severity=AuditSeverity.WARNING,
        resource_type="agent",
        resource_id="agent_98765",
        cost_impact=85.0,
        sensitive_action=True,
        tags={"threshold": "85%", "limit_type": "daily"}
    )

    print("3. COST WARNING EVENT:")
    print(f"   Type: {cost_event.event_type.value}")
    print(f"   Severity: {cost_event.severity.value}")
    print(f"   Description: {cost_event.description}")
    print(f"   Cost Impact: ${cost_event.cost_impact}")
    print(f"   Tags: {cost_event.tags}")
    print()

    # Sample security event
    security_event = AuditEvent(
        event_type=AuditEventType.SECURITY_ACCESS_DENIED,
        action="security",
        description="Unauthorized access attempt to admin endpoint",
        severity=AuditSeverity.CRITICAL,
        user_id="user_67890",
        ip_address="203.0.113.42",
        resource_type="api_endpoint",
        resource_id="/api/v1/admin/settings",
        success=False,
        error_code="E403",
        error_message="Insufficient permissions",
        sensitive_action=True,
        metadata={
            "attempted_action": "DELETE",
            "user_role": "viewer",
            "required_role": "admin"
        }
    )

    print("4. SECURITY EVENT:")
    print(f"   Type: {security_event.event_type.value}")
    print(f"   Severity: {security_event.severity.value}")
    print(f"   Description: {security_event.description}")
    print(f"   IP: {security_event.ip_address}")
    print(f"   Error: {security_event.error_message} ({security_event.error_code})")
    print(f"   Metadata: {security_event.metadata}")
    print()

    # Sample workflow update with changes
    workflow_event = AuditEvent(
        event_type=AuditEventType.WORKFLOW_UPDATED,
        action="update",
        description="Workflow configuration updated",
        severity=AuditSeverity.NOTICE,
        user_id="user_12345",
        resource_type="workflow",
        resource_id="workflow_54321",
        resource_name="CustomerOnboarding",
        changes={
            "max_concurrent_tasks": {"old": 5, "new": 10},
            "timeout_seconds": {"old": 300, "new": 600},
            "nodes": {"old": 4, "new": 5}
        },
        success=True,
        correlation_id="workflow_update_batch_2025_12_17"
    )

    print("5. WORKFLOW UPDATE EVENT:")
    print(f"   Type: {workflow_event.event_type.value}")
    print(f"   Resource: {workflow_event.resource_name}")
    print(f"   Changes:")
    for field, change in workflow_event.changes.items():
        print(f"     • {field}: {change['old']} → {change['new']}")
    print(f"   Correlation ID: {workflow_event.correlation_id}")
    print()

    # Sample PII access
    pii_event = AuditEvent(
        event_type=AuditEventType.DATA_EXPORT,
        action="export",
        description="Customer data exported for analysis",
        severity=AuditSeverity.NOTICE,
        user_id="user_12345",
        user_role="data_analyst",
        resource_type="customer_data",
        resource_id="export_20251217_001",
        pii_accessed=True,
        sensitive_action=True,
        request_data={
            "format": "CSV",
            "record_count": 1500,
            "fields": ["email", "phone", "address"]
        },
        tags={"compliance": "GDPR", "purpose": "marketing_analysis"}
    )

    print("6. PII ACCESS EVENT (GDPR/HIPAA):")
    print(f"   Type: {pii_event.event_type.value}")
    print(f"   PII Accessed: {pii_event.pii_accessed}")
    print(f"   User: {pii_event.user_id} ({pii_event.user_role})")
    print(f"   Records: {pii_event.request_data['record_count']}")
    print(f"   Fields: {pii_event.request_data['fields']}")
    print(f"   Purpose: {pii_event.tags['purpose']}")
    print()

    print("=" * 80)
    print("🔗 CORRELATION & TRACING")
    print("=" * 80)
    print()

    correlation_id = str(uuid4())
    print(f"Correlation ID: {correlation_id}")
    print()
    print("Events in same transaction:")

    # Create correlated events
    task_created = AuditEvent(
        event_type=AuditEventType.TASK_CREATED,
        action="create",
        description="Task created for data processing",
        user_id="user_12345",
        resource_type="task",
        resource_id="task_001",
        correlation_id=correlation_id,
        timestamp=datetime.utcnow()
    )

    task_assigned = AuditEvent(
        event_type=AuditEventType.TASK_ASSIGNED,
        action="assign",
        description="Task assigned to DataAnalysisAgent",
        resource_type="task",
        resource_id="task_001",
        correlation_id=correlation_id,
        parent_event_id=task_created.event_id,
        timestamp=datetime.utcnow() + timedelta(seconds=1)
    )

    task_completed = AuditEvent(
        event_type=AuditEventType.TASK_COMPLETED,
        action="complete",
        description="Task completed successfully",
        resource_type="task",
        resource_id="task_001",
        cost_impact=2.50,
        correlation_id=correlation_id,
        parent_event_id=task_assigned.event_id,
        timestamp=datetime.utcnow() + timedelta(seconds=45)
    )

    print(f"1. {task_created.timestamp.strftime('%H:%M:%S.%f')[:-3]} - {task_created.description}")
    print(f"2. {task_assigned.timestamp.strftime('%H:%M:%S.%f')[:-3]} - {task_assigned.description}")
    print(f"3. {task_completed.timestamp.strftime('%H:%M:%S.%f')[:-3]} - {task_completed.description} (Cost: ${task_completed.cost_impact})")
    print()

    print("=" * 80)
    print("📈 REPORTING CAPABILITIES")
    print("=" * 80)
    print()

    print("Available Reports:")
    print("  • User Activity Report: Who did what, when?")
    print("  • Resource Access Report: What was accessed?")
    print("  • Security Incident Report: Failed auth, policy violations")
    print("  • Compliance Report: PII access, sensitive actions")
    print("  • Cost Impact Report: Financial tracking")
    print("  • Error Analysis Report: Common failures")
    print("  • Time-series Analysis: Activity patterns")
    print()

    print("Query Examples:")
    print("  1. Failed authentication attempts in last 24h")
    print("  2. All PII access by user_id=user_12345")
    print("  3. Cost limit warnings in last week")
    print("  4. Security events with severity=CRITICAL")
    print("  5. Workflow changes by admin users")
    print("  6. Complete trace for correlation_id")
    print()

    print("=" * 80)
    print("✅ AUDIT LOGGING SYSTEM READY")
    print("=" * 80)
    print()

    print("Key Benefits:")
    print("  ✓ 70% of enterprises can now trace agent decisions")
    print("  ✓ SOC 2 / HIPAA / GDPR compliance ready")
    print("  ✓ Forensic debugging with complete context")
    print("  ✓ Automatic security incident detection")
    print("  ✓ Cost attribution and tracking")
    print("  ✓ 7-year retention for regulatory compliance")
    print("  ✓ Fast queries with 25+ specialized indexes")
    print("  ✓ CSV export for external audits")
    print()

    print("API Endpoints:")
    print("  • GET  /api/v1/audit/events - Query audit events")
    print("  • GET  /api/v1/audit/events/{id} - Get specific event")
    print("  • GET  /api/v1/audit/events/correlation/{id} - Trace transaction")
    print("  • GET  /api/v1/audit/report - Generate compliance report")
    print("  • GET  /api/v1/audit/export/csv - Export to CSV")
    print("  • GET  /api/v1/audit/types - List event types")
    print("  • GET  /api/v1/audit/severities - List severity levels")
    print()

    print("Database Migration:")
    print("  • Run: alembic upgrade head")
    print("  • Creates audit_events table with 25+ indexes")
    print("  • Ready for TimescaleDB hypertable conversion")
    print()

    print("=" * 80)



if __name__ == "__main__":
    main()

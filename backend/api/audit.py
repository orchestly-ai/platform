"""
Audit Log API Endpoints

RESTful API for querying and reporting on audit logs.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from backend.database.session import get_db
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import (
    AuditEventType, AuditSeverity, AuditQuery, AuditReport
)
from backend.api.response_transformers import ResponseTransformer
from backend.shared.plan_enforcement import enforce_feature

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


# Request/Response Models

class AuditEventResponse(BaseModel):
    """Audit event response model"""
    event_id: UUID
    event_type: str
    severity: str
    timestamp: datetime
    user_id: Optional[str]
    user_email: Optional[str]
    user_role: Optional[str]
    session_id: Optional[str]
    request_id: Optional[str]
    ip_address: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    resource_name: Optional[str]
    action: str
    description: str
    changes: Optional[dict]
    success: bool
    error_message: Optional[str]
    error_code: Optional[str]
    cost_impact: Optional[float]
    tags: Optional[dict]
    pii_accessed: bool
    sensitive_action: bool
    correlation_id: Optional[str]
    parent_event_id: Optional[UUID]

    class Config:
        from_attributes = True


class AuditQueryRequest(BaseModel):
    """Audit query request"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    event_types: Optional[List[str]] = None
    user_ids: Optional[List[str]] = None
    resource_types: Optional[List[str]] = None
    resource_ids: Optional[List[str]] = None
    actions: Optional[List[str]] = None
    severities: Optional[List[str]] = None
    success_only: Optional[bool] = None
    failures_only: bool = False
    pii_accessed: Optional[bool] = None
    sensitive_only: bool = False
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    parent_event_id: Optional[UUID] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    sort_by: str = "timestamp"
    sort_order: str = "desc"


class AuditQueryResponse(BaseModel):
    """Audit query response"""
    events: List[AuditEventResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class AuditReportResponse(BaseModel):
    """Audit report response"""
    total_events: int
    event_type_breakdown: dict
    severity_breakdown: dict
    user_activity: dict
    resource_activity: dict
    success_rate: float
    pii_access_count: int
    sensitive_action_count: int
    time_range: tuple[datetime, datetime]
    most_active_users: List[tuple[str, int]]
    most_accessed_resources: List[tuple[str, int]]
    most_common_errors: List[tuple[str, int]]
    generated_at: datetime

    class Config:
        from_attributes = True


class AuditEventTypeInfo(BaseModel):
    """Audit event type information"""
    name: str
    value: str
    category: str


class AuditSeverityInfo(BaseModel):
    """Audit severity information"""
    name: str
    value: str
    level: int


# Endpoints

@router.get("/events", response_model=AuditQueryResponse)
async def query_audit_events(
    start_time: Optional[datetime] = Query(None, description="Start time (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="End time (ISO 8601)"),
    event_type: Optional[str] = Query(None, description="Event type filter"),
    user_id: Optional[str] = Query(None, description="User ID filter"),
    resource_type: Optional[str] = Query(None, description="Resource type filter"),
    resource_id: Optional[str] = Query(None, description="Resource ID filter"),
    action: Optional[str] = Query(None, description="Action filter"),
    severity: Optional[str] = Query(None, description="Severity filter"),
    success_only: Optional[bool] = Query(None, description="Show only successful events"),
    failures_only: bool = Query(False, description="Show only failed events"),
    pii_accessed: Optional[bool] = Query(None, description="Filter by PII access"),
    sensitive_only: bool = Query(False, description="Show only sensitive actions"),
    session_id: Optional[str] = Query(None, description="Session ID filter"),
    correlation_id: Optional[str] = Query(None, description="Correlation ID filter"),
    limit: int = Query(100, ge=1, le=1000, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    sort_by: str = Query("timestamp", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Query audit events with filtering and pagination.

    Example queries:
    - Get last 100 events: GET /audit/events
    - Failed auth events: GET /audit/events?event_type=auth.failed&failures_only=true
    - PII access: GET /audit/events?pii_accessed=true
    - User activity: GET /audit/events?user_id=user123&start_time=2025-01-01T00:00:00Z
    """
    await enforce_feature("audit_logs", "default", db)

    audit_logger = get_audit_logger()

    # Build query
    query = AuditQuery(
        start_time=start_time,
        end_time=end_time,
        event_types=[AuditEventType(event_type)] if event_type else None,
        user_ids=[user_id] if user_id else None,
        resource_types=[resource_type] if resource_type else None,
        resource_ids=[resource_id] if resource_id else None,
        actions=[action] if action else None,
        severities=[AuditSeverity(severity)] if severity else None,
        success_only=success_only,
        failures_only=failures_only,
        pii_accessed=pii_accessed,
        sensitive_only=sensitive_only,
        session_id=session_id,
        correlation_id=correlation_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order
    )

    # Execute query
    events, total = await audit_logger.query_events(query, db)

    # Convert to response model and transform to frontend format
    event_responses = [
        AuditEventResponse(
            event_id=e.event_id,
            event_type=e.event_type,  # Already a string in DB
            severity=e.severity,      # Already a string in DB
            timestamp=e.timestamp,
            user_id=e.user_id,
            user_email=e.user_email,
            user_role=e.user_role,
            session_id=e.session_id,
            request_id=e.request_id,
            ip_address=str(e.ip_address) if e.ip_address else None,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            resource_name=e.resource_name,
            action=e.action,
            description=e.description,
            changes=e.changes,
            success=e.success,
            error_message=e.error_message,
            error_code=e.error_code,
            cost_impact=e.cost_impact,
            tags=e.tags,
            pii_accessed=e.pii_accessed,
            sensitive_action=e.sensitive_action,
            correlation_id=e.correlation_id,
            parent_event_id=e.parent_event_id
        )
        for e in events
    ]

    return AuditQueryResponse(
        events=event_responses,  # Don't transform - Pydantic handles serialization
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total
    )


@router.get("/events/{event_id}", response_model=AuditEventResponse)
async def get_audit_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific audit event by ID"""
    audit_logger = get_audit_logger()

    # Query single event
    query = AuditQuery(limit=1, offset=0)
    events, _ = await audit_logger.query_events(query, db)

    event = next((e for e in events if e.event_id == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")

    event_response = AuditEventResponse(
        event_id=event.event_id,
        event_type=event.event_type.value,
        severity=event.severity.value,
        timestamp=event.timestamp,
        user_id=event.user_id,
        user_email=event.user_email,
        user_role=event.user_role,
        session_id=event.session_id,
        request_id=event.request_id,
        ip_address=str(event.ip_address) if event.ip_address else None,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        resource_name=event.resource_name,
        action=event.action,
        description=event.description,
        changes=event.changes,
        success=event.success,
        error_message=event.error_message,
        error_code=event.error_code,
        cost_impact=event.cost_impact,
        tags=event.tags,
        pii_accessed=event.pii_accessed,
        sensitive_action=event.sensitive_action,
        correlation_id=event.correlation_id,
        parent_event_id=event.parent_event_id
    )

    # Transform to frontend format
    return ResponseTransformer.transform_audit_log_entry(event_response)


@router.get("/events/correlation/{correlation_id}", response_model=List[AuditEventResponse])
async def get_correlated_events(
    correlation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all events with the same correlation ID.

    Useful for tracing a complete workflow or transaction.
    """
    audit_logger = get_audit_logger()

    query = AuditQuery(
        correlation_id=correlation_id,
        limit=1000,  # High limit for complete traces
        sort_by="timestamp",
        sort_order="asc"
    )

    events, _ = await audit_logger.query_events(query, db)

    event_responses = [
        AuditEventResponse(
            event_id=e.event_id,
            event_type=e.event_type.value,
            severity=e.severity.value,
            timestamp=e.timestamp,
            user_id=e.user_id,
            user_email=e.user_email,
            user_role=e.user_role,
            session_id=e.session_id,
            request_id=e.request_id,
            ip_address=str(e.ip_address) if e.ip_address else None,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            resource_name=e.resource_name,
            action=e.action,
            description=e.description,
            changes=e.changes,
            success=e.success,
            error_message=e.error_message,
            error_code=e.error_code,
            cost_impact=e.cost_impact,
            tags=e.tags,
            pii_accessed=e.pii_accessed,
            sensitive_action=e.sensitive_action,
            correlation_id=e.correlation_id,
            parent_event_id=e.parent_event_id
        )
        for e in events
    ]

    # Transform to frontend format
    return ResponseTransformer.transform_list(
        event_responses,
        ResponseTransformer.transform_audit_log_entry
    )


@router.get("/report", response_model=AuditReportResponse)
async def generate_audit_report(
    start_time: datetime = Query(..., description="Report start time"),
    end_time: datetime = Query(..., description="Report end time"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate comprehensive audit report for a time period.

    Example:
    - Last 7 days: GET /audit/report?start_time=2025-01-10T00:00:00Z&end_time=2025-01-17T00:00:00Z
    - Last month: GET /audit/report?start_time=2024-12-01T00:00:00Z&end_time=2025-01-01T00:00:00Z
    """
    await enforce_feature("advanced_audit", "default", db)

    if end_time < start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    # Limit report to 90 days max
    if (end_time - start_time).days > 90:
        raise HTTPException(status_code=400, detail="Report period cannot exceed 90 days")

    audit_logger = get_audit_logger()
    report = await audit_logger.generate_report(start_time, end_time, db)

    return AuditReportResponse(
        total_events=report.total_events,
        event_type_breakdown=report.event_type_breakdown,
        severity_breakdown=report.severity_breakdown,
        user_activity=report.user_activity,
        resource_activity=report.resource_activity,
        success_rate=report.success_rate,
        pii_access_count=report.pii_access_count,
        sensitive_action_count=report.sensitive_action_count,
        time_range=report.time_range,
        most_active_users=report.most_active_users,
        most_accessed_resources=report.most_accessed_resources,
        most_common_errors=report.most_common_errors,
        generated_at=report.generated_at
    )


@router.get("/types", response_model=List[AuditEventTypeInfo])
async def list_audit_event_types():
    """List all available audit event types"""
    return [
        AuditEventTypeInfo(
            name=event_type.name,
            value=event_type.value,
            category=event_type.value.split('.')[0]
        )
        for event_type in AuditEventType
    ]


@router.get("/severities", response_model=List[AuditSeverityInfo])
async def list_audit_severities():
    """List all available audit severity levels"""
    severity_levels = {
        AuditSeverity.DEBUG: 0,
        AuditSeverity.INFO: 1,
        AuditSeverity.NOTICE: 2,
        AuditSeverity.WARNING: 3,
        AuditSeverity.ERROR: 4,
        AuditSeverity.CRITICAL: 5
    }

    return [
        AuditSeverityInfo(
            name=severity.name,
            value=severity.value,
            level=severity_levels[severity]
        )
        for severity in AuditSeverity
    ]


@router.get("/export/csv")
async def export_audit_events_csv(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Export audit events as CSV.

    Returns a CSV file download.
    """
    await enforce_feature("advanced_audit", "default", db)

    if end_time < start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    audit_logger = get_audit_logger()

    query = AuditQuery(
        start_time=start_time,
        end_time=end_time,
        limit=10000,  # Max export limit
        sort_by="timestamp",
        sort_order="asc"
    )

    events, total = await audit_logger.query_events(query, db)

    if total > 10000:
        raise HTTPException(
            status_code=400,
            detail=f"Too many events ({total}). Please narrow your time range or use pagination."
        )

    # Generate CSV
    import io
    import csv

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Timestamp', 'Event Type', 'Severity', 'User ID', 'User Email',
        'Action', 'Resource Type', 'Resource ID', 'Description',
        'Success', 'Error Message', 'Cost Impact', 'PII Accessed',
        'Sensitive Action', 'IP Address', 'Session ID', 'Correlation ID'
    ])

    # Rows
    for event in events:
        writer.writerow([
            event.timestamp.isoformat(),
            event.event_type.value,
            event.severity.value,
            event.user_id or '',
            event.user_email or '',
            event.action,
            event.resource_type or '',
            event.resource_id or '',
            event.description,
            'Yes' if event.success else 'No',
            event.error_message or '',
            event.cost_impact or '',
            'Yes' if event.pii_accessed else 'No',
            'Yes' if event.sensitive_action else 'No',
            str(event.ip_address) if event.ip_address else '',
            event.session_id or '',
            event.correlation_id or ''
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=audit_events_{start_time.date()}_{end_time.date()}.csv"
        }
    )

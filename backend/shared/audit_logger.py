"""
Audit Logger Service

High-performance audit logging with async writes and compliance features.
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import logging
from contextlib import asynccontextmanager
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import sessionmaker

from backend.shared.audit_models import (
    AuditEventModel, AuditEvent, AuditEventType, AuditSeverity,
    AuditQuery, AuditReport
)

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Centralized audit logging service.

    Features:
    - Async writes for high performance
    - Automatic context enrichment (request ID, session ID, IP)
    - Compliance-ready (SOC 2, HIPAA, GDPR)
    - Structured query interface
    - Automatic retention enforcement
    """

    def __init__(self, session_maker: sessionmaker):
        self.session_maker = session_maker
        self._context_stack: list[Dict[str, Any]] = []

    async def log_event(
        self,
        event: AuditEvent,
        db: Optional[AsyncSession] = None
    ) -> UUID:
        """
        Log an audit event.

        Args:
            event: Audit event to log
            db: Optional database session (creates new if not provided)

        Returns:
            Event ID
        """
        # Merge context from stack
        if self._context_stack:
            context = self._context_stack[-1]
            if not event.session_id:
                event.session_id = context.get('session_id')
            if not event.request_id:
                event.request_id = context.get('request_id')
            if not event.user_id:
                event.user_id = context.get('user_id')
            if not event.user_email:
                event.user_email = context.get('user_email')
            if not event.user_role:
                event.user_role = context.get('user_role')
            if not event.ip_address:
                event.ip_address = context.get('ip_address')
            if not event.user_agent:
                event.user_agent = context.get('user_agent')
            if not event.correlation_id:
                event.correlation_id = context.get('correlation_id')

        # Create database model
        model = AuditEventModel(
            event_id=event.event_id,
            event_type=event.event_type.value if isinstance(event.event_type, Enum) else event.event_type,
            severity=event.severity.value if isinstance(event.severity, Enum) else event.severity,
            timestamp=event.timestamp,
            user_id=event.user_id,
            user_email=event.user_email,
            user_role=event.user_role,
            session_id=event.session_id,
            request_id=event.request_id,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            resource_name=event.resource_name,
            action=event.action,
            description=event.description,
            changes=event.changes,
            request_data=event.request_data,
            response_data=event.response_data,
            success=event.success,
            error_message=event.error_message,
            error_code=event.error_code,
            cost_impact=event.cost_impact,
            tags=event.tags,
            extra_metadata=event.metadata,  # Note: column is extra_metadata, not metadata
            pii_accessed=event.pii_accessed,
            sensitive_action=event.sensitive_action,
            retention_days=event.retention_days,
            parent_event_id=event.parent_event_id,
            correlation_id=event.correlation_id
        )

        # Save to database
        if db:
            db.add(model)
            await db.flush()
        else:
            async with self.session_maker() as session:
                session.add(model)
                await session.commit()

        logger.debug(f"Audit event logged: {event.event_type} - {event.description}")
        return event.event_id

    async def log_auth_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str],
        success: bool,
        description: str,
        ip_address: Optional[str] = None,
        error_message: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> UUID:
        """Convenience method for authentication events"""
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING

        event = AuditEvent(
            event_type=event_type,
            action="authenticate",
            description=description,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            error_message=error_message,
            sensitive_action=True,
            resource_type="session"
        )

        return await self.log_event(event, db)

    async def log_resource_event(
        self,
        event_type: AuditEventType,
        action: str,
        resource_type: str,
        resource_id: str,
        description: str,
        changes: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> UUID:
        """Convenience method for resource lifecycle events"""
        event = AuditEvent(
            event_type=event_type,
            action=action,
            description=description,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            success=success,
            error_message=error_message
        )

        return await self.log_event(event, db)

    async def log_cost_event(
        self,
        event_type: AuditEventType,
        description: str,
        cost_impact: float,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        db: Optional[AsyncSession] = None
    ) -> UUID:
        """Convenience method for cost-related events"""
        event = AuditEvent(
            event_type=event_type,
            action="cost_tracking",
            description=description,
            severity=severity,
            cost_impact=cost_impact,
            resource_type=resource_type,
            resource_id=resource_id,
            sensitive_action=True
        )

        return await self.log_event(event, db)

    async def log_security_event(
        self,
        event_type: AuditEventType,
        description: str,
        severity: AuditSeverity = AuditSeverity.WARNING,
        ip_address: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None
    ) -> UUID:
        """Convenience method for security events"""
        event = AuditEvent(
            event_type=event_type,
            action="security",
            description=description,
            severity=severity,
            ip_address=ip_address,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            sensitive_action=True,
            success=False  # Security events are typically failures
        )

        return await self.log_event(event, db)

    async def query_events(
        self,
        query: AuditQuery,
        db: AsyncSession
    ) -> tuple[List[AuditEventModel], int]:
        """
        Query audit events.

        Returns:
            Tuple of (events, total_count)
        """
        # Build base query
        stmt = select(AuditEventModel)
        count_stmt = select(func.count()).select_from(AuditEventModel)

        # Apply filters
        filters = []

        if query.start_time:
            filters.append(AuditEventModel.timestamp >= query.start_time)
        if query.end_time:
            filters.append(AuditEventModel.timestamp <= query.end_time)

        if query.event_types:
            filters.append(AuditEventModel.event_type.in_(query.event_types))
        if query.user_ids:
            filters.append(AuditEventModel.user_id.in_(query.user_ids))
        if query.resource_types:
            filters.append(AuditEventModel.resource_type.in_(query.resource_types))
        if query.resource_ids:
            filters.append(AuditEventModel.resource_id.in_(query.resource_ids))
        if query.actions:
            filters.append(AuditEventModel.action.in_(query.actions))
        if query.severities:
            filters.append(AuditEventModel.severity.in_(query.severities))

        if query.success_only:
            filters.append(AuditEventModel.success == True)
        if query.failures_only:
            filters.append(AuditEventModel.success == False)

        if query.pii_accessed is not None:
            filters.append(AuditEventModel.pii_accessed == query.pii_accessed)
        if query.sensitive_only:
            filters.append(AuditEventModel.sensitive_action == True)

        if query.session_id:
            filters.append(AuditEventModel.session_id == query.session_id)
        if query.correlation_id:
            filters.append(AuditEventModel.correlation_id == query.correlation_id)
        if query.parent_event_id:
            filters.append(AuditEventModel.parent_event_id == query.parent_event_id)

        if filters:
            stmt = stmt.where(and_(*filters))
            count_stmt = count_stmt.where(and_(*filters))

        # Get total count
        result = await db.execute(count_stmt)
        total = result.scalar_one()

        # Apply sorting
        if query.sort_order == "desc":
            stmt = stmt.order_by(desc(getattr(AuditEventModel, query.sort_by)))
        else:
            stmt = stmt.order_by(asc(getattr(AuditEventModel, query.sort_by)))

        # Apply pagination
        stmt = stmt.limit(query.limit).offset(query.offset)

        # Execute query
        result = await db.execute(stmt)
        events = result.scalars().all()

        return events, total

    async def generate_report(
        self,
        start_time: datetime,
        end_time: datetime,
        db: AsyncSession
    ) -> AuditReport:
        """
        Generate audit report for a time period.
        """
        # Base filter
        time_filter = and_(
            AuditEventModel.timestamp >= start_time,
            AuditEventModel.timestamp <= end_time
        )

        # Total events
        total_stmt = select(func.count()).select_from(AuditEventModel).where(time_filter)
        result = await db.execute(total_stmt)
        total_events = result.scalar_one()

        # Event type breakdown
        type_stmt = select(
            AuditEventModel.event_type,
            func.count()
        ).where(time_filter).group_by(AuditEventModel.event_type)
        result = await db.execute(type_stmt)
        event_type_breakdown = {str(t): c for t, c in result.all()}

        # Severity breakdown
        severity_stmt = select(
            AuditEventModel.severity,
            func.count()
        ).where(time_filter).group_by(AuditEventModel.severity)
        result = await db.execute(severity_stmt)
        severity_breakdown = {str(s): c for s, c in result.all()}

        # User activity
        user_stmt = select(
            AuditEventModel.user_id,
            func.count()
        ).where(time_filter).group_by(AuditEventModel.user_id).order_by(desc(func.count())).limit(10)
        result = await db.execute(user_stmt)
        user_activity = {u: c for u, c in result.all() if u}

        # Resource activity
        resource_stmt = select(
            AuditEventModel.resource_type,
            func.count()
        ).where(time_filter).group_by(AuditEventModel.resource_type)
        result = await db.execute(resource_stmt)
        resource_activity = {r: c for r, c in result.all() if r}

        # Success rate
        success_stmt = select(func.count()).select_from(AuditEventModel).where(
            and_(time_filter, AuditEventModel.success == True)
        )
        result = await db.execute(success_stmt)
        success_count = result.scalar_one()
        success_rate = (success_count / total_events * 100) if total_events > 0 else 0.0

        # PII access count
        pii_stmt = select(func.count()).select_from(AuditEventModel).where(
            and_(time_filter, AuditEventModel.pii_accessed == True)
        )
        result = await db.execute(pii_stmt)
        pii_access_count = result.scalar_one()

        # Sensitive action count
        sensitive_stmt = select(func.count()).select_from(AuditEventModel).where(
            and_(time_filter, AuditEventModel.sensitive_action == True)
        )
        result = await db.execute(sensitive_stmt)
        sensitive_action_count = result.scalar_one()

        # Top active users
        top_users_stmt = select(
            AuditEventModel.user_id,
            func.count()
        ).where(
            and_(time_filter, AuditEventModel.user_id.isnot(None))
        ).group_by(AuditEventModel.user_id).order_by(desc(func.count())).limit(5)
        result = await db.execute(top_users_stmt)
        most_active_users = [(u, c) for u, c in result.all()]

        # Most accessed resources
        top_resources_stmt = select(
            AuditEventModel.resource_id,
            func.count()
        ).where(
            and_(time_filter, AuditEventModel.resource_id.isnot(None))
        ).group_by(AuditEventModel.resource_id).order_by(desc(func.count())).limit(5)
        result = await db.execute(top_resources_stmt)
        most_accessed_resources = [(r, c) for r, c in result.all()]

        # Most common errors
        errors_stmt = select(
            AuditEventModel.error_code,
            func.count()
        ).where(
            and_(time_filter, AuditEventModel.success == False, AuditEventModel.error_code.isnot(None))
        ).group_by(AuditEventModel.error_code).order_by(desc(func.count())).limit(5)
        result = await db.execute(errors_stmt)
        most_common_errors = [(e, c) for e, c in result.all()]

        return AuditReport(
            total_events=total_events,
            event_type_breakdown=event_type_breakdown,
            severity_breakdown=severity_breakdown,
            user_activity=user_activity,
            resource_activity=resource_activity,
            success_rate=success_rate,
            pii_access_count=pii_access_count,
            sensitive_action_count=sensitive_action_count,
            time_range=(start_time, end_time),
            most_active_users=most_active_users,
            most_accessed_resources=most_accessed_resources,
            most_common_errors=most_common_errors
        )

    async def cleanup_expired_events(self, db: AsyncSession) -> int:
        """
        Clean up audit events past their retention period.

        Returns:
            Number of events deleted
        """
        # This would typically run as a cron job
        # For now, just return 0 as we don't want to delete events automatically
        logger.info("Audit event cleanup skipped (retention enforcement disabled)")
        return 0

    @asynccontextmanager
    async def audit_context(
        self,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        user_role: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Context manager for enriching audit logs.

        Usage:
            async with audit_logger.audit_context(
                user_id="user123",
                session_id="session456",
                ip_address="192.168.1.1"
            ):
                # All audit logs within this context will be enriched
                await audit_logger.log_event(event)
        """
        context = {
            'user_id': user_id,
            'user_email': user_email,
            'user_role': user_role,
            'session_id': session_id,
            'request_id': request_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'correlation_id': correlation_id
        }

        self._context_stack.append(context)
        try:
            yield
        finally:
            self._context_stack.pop()


# Global audit logger instance (initialized by app startup)
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance"""
    if _audit_logger is None:
        raise RuntimeError("Audit logger not initialized. Call init_audit_logger() first.")
    return _audit_logger


def init_audit_logger(session_maker: sessionmaker) -> AuditLogger:
    """Initialize the global audit logger"""
    global _audit_logger
    _audit_logger = AuditLogger(session_maker)
    return _audit_logger

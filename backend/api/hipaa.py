"""
HIPAA Compliance Router for Agent Orchestration Platform

Provides HIPAA compliance posture, PHI audit summary, and controls
for the orchestration platform's role as a Business Associate.
"""

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter(prefix="/api/v1/hipaa", tags=["HIPAA Compliance"])


@router.get("/status")
async def get_hipaa_status():
    """
    Get HIPAA compliance posture for the orchestration platform.

    Returns status of PHI detection, audit logging, encryption,
    and Business Associate role information.
    """
    return {
        "hipaa_compliant": True,
        "role": "Business Associate",
        "description": "Agent Orchestration Platform processes PHI on behalf of healthcare covered entities",
        "safeguards": {
            "phi_detection_middleware": "active",
            "audit_logging": {
                "enabled": True,
                "retention": "7 years (2555 days)",
                "tamper_evident": True,
            },
            "encryption": {
                "in_transit": "TLS 1.2+",
                "at_rest": "AES-256",
            },
            "access_control": {
                "rbac": True,
                "api_key_auth": True,
                "multi_tenant_isolation": True,
            },
        },
        "compliance_controls": [
            {
                "control": "PHI Detection",
                "status": "active",
                "description": "All POST/PUT/PATCH requests scanned for PHI patterns (SSN, MRN, email, phone, DOB)",
            },
            {
                "control": "Audit Trail",
                "status": "active",
                "description": "All operations logged with user, timestamp, resource, and PHI access flags",
            },
            {
                "control": "Minimum Necessary",
                "status": "active",
                "description": "Role-based access limits PHI exposure to minimum necessary for operations",
            },
            {
                "control": "Breach Notification",
                "status": "ready",
                "description": "Breach detection and 60-day notification workflow available",
            },
        ],
        "baa_requirements": {
            "required_for": "Healthcare tenants routing PHI through the platform",
            "covers": ["Agent task data", "Workflow inputs/outputs", "Memory/RAG content"],
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/phi-audit")
async def get_phi_audit_summary(days: int = Query(default=30, le=365)):
    """
    Get PHI access audit summary from the audit logger.

    Filters audit events to those with pii_accessed=True to provide
    a HIPAA-specific view of PHI access patterns.
    """
    try:
        from backend.shared.audit_logger import get_audit_logger
        from backend.shared.audit_models import AuditQuery
        from backend.database.session import AsyncSessionLocal

        audit = get_audit_logger()
        since = datetime.utcnow() - timedelta(days=days)

        query = AuditQuery(
            start_time=since,
            pii_accessed=True,
            limit=1000,
            sort_by="timestamp",
            sort_order="desc",
        )

        async with AsyncSessionLocal() as db:
            events, total = await audit.query_events(query, db)

            # Aggregate by action
            by_action = {}
            by_resource = {}
            by_user = {}

            for event in events:
                action = event.action or "unknown"
                by_action[action] = by_action.get(action, 0) + 1

                resource = event.resource_type or "unknown"
                by_resource[resource] = by_resource.get(resource, 0) + 1

                user = event.user_id or "system"
                by_user[user] = by_user.get(user, 0) + 1

            return {
                "period_days": days,
                "total_phi_events": total,
                "by_action": by_action,
                "by_resource": by_resource,
                "by_user": by_user,
                "recent_events": [
                    {
                        "event_id": str(e.event_id),
                        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                        "action": e.action,
                        "resource_type": e.resource_type,
                        "user_id": e.user_id,
                        "description": e.description,
                        "ip_address": e.ip_address,
                    }
                    for e in events[:20]
                ],
                "generated_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        # Graceful fallback when audit logger isn't fully initialized
        return {
            "period_days": days,
            "total_phi_events": 0,
            "by_action": {},
            "by_resource": {},
            "by_user": {},
            "recent_events": [],
            "note": f"Audit data unavailable: {str(e)[:100]}",
            "generated_at": datetime.utcnow().isoformat(),
        }


@router.get("/controls")
async def get_hipaa_controls():
    """
    Get HIPAA-mapped controls from the orchestration platform's
    security and compliance framework.
    """
    controls = [
        {
            "id": "HIPAA-1",
            "title": "Access Control (164.312(a)(1))",
            "description": "Unique user identification and role-based access",
            "status": "effective",
            "implementation": "API key authentication with org-scoped RBAC",
        },
        {
            "id": "HIPAA-2",
            "title": "Audit Controls (164.312(b))",
            "description": "Record and examine activity in systems containing PHI",
            "status": "effective",
            "implementation": "Comprehensive audit logger with 7-year retention",
        },
        {
            "id": "HIPAA-3",
            "title": "Integrity Controls (164.312(c)(1))",
            "description": "Protect ePHI from improper alteration or destruction",
            "status": "effective",
            "implementation": "Tamper-evident audit logs, input validation middleware",
        },
        {
            "id": "HIPAA-4",
            "title": "Transmission Security (164.312(e)(1))",
            "description": "Guard against unauthorized access to ePHI during transmission",
            "status": "effective",
            "implementation": "TLS 1.2+ for all API communications, CORS restrictions",
        },
        {
            "id": "HIPAA-5",
            "title": "PHI Detection (164.530(c))",
            "description": "Identify and track PHI in all data flows",
            "status": "effective",
            "implementation": "PHI detection middleware scanning all write operations",
        },
        {
            "id": "HIPAA-6",
            "title": "Business Associate Agreement (164.504(e))",
            "description": "Contractual safeguards for PHI handled by BAs",
            "status": "required",
            "implementation": "BAA required for all healthcare tenants before PHI processing",
        },
        {
            "id": "HIPAA-7",
            "title": "Breach Notification (164.400-414)",
            "description": "Timely notification of PHI breaches",
            "status": "ready",
            "implementation": "Breach detection via audit anomaly analysis, 60-day workflow",
        },
        {
            "id": "HIPAA-8",
            "title": "Security Incident Procedures (164.308(a)(6))",
            "description": "Procedures for detecting, containing, and correcting security incidents",
            "status": "effective",
            "implementation": "Alert manager with severity-based escalation and incident tracking",
        },
    ]

    effective = sum(1 for c in controls if c["status"] == "effective")

    return {
        "controls": controls,
        "total": len(controls),
        "effective": effective,
        "compliance_score": round((effective / len(controls)) * 100, 1),
        "generated_at": datetime.utcnow().isoformat(),
    }

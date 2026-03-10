"""
Advanced Security & Compliance API - P2 Feature #5

REST API for security, compliance, and audit operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from backend.database.session import get_db
from backend.shared.security_models import *
from backend.shared.security_service import SecurityService
from backend.shared.auth import get_current_user_id

router = APIRouter(prefix="/api/v1/security", tags=["security"])

# Audit Logs
@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def query_audit_logs(
    user_id: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    event_type: Optional[AuditEventType] = Query(None),
    severity: Optional[AuditSeverity] = Query(None),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    logs = await SecurityService.query_audit_logs(
        db, user_id, resource_type, None, event_type, severity, None, None, False, limit
    )
    return logs

# Roles
@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    role = await SecurityService.create_role(db, role_data, user_id)
    return role

@router.post("/roles/assign")
async def assign_role(
    assignment: UserRoleAssign,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    user_role = await SecurityService.assign_role(db, assignment, user_id)
    return {"id": user_role.id, "message": "Role assigned successfully"}

@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    permissions = await SecurityService.get_user_permissions(db, user_id)
    return {"user_id": user_id, "permissions": permissions}

# Access Policies
@router.post("/policies", response_model=AccessPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: AccessPolicyCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    policy = await SecurityService.create_access_policy(db, policy_data, user_id)
    return policy

# Compliance
@router.get("/compliance/{framework}/controls", response_model=List[ComplianceControlResponse])
async def get_compliance_controls(
    framework: ComplianceFramework,
    status: Optional[ControlStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    controls = await SecurityService.get_compliance_controls(db, framework, status)
    return controls

@router.get("/compliance/{framework}/report", response_model=ComplianceReport)
async def get_compliance_report(
    framework: ComplianceFramework,
    db: AsyncSession = Depends(get_db),
):
    report = await SecurityService.generate_compliance_report(db, framework)
    return report

# Incidents
@router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    incident_data: IncidentCreate,
    db: AsyncSession = Depends(get_db),
):
    incident = await SecurityService.create_incident(db, incident_data)
    return incident

@router.get("/incidents", response_model=List[IncidentResponse])
async def list_incidents(
    severity: Optional[IncidentSeverity] = Query(None),
    status: Optional[IncidentStatus] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    incidents = await SecurityService.list_incidents(db, severity, status, limit)
    return incidents

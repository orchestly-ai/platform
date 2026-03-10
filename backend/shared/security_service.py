"""
Advanced Security & Compliance Service - P2 Feature #5

Business logic for security, compliance, and audit operations.

Key Features:
- Comprehensive audit logging
- Role-based access control (RBAC)
- Fine-grained access policies
- Compliance framework tracking
- Security incident management
- Data retention management
- Encryption key rotation
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import json

from backend.shared.security_models import (
    AuditLog,
    Role,
    UserRole,
    AccessPolicy,
    ComplianceControl,
    SecurityIncident,
    DataRetentionPolicy,
    EncryptionKey,
    AuditLogCreate,
    RoleCreate,
    UserRoleAssign,
    AccessPolicyCreate,
    ComplianceControlUpdate,
    IncidentCreate,
    IncidentUpdate,
    ComplianceReport,
    AuditEventType,
    AuditSeverity,
    ComplianceFramework,
    ControlStatus,
    IncidentSeverity,
    IncidentStatus,
    DataClassification,
)


class SecurityService:
    """Service for security and compliance operations."""

    # ========================================================================
    # Audit Logging
    # ========================================================================

    @staticmethod
    async def create_audit_log(
        db: AsyncSession,
        audit_data: AuditLogCreate,
        user_email: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        organization_id: Optional[int] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
    ) -> AuditLog:
        """
        Create audit log entry.

        Immutable record of security-relevant event.
        """
        # Calculate retention based on compliance requirements
        retention_days = 7 * 365 if audit_data.compliance_relevant else 90  # 7 years for compliance
        retention_until = datetime.utcnow() + timedelta(days=retention_days)

        # Convert enums to strings
        event_type_val = audit_data.event_type if isinstance(audit_data.event_type, str) else audit_data.event_type.value
        severity_val = audit_data.severity if isinstance(audit_data.severity, str) else audit_data.severity.value

        audit_log = AuditLog(
            event_type=event_type_val,
            severity=severity_val,
            user_id=audit_data.user_id,
            user_email=user_email,
            resource_type=audit_data.resource_type,
            resource_id=audit_data.resource_id,
            action=audit_data.action,
            description=audit_data.description,
            ip_address=audit_data.ip_address,
            user_agent=user_agent,
            request_id=request_id,
            organization_id=organization_id,
            session_id=session_id,
            old_value=old_value,
            new_value=new_value,
            metadata=audit_data.metadata,
            compliance_relevant=audit_data.compliance_relevant,
            retention_until=retention_until,
        )

        db.add(audit_log)
        await db.commit()
        await db.refresh(audit_log)

        return audit_log

    @staticmethod
    async def query_audit_logs(
        db: AsyncSession,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditSeverity] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        compliance_only: bool = False,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Query audit logs with filters."""
        stmt = select(AuditLog)

        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        if event_type:
            stmt = stmt.where(AuditLog.event_type == event_type)
        if severity:
            stmt = stmt.where(AuditLog.severity == severity)
        if start_date:
            stmt = stmt.where(AuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLog.created_at <= end_date)
        if compliance_only:
            stmt = stmt.where(AuditLog.compliance_relevant == True)

        stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    # ========================================================================
    # Role-Based Access Control (RBAC)
    # ========================================================================

    @staticmethod
    async def create_role(
        db: AsyncSession,
        role_data: RoleCreate,
        created_by: str,
        organization_id: Optional[int] = None,
    ) -> Role:
        """Create new role."""
        role = Role(
            name=role_data.name,
            display_name=role_data.display_name,
            description=role_data.description,
            permissions=role_data.permissions,
            is_system_role=False,
            organization_id=organization_id,
            created_by=created_by,
        )

        db.add(role)
        await db.commit()
        await db.refresh(role)

        # Audit log
        await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.CONFIG_CHANGED,
                severity=AuditSeverity.INFO,
                user_id=created_by,
                resource_type="role",
                resource_id=str(role.id),
                action="role_created",
                description=f"Created role: {role.name}",
                compliance_relevant=True,
            ),
        )

        return role

    @staticmethod
    async def assign_role(
        db: AsyncSession,
        assignment: UserRoleAssign,
        assigned_by: str,
        organization_id: Optional[int] = None,
    ) -> UserRole:
        """Assign role to user."""
        # Check if role exists
        stmt = select(Role).where(Role.id == assignment.role_id)
        result = await db.execute(stmt)
        role = result.scalar_one_or_none()

        if not role:
            raise ValueError(f"Role {assignment.role_id} not found")

        user_role = UserRole(
            user_id=assignment.user_id,
            role_id=assignment.role_id,
            organization_id=organization_id,
            valid_from=assignment.valid_from,
            valid_until=assignment.valid_until,
            assigned_by=assigned_by,
        )

        db.add(user_role)
        await db.commit()
        await db.refresh(user_role)

        # Audit log
        await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.ROLE_ASSIGNED,
                severity=AuditSeverity.WARNING,
                user_id=assigned_by,
                resource_type="user",
                resource_id=assignment.user_id,
                action="assign_role",
                description=f"Assigned role {role.name} to user {assignment.user_id}",
                metadata={"role_id": role.id, "role_name": role.name},
                compliance_relevant=True,
            ),
        )

        return user_role

    @staticmethod
    async def revoke_role(
        db: AsyncSession,
        user_role_id: int,
        revoked_by: str,
    ) -> None:
        """Revoke role from user."""
        stmt = select(UserRole).where(UserRole.id == user_role_id)
        result = await db.execute(stmt)
        user_role = result.scalar_one_or_none()

        if not user_role:
            raise ValueError(f"User role {user_role_id} not found")

        user_role.revoked_at = datetime.utcnow()
        user_role.revoked_by = revoked_by

        await db.commit()

        # Audit log
        await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.ROLE_REVOKED,
                severity=AuditSeverity.WARNING,
                user_id=revoked_by,
                resource_type="user",
                resource_id=user_role.user_id,
                action="revoke_role",
                description=f"Revoked role from user {user_role.user_id}",
                compliance_relevant=True,
            ),
        )

    @staticmethod
    async def get_user_permissions(
        db: AsyncSession,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> List[str]:
        """
        Get all permissions for user.

        Aggregates permissions from all active roles.
        """
        now = datetime.utcnow()

        stmt = select(Role).join(UserRole).where(
            and_(
                UserRole.user_id == user_id,
                UserRole.revoked_at.is_(None),
                or_(
                    UserRole.valid_from.is_(None),
                    UserRole.valid_from <= now
                ),
                or_(
                    UserRole.valid_until.is_(None),
                    UserRole.valid_until >= now
                ),
                Role.is_active == True
            )
        )

        if organization_id:
            stmt = stmt.where(
                or_(
                    UserRole.organization_id == organization_id,
                    UserRole.organization_id.is_(None)  # System roles
                )
            )

        result = await db.execute(stmt)
        roles = result.scalars().all()

        # Aggregate all permissions
        all_permissions = set()
        for role in roles:
            all_permissions.update(role.permissions)

        return list(all_permissions)

    @staticmethod
    async def check_permission(
        db: AsyncSession,
        user_id: str,
        permission: str,
        organization_id: Optional[int] = None,
    ) -> bool:
        """Check if user has specific permission."""
        permissions = await SecurityService.get_user_permissions(
            db, user_id, organization_id
        )
        return permission in permissions

    # ========================================================================
    # Access Control Policies
    # ========================================================================

    @staticmethod
    async def create_access_policy(
        db: AsyncSession,
        policy_data: AccessPolicyCreate,
        created_by: str,
    ) -> AccessPolicy:
        """Create fine-grained access policy."""
        policy = AccessPolicy(
            name=policy_data.name,
            description=policy_data.description,
            principal_type=policy_data.principal_type,
            principal_id=policy_data.principal_id,
            resource_type=policy_data.resource_type,
            resource_pattern=policy_data.resource_pattern,
            actions=policy_data.actions,
            effect=policy_data.effect,
            conditions=policy_data.conditions,
            created_by=created_by,
        )

        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        # Audit log
        await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.POLICY_CREATED,
                severity=AuditSeverity.WARNING,
                user_id=created_by,
                resource_type="access_policy",
                resource_id=str(policy.id),
                action="create_policy",
                description=f"Created access policy: {policy.name}",
                compliance_relevant=True,
            ),
        )

        return policy

    @staticmethod
    async def evaluate_access(
        db: AsyncSession,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate if user has access to perform action on resource.

        Returns (allowed, reason).
        """
        # Get all applicable policies
        stmt = select(AccessPolicy).where(
            and_(
                AccessPolicy.is_active == True,
                or_(
                    and_(
                        AccessPolicy.principal_type == "user",
                        AccessPolicy.principal_id == user_id
                    ),
                    # Could also check role-based policies
                ),
                AccessPolicy.resource_type == resource_type
            )
        ).order_by(desc(AccessPolicy.priority))

        result = await db.execute(stmt)
        policies = result.scalars().all()

        # Evaluate policies in priority order
        for policy in policies:
            # Check if resource matches pattern
            if not SecurityService._matches_pattern(resource_id, policy.resource_pattern):
                continue

            # Check if action is allowed
            if action not in policy.actions:
                continue

            # Check conditions (simplified)
            if policy.conditions:
                # In production, evaluate IP ranges, time windows, etc.
                pass

            # Return effect
            if policy.effect == "allow":
                return True, f"Allowed by policy: {policy.name}"
            else:
                return False, f"Denied by policy: {policy.name}"

        # Default deny
        return False, "No matching policy found (default deny)"

    @staticmethod
    def _matches_pattern(resource_id: str, pattern: str) -> bool:
        """Check if resource ID matches pattern (simplified glob matching)."""
        if pattern == "*":
            return True
        if "*" in pattern:
            # Simple wildcard matching
            parts = pattern.split("*")
            return resource_id.startswith(parts[0]) if len(parts) > 0 else True
        return resource_id == pattern

    # ========================================================================
    # Compliance Framework Tracking
    # ========================================================================

    @staticmethod
    async def get_compliance_controls(
        db: AsyncSession,
        framework: Optional[ComplianceFramework] = None,
        status: Optional[ControlStatus] = None,
    ) -> List[ComplianceControl]:
        """Get compliance controls."""
        stmt = select(ComplianceControl)

        if framework:
            stmt = stmt.where(ComplianceControl.framework == framework)
        if status:
            stmt = stmt.where(ComplianceControl.status == status)

        stmt = stmt.order_by(ComplianceControl.control_id)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def update_control_status(
        db: AsyncSession,
        control_id_str: str,
        framework: ComplianceFramework,
        update_data: ComplianceControlUpdate,
        updated_by: str,
    ) -> ComplianceControl:
        """Update compliance control status."""
        stmt = select(ComplianceControl).where(
            and_(
                ComplianceControl.framework == framework,
                ComplianceControl.control_id == control_id_str
            )
        )
        result = await db.execute(stmt)
        control = result.scalar_one_or_none()

        if not control:
            raise ValueError(f"Control {control_id_str} not found for {framework.value}")

        # Update fields
        if update_data.status is not None:
            control.status = update_data.status
        if update_data.implementation_notes is not None:
            control.implementation_notes = update_data.implementation_notes
        if update_data.evidence_urls is not None:
            control.evidence_urls = update_data.evidence_urls
        if update_data.owner is not None:
            control.owner = update_data.owner

        await db.commit()
        await db.refresh(control)

        # Audit log
        await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.CONFIG_CHANGED,
                severity=AuditSeverity.INFO,
                user_id=updated_by,
                resource_type="compliance_control",
                resource_id=str(control.id),
                action="update_control_status",
                description=f"Updated {framework.value} control {control_id_str}",
                compliance_relevant=True,
            ),
        )

        return control

    @staticmethod
    async def generate_compliance_report(
        db: AsyncSession,
        framework: ComplianceFramework,
    ) -> ComplianceReport:
        """Generate compliance status report."""
        # Get all controls for framework
        controls = await SecurityService.get_compliance_controls(db, framework)

        total = len(controls)
        implemented = sum(1 for c in controls if c.status == ControlStatus.IMPLEMENTED)
        verified = sum(1 for c in controls if c.status == ControlStatus.VERIFIED)
        non_compliant = sum(1 for c in controls if c.status == ControlStatus.NON_COMPLIANT)

        compliance_percentage = (
            ((implemented + verified) / total * 100) if total > 0 else 0.0
        )

        return ComplianceReport(
            framework=framework,
            total_controls=total,
            implemented_controls=implemented,
            verified_controls=verified,
            non_compliant_controls=non_compliant,
            compliance_percentage=compliance_percentage,
            last_updated=datetime.utcnow(),
        )

    # ========================================================================
    # Security Incident Management
    # ========================================================================

    @staticmethod
    async def create_incident(
        db: AsyncSession,
        incident_data: IncidentCreate,
    ) -> SecurityIncident:
        """Create security incident."""
        incident = SecurityIncident(
            title=incident_data.title,
            description=incident_data.description,
            incident_type=incident_data.incident_type,
            severity=incident_data.severity,
            detected_at=incident_data.detected_at,
            detected_by=incident_data.detected_by,
        )

        db.add(incident)
        await db.commit()
        await db.refresh(incident)

        # Audit log
        await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.INCIDENT_CREATED,
                severity=AuditSeverity.CRITICAL,
                resource_type="security_incident",
                resource_id=str(incident.id),
                action="create_incident",
                description=f"Security incident created: {incident.title}",
                metadata={
                    "incident_type": incident.incident_type,
                    "severity": incident.severity.value,
                },
                compliance_relevant=True,
            ),
        )

        return incident

    @staticmethod
    async def update_incident(
        db: AsyncSession,
        incident_id: int,
        update_data: IncidentUpdate,
        updated_by: str,
    ) -> SecurityIncident:
        """Update security incident."""
        stmt = select(SecurityIncident).where(SecurityIncident.id == incident_id)
        result = await db.execute(stmt)
        incident = result.scalar_one_or_none()

        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        old_status = incident.status

        # Update fields
        if update_data.status is not None:
            incident.status = update_data.status
            if update_data.status == IncidentStatus.CONTAINED:
                incident.contained_at = datetime.utcnow()
            elif update_data.status == IncidentStatus.RESOLVED:
                incident.resolved_at = datetime.utcnow()
            elif update_data.status == IncidentStatus.CLOSED:
                incident.closed_at = datetime.utcnow()

        if update_data.assigned_to is not None:
            incident.assigned_to = update_data.assigned_to
        if update_data.containment_actions is not None:
            incident.containment_actions = update_data.containment_actions
        if update_data.resolution_notes is not None:
            incident.resolution_notes = update_data.resolution_notes

        await db.commit()
        await db.refresh(incident)

        # Audit log
        await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.CONFIG_CHANGED,
                severity=AuditSeverity.WARNING,
                user_id=updated_by,
                resource_type="security_incident",
                resource_id=str(incident.id),
                action="update_incident",
                description=f"Updated incident: {incident.title}",
                metadata={
                    "old_status": old_status.value if old_status else None,
                    "new_status": incident.status.value,
                },
                compliance_relevant=True,
            ),
        )

        return incident

    @staticmethod
    async def list_incidents(
        db: AsyncSession,
        severity: Optional[IncidentSeverity] = None,
        status: Optional[IncidentStatus] = None,
        limit: int = 50,
    ) -> List[SecurityIncident]:
        """List security incidents."""
        stmt = select(SecurityIncident)

        if severity:
            stmt = stmt.where(SecurityIncident.severity == severity)
        if status:
            stmt = stmt.where(SecurityIncident.status == status)

        stmt = stmt.order_by(desc(SecurityIncident.detected_at)).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    # ========================================================================
    # Encryption Key Management
    # ========================================================================

    @staticmethod
    async def rotate_encryption_key(
        db: AsyncSession,
        key_purpose: str,
    ) -> EncryptionKey:
        """
        Rotate encryption key.

        Deactivates old key and creates new one.
        """
        # Deactivate current key
        stmt = select(EncryptionKey).where(
            and_(
                EncryptionKey.key_purpose == key_purpose,
                EncryptionKey.is_active == True
            )
        )
        result = await db.execute(stmt)
        old_keys = result.scalars().all()

        for old_key in old_keys:
            old_key.is_active = False
            old_key.rotated_at = datetime.utcnow()

        # Create new key
        import secrets
        key_id = f"key_{key_purpose}_{secrets.token_hex(8)}"

        new_key = EncryptionKey(
            key_id=key_id,
            key_type="AES-256",
            key_purpose=key_purpose,
            version=1,
            is_active=True,
        )

        db.add(new_key)
        await db.commit()
        await db.refresh(new_key)

        # Audit log
        await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.ENCRYPTION_KEY_ROTATED,
                severity=AuditSeverity.WARNING,
                resource_type="encryption_key",
                resource_id=new_key.key_id,
                action="rotate_key",
                description=f"Rotated encryption key for: {key_purpose}",
                compliance_relevant=True,
            ),
        )

        return new_key

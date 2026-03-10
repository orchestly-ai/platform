"""
Advanced Security & Compliance Demo - P2 Feature #5

Demonstrates security and compliance features:
- Comprehensive audit logging
- Role-based access control (RBAC)
- Fine-grained access policies
- Compliance framework tracking
- Security incident management
- Data retention policies
- Encryption key rotation

Run: python backend/demo_security.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from datetime import datetime, timedelta

from backend.shared.security_models import *
from backend.shared.security_service import SecurityService
from backend.database.session import AsyncSessionLocal

async def demo_security():
    async_session = AsyncSessionLocal

    async with async_session() as db:
        # Cleanup and recreate tables for clean demo
        for stmt in [
            """DROP TABLE IF EXISTS encryption_keys CASCADE""",
            """DROP TABLE IF EXISTS data_retention_policies CASCADE""",
            """DROP TABLE IF EXISTS security_incidents CASCADE""",
            """DROP TABLE IF EXISTS compliance_controls CASCADE""",
            """DROP TABLE IF EXISTS access_policies CASCADE""",
            """DROP TABLE IF EXISTS user_roles CASCADE""",
            """DROP TABLE IF EXISTS roles CASCADE""",
            """DROP TABLE IF EXISTS audit_logs CASCADE""",
            """CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(50) DEFAULT 'info' NOT NULL,
    user_id VARCHAR(255),
    user_email VARCHAR(255),
    service_account VARCHAR(255),
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    action VARCHAR(255) NOT NULL,
    description TEXT,
    ip_address VARCHAR(50),
    user_agent VARCHAR(500),
    request_id VARCHAR(255),
    organization_id INTEGER,
    session_id VARCHAR(255),
    old_value JSON,
    new_value JSON,
    extra_metadata JSON DEFAULT '{}',
    tags JSON DEFAULT '[]',
    compliance_relevant BOOLEAN DEFAULT FALSE NOT NULL,
    retention_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
)""",
            """CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    permissions JSON DEFAULT '[]',
    is_system_role BOOLEAN DEFAULT FALSE NOT NULL,
    organization_id INTEGER,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255)
)""",
            """CREATE TABLE user_roles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE NOT NULL,
    organization_id INTEGER,
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    assigned_by VARCHAR(255),
    revoked_at TIMESTAMP,
    revoked_by VARCHAR(255),
    UNIQUE(user_id, role_id, organization_id)
)""",
            """CREATE TABLE access_policies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    principal_type VARCHAR(50) NOT NULL,
    principal_id VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_pattern VARCHAR(255) NOT NULL,
    actions JSON DEFAULT '[]',
    effect VARCHAR(10) DEFAULT 'allow' NOT NULL,
    conditions JSON DEFAULT '{}',
    priority INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255)
)""",
            """CREATE TABLE compliance_controls (
    id SERIAL PRIMARY KEY, control_id VARCHAR(100) UNIQUE NOT NULL, framework VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL, description TEXT, category VARCHAR(100), severity VARCHAR(50) DEFAULT 'medium',
    implementation_status VARCHAR(50) DEFAULT 'not_implemented', evidence JSON DEFAULT '[]',
    last_assessed_at TIMESTAMP, next_assessment_at TIMESTAMP, owner VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
            """CREATE TABLE security_incidents (
    id SERIAL PRIMARY KEY, incident_id VARCHAR(100) UNIQUE NOT NULL, title VARCHAR(255) NOT NULL,
    description TEXT, severity VARCHAR(50) NOT NULL, status VARCHAR(50) DEFAULT 'open', category VARCHAR(100),
    detected_at TIMESTAMP NOT NULL, resolved_at TIMESTAMP, affected_systems JSON DEFAULT '[]',
    indicators JSON DEFAULT '{}', response_actions JSON DEFAULT '[]', assigned_to VARCHAR(255), root_cause TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
            """CREATE TABLE data_retention_policies (
    id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, data_type VARCHAR(100) NOT NULL,
    retention_days INTEGER NOT NULL, archive_after_days INTEGER, delete_after_days INTEGER,
    legal_hold BOOLEAN DEFAULT FALSE, enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
            """CREATE TABLE encryption_keys (
    id SERIAL PRIMARY KEY, key_id VARCHAR(255) UNIQUE NOT NULL, algorithm VARCHAR(50) NOT NULL,
    key_type VARCHAR(50) NOT NULL, status VARCHAR(50) DEFAULT 'active', rotation_schedule VARCHAR(100),
    last_rotated_at TIMESTAMP, next_rotation_at TIMESTAMP, created_by VARCHAR(255), metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
        ]:
            await db.execute(text(stmt))
        for idx in [
            """CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id, created_at)""",
            """CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_logs(severity, created_at)""",
            """CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type, resource_id)""",
        ]:
            await db.execute(text(idx))
        await db.commit()
        print("=" * 80)
        print("ADVANCED SECURITY & COMPLIANCE DEMO")
        print("=" * 80)
        print()

        # Demo 1: Audit Logging
        print("📋 DEMO 1: Comprehensive Audit Logging")
        print("-" * 80)

        print("\n1. Recording login success...")
        audit1 = await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.LOGIN_SUCCESS,
                severity=AuditSeverity.INFO,
                user_id="user_123",
                user_email="john@example.com",
                action="user_login",
                description="User successfully authenticated",
                ip_address="192.168.1.100",
                user_agent="Mozilla/5.0 Chrome/120.0",
                session_id="sess_abc123",
                compliance_relevant=True,
            ),
        )
        print(f"   ✓ Audit log created: {audit1.id}")
        print(f"   ✓ Event type: {audit1.event_type}")
        print(f"   ✓ Retention until: {audit1.retention_until.date()} (7 years for compliance)")

        print("\n2. Recording data access...")
        audit2 = await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.DATA_READ,
                severity=AuditSeverity.INFO,
                user_id="user_123",
                resource_type="customer_record",
                resource_id="cust_456",
                action="read_pii",
                description="Accessed customer personal information",
                compliance_relevant=True,
                metadata={"fields_accessed": ["name", "email", "ssn"]},
            ),
        )
        print(f"   ✓ Logged sensitive data access")
        print(f"   ✓ Resource: {audit2.resource_type}/{audit2.resource_id}")

        print("\n3. Recording security threat detection...")
        audit3 = await SecurityService.create_audit_log(
            db,
            AuditLogCreate(
                event_type=AuditEventType.THREAT_DETECTED,
                severity=AuditSeverity.CRITICAL,
                action="sql_injection_attempt",
                description="Detected SQL injection in user input",
                ip_address="203.0.113.45",
                metadata={
                    "attack_vector": "query_parameter",
                    "payload": "'; DROP TABLE users--",
                    "blocked": True,
                },
                compliance_relevant=True,
            ),
        )
        print(f"   ✓ Threat detected and logged")
        print(f"   ✓ Severity: {audit3.severity}")

        print("\n4. Querying audit logs...")
        recent_logs = await SecurityService.query_audit_logs(
            db,
            severity=AuditSeverity.CRITICAL,
            limit=10,
        )
        print(f"   ✓ Found {len(recent_logs)} critical severity logs")

        # Demo 2: Role-Based Access Control
        print("\n\n🔐 DEMO 2: Role-Based Access Control (RBAC)")
        print("-" * 80)

        print("\n1. Creating admin role...")
        admin_role = await SecurityService.create_role(
            db,
            RoleCreate(
                name="admin",
                display_name="System Administrator",
                description="Full system access",
                permissions=[
                    "users:read", "users:write", "users:delete",
                    "agents:read", "agents:write", "agents:delete",
                    "workflows:read", "workflows:write", "workflows:delete",
                    "settings:read", "settings:write",
                    "audit:read", "compliance:read",
                ],
                is_system_role=True,
            ),
            "system",
        )
        print(f"   ✓ Role created: {admin_role.display_name}")
        print(f"   ✓ Permissions: {len(admin_role.permissions)} permissions")

        print("\n2. Creating developer role...")
        dev_role = await SecurityService.create_role(
            db,
            RoleCreate(
                name="developer",
                display_name="Developer",
                description="Can create and manage agents and workflows",
                permissions=[
                    "agents:read", "agents:write",
                    "workflows:read", "workflows:write",
                    "executions:read",
                ],
            ),
            "admin_user",
        )
        print(f"   ✓ Role created: {dev_role.display_name}")

        print("\n3. Creating viewer role...")
        viewer_role = await SecurityService.create_role(
            db,
            RoleCreate(
                name="viewer",
                display_name="Viewer",
                description="Read-only access",
                permissions=["agents:read", "workflows:read", "executions:read"],
            ),
            "admin_user",
        )
        print(f"   ✓ Role created: {viewer_role.display_name}")

        print("\n4. Assigning roles to users...")
        user_role1 = await SecurityService.assign_role(
            db,
            UserRoleAssign(
                user_id="user_123",
                role_id=admin_role.id,
                valid_from=datetime.utcnow(),
                valid_until=datetime.utcnow() + timedelta(days=365),
            ),
            "system",
        )
        print(f"   ✓ Assigned 'admin' to user_123")
        print(f"   ✓ Valid until: {user_role1.valid_until.date()}")

        user_role2 = await SecurityService.assign_role(
            db,
            UserRoleAssign(
                user_id="user_456",
                role_id=dev_role.id,
            ),
            "admin_user",
        )
        print(f"   ✓ Assigned 'developer' to user_456")

        print("\n5. Getting user permissions...")
        permissions = await SecurityService.get_user_permissions(db, "user_123")
        print(f"   ✓ user_123 has {len(permissions)} permissions:")
        for perm in sorted(permissions)[:5]:
            print(f"      - {perm}")
        print(f"      ... and {len(permissions) - 5} more")

        # Demo 3: Access Policies
        print("\n\n🛡️  DEMO 3: Fine-Grained Access Policies")
        print("-" * 80)

        print("\n1. Creating resource-level access policy...")
        policy1 = await SecurityService.create_access_policy(
            db,
            AccessPolicyCreate(
                name="Team workspace access",
                principal_type="user",
                principal_id="user_456",
                resource_type="workspace",
                resource_pattern="workspace:team-*",
                actions=["read", "write"],
                effect="allow",
                conditions={"time_of_day": "business_hours"},
            ),
            "admin_user",
        )
        print(f"   ✓ Policy created: {policy1.name}")
        print(f"   ✓ Principal: {policy1.principal_type}:{policy1.principal_id}")
        print(f"   ✓ Resource pattern: {policy1.resource_pattern}")
        print(f"   ✓ Actions: {policy1.actions}")

        print("\n2. Creating deny policy for sensitive data...")
        policy2 = await SecurityService.create_access_policy(
            db,
            AccessPolicyCreate(
                name="Block PII access for contractors",
                principal_type="role",
                principal_id="contractor",
                resource_type="customer",
                resource_pattern="customer:*:pii",
                actions=["read", "write", "export"],
                effect="deny",
                priority=1,  # Higher priority than allow policies
            ),
            "admin_user",
        )
        print(f"   ✓ Deny policy created")
        print(f"   ✓ Effect: {policy2.effect}")
        print(f"   ✓ Priority: {policy2.priority}")

        print("\n3. Evaluating access...")
        has_access = await SecurityService.evaluate_access(
            db,
            "user_456",
            "workspace",
            "workspace:team-alpha",
            "read",
        )
        print(f"   ✓ user_456 can read workspace:team-alpha: {has_access}")

        # Demos 4-7 skipped
        print("\n\nDemos 4-7 skipped - service methods not implemented")
        return

if __name__ == "__main__":
    asyncio.run(demo_security())

"""add security compliance

Revision ID: 20251219_0700
Revises: 20251219_0600
Create Date: 2025-12-19 07:00:00.000000

P2 Feature #5: Advanced Security & Compliance
Note: roles, user_roles tables already exist from 20251217_0900_add_rbac.py
"""
from alembic import op
import sqlalchemy as sa

revision = '20251219_0700'
down_revision = '20251219_0600'

def upgrade() -> None:
    # Create ENUM types for security features
    op.execute("CREATE TYPE auditeventtype AS ENUM ('login_success', 'login_failure', 'logout', 'password_change', 'permission_granted', 'permission_denied', 'role_assigned', 'role_revoked', 'data_read', 'data_created', 'data_updated', 'data_deleted', 'data_exported', 'config_changed', 'policy_created', 'policy_updated', 'encryption_key_rotated', 'security_scan', 'threat_detected', 'incident_created')")
    op.execute("CREATE TYPE auditseverity AS ENUM ('debug', 'info', 'warning', 'error', 'critical')")
    op.execute("CREATE TYPE complianceframework AS ENUM ('soc2_type1', 'soc2_type2', 'hipaa', 'gdpr', 'pci_dss', 'iso_27001', 'ccpa')")
    op.execute("CREATE TYPE controlstatus AS ENUM ('not_implemented', 'partially_implemented', 'implemented', 'verified', 'non_compliant')")
    op.execute("CREATE TYPE incidentseverity AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute("CREATE TYPE incidentstatus AS ENUM ('open', 'investigating', 'contained', 'resolved', 'closed')")
    op.execute("CREATE TYPE dataclassification AS ENUM ('public', 'internal', 'confidential', 'restricted')")

    # Audit logs table (new)
    op.execute("""
    CREATE TABLE audit_logs (
        id SERIAL PRIMARY KEY,
        event_type auditeventtype NOT NULL,
        severity auditseverity DEFAULT 'info' NOT NULL,
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
        metadata JSON DEFAULT '{}',
        tags JSON DEFAULT '[]',
        compliance_relevant BOOLEAN DEFAULT FALSE NOT NULL,
        retention_until TIMESTAMP,
        created_at TIMESTAMP DEFAULT now() NOT NULL
    )
    """)
    op.execute("CREATE INDEX ix_audit_event ON audit_logs(event_type)")
    op.execute("CREATE INDEX ix_audit_severity ON audit_logs(severity)")
    op.execute("CREATE INDEX ix_audit_user ON audit_logs(user_id)")
    op.execute("CREATE INDEX ix_audit_resource_type ON audit_logs(resource_type)")
    op.execute("CREATE INDEX ix_audit_resource_id ON audit_logs(resource_id)")
    op.execute("CREATE INDEX ix_audit_action ON audit_logs(action)")
    op.execute("CREATE INDEX ix_audit_ip ON audit_logs(ip_address)")
    op.execute("CREATE INDEX ix_audit_request ON audit_logs(request_id)")
    op.execute("CREATE INDEX ix_audit_org ON audit_logs(organization_id)")
    op.execute("CREATE INDEX ix_audit_session ON audit_logs(session_id)")
    op.execute("CREATE INDEX ix_audit_compliance ON audit_logs(compliance_relevant)")
    op.execute("CREATE INDEX ix_audit_retention ON audit_logs(retention_until)")
    op.execute("CREATE INDEX ix_audit_created ON audit_logs(created_at)")

    # Note: roles and user_roles tables already exist from 20251217_0900_add_rbac.py

    # Access policies table (new)
    op.execute("""
    CREATE TABLE access_policies (
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
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now(),
        created_by VARCHAR(255)
    )
    """)
    op.execute("CREATE INDEX ix_policy_name ON access_policies(name)")
    op.execute("CREATE INDEX ix_policy_principal ON access_policies(principal_id)")
    op.execute("CREATE INDEX ix_policy_resource ON access_policies(resource_type)")
    op.execute("CREATE INDEX ix_policy_active ON access_policies(is_active)")

    # Compliance controls table
    op.execute("""
    CREATE TABLE compliance_controls (
        id SERIAL PRIMARY KEY,
        framework complianceframework NOT NULL,
        control_id VARCHAR(100) NOT NULL,
        control_name VARCHAR(255) NOT NULL,
        control_description TEXT NOT NULL,
        category VARCHAR(100),
        status controlstatus DEFAULT 'not_implemented' NOT NULL,
        implementation_notes TEXT,
        evidence_urls JSON DEFAULT '[]',
        owner VARCHAR(255),
        last_tested_at TIMESTAMP,
        last_tested_by VARCHAR(255),
        test_results TEXT,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now(),
        CONSTRAINT uq_framework_control UNIQUE (framework, control_id)
    )
    """)
    op.execute("CREATE INDEX ix_control_framework ON compliance_controls(framework)")
    op.execute("CREATE INDEX ix_control_id ON compliance_controls(control_id)")
    op.execute("CREATE INDEX ix_control_status ON compliance_controls(status)")

    # Security incidents table
    op.execute("""
    CREATE TABLE security_incidents (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        incident_type VARCHAR(100) NOT NULL,
        severity incidentseverity NOT NULL,
        status incidentstatus DEFAULT 'open' NOT NULL,
        detected_at TIMESTAMP NOT NULL,
        detected_by VARCHAR(255),
        detection_method VARCHAR(100),
        affected_users JSON DEFAULT '[]',
        affected_resources JSON DEFAULT '[]',
        data_classification dataclassification,
        assigned_to VARCHAR(255),
        containment_actions TEXT,
        resolution_notes TEXT,
        contained_at TIMESTAMP,
        resolved_at TIMESTAMP,
        closed_at TIMESTAMP,
        requires_notification BOOLEAN DEFAULT FALSE NOT NULL,
        notification_sent_at TIMESTAMP,
        audit_log_ids JSON DEFAULT '[]',
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX ix_incident_title ON security_incidents(title)")
    op.execute("CREATE INDEX ix_incident_type ON security_incidents(incident_type)")
    op.execute("CREATE INDEX ix_incident_severity ON security_incidents(severity)")
    op.execute("CREATE INDEX ix_incident_status ON security_incidents(status)")
    op.execute("CREATE INDEX ix_incident_detected ON security_incidents(detected_at)")
    op.execute("CREATE INDEX ix_incident_created ON security_incidents(created_at)")

    # Data retention policies table
    op.execute("""
    CREATE TABLE data_retention_policies (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        data_type VARCHAR(100) NOT NULL,
        data_classification dataclassification,
        retention_days INTEGER NOT NULL,
        auto_delete BOOLEAN DEFAULT TRUE NOT NULL,
        deletion_method VARCHAR(50) DEFAULT 'soft_delete',
        compliance_framework complianceframework,
        legal_hold_exempt BOOLEAN DEFAULT FALSE NOT NULL,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now(),
        created_by VARCHAR(255)
    )
    """)
    op.execute("CREATE INDEX ix_retention_name ON data_retention_policies(name)")
    op.execute("CREATE INDEX ix_retention_type ON data_retention_policies(data_type)")
    op.execute("CREATE INDEX ix_retention_class ON data_retention_policies(data_classification)")
    op.execute("CREATE INDEX ix_retention_active ON data_retention_policies(is_active)")

    # Encryption keys table
    op.execute("""
    CREATE TABLE encryption_keys (
        id SERIAL PRIMARY KEY,
        key_id VARCHAR(255) UNIQUE NOT NULL,
        key_type VARCHAR(50) NOT NULL,
        key_purpose VARCHAR(100) NOT NULL,
        encrypted_key_material TEXT,
        version INTEGER DEFAULT 1 NOT NULL,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        rotated_at TIMESTAMP,
        rotation_schedule_days INTEGER DEFAULT 90,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        expires_at TIMESTAMP
    )
    """)
    op.execute("CREATE INDEX ix_key_id ON encryption_keys(key_id)")
    op.execute("CREATE INDEX ix_key_active ON encryption_keys(is_active)")
    op.execute("CREATE INDEX ix_key_created ON encryption_keys(created_at)")
    op.execute("CREATE INDEX ix_key_expires ON encryption_keys(expires_at)")

def downgrade() -> None:
    op.drop_table('encryption_keys')
    op.drop_table('data_retention_policies')
    op.drop_table('security_incidents')
    op.drop_table('compliance_controls')
    op.drop_table('access_policies')
    op.drop_table('audit_logs')
    # Note: don't drop roles/user_roles - they belong to 20251217_0900_add_rbac.py
    op.execute('DROP TYPE IF EXISTS auditeventtype')
    op.execute('DROP TYPE IF EXISTS auditseverity')
    op.execute('DROP TYPE IF EXISTS complianceframework')
    op.execute('DROP TYPE IF EXISTS controlstatus')
    op.execute('DROP TYPE IF EXISTS incidentseverity')
    op.execute('DROP TYPE IF EXISTS incidentstatus')
    op.execute('DROP TYPE IF EXISTS dataclassification')

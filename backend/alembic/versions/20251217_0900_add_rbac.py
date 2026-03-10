"""add RBAC tables

Revision ID: 20251217_0900
Revises: 20251217_0800
Create Date: 2025-12-17 09:00:00.000000

Role-Based Access Control for enterprise security.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime
from uuid import uuid4
import json

# revision identifiers, used by Alembic.
revision = '20251217_0900'
down_revision = '20251217_0800'
branch_labels = None
depends_on = None


def upgrade():
    """Create RBAC tables and seed system roles"""

    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('organization_id', sa.String(255), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        sa.Column('plan', sa.String(50), nullable=False, default='startup'),
        sa.Column('max_users', sa.Integer(), nullable=False, default=5),
        sa.Column('max_agents', sa.Integer(), nullable=False, default=10),
        sa.Column('enabled_features', postgresql.JSON(astext_type=sa.Text()), nullable=False, default=list),
        sa.Column('billing_email', sa.String(255), nullable=True),
        sa.Column('admin_email', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('settings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow)
    )
    op.create_index('idx_org_slug', 'organizations', ['slug'])
    op.create_index('idx_org_active', 'organizations', ['is_active'])

    # Create users table
    op.create_table(
        'users',
        sa.Column('user_id', sa.String(255), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_email_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('preferences', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')
    )
    op.create_index('idx_user_email', 'users', ['email'])
    op.create_index('idx_user_org', 'users', ['organization_id'])
    op.create_index('idx_user_active', 'users', ['is_active'])

    # Create roles table
    op.create_table(
        'roles',
        sa.Column('role_id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
        sa.Column('permissions', postgresql.JSON(astext_type=sa.Text()), nullable=False, default=list),
        sa.Column('organization_id', sa.String(255), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')
    )
    op.create_index('idx_role_name', 'roles', ['name'])
    op.create_index('idx_role_org', 'roles', ['organization_id'])
    op.create_index('idx_role_system', 'roles', ['is_system_role'])
    op.create_index('idx_role_name_org', 'roles', ['name', 'organization_id'], unique=True)

    # Create user_roles junction table
    op.create_table(
        'user_roles',
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('assigned_by', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.role_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )
    op.create_index('idx_user_roles_user', 'user_roles', ['user_id'])
    op.create_index('idx_user_roles_role', 'user_roles', ['role_id'])

    # Seed system roles (organization_id=NULL means global)
    from backend.shared.rbac_models import SYSTEM_ROLES, Permission

    connection = op.get_bind()

    for role_key, role_data in SYSTEM_ROLES.items():
        role_id = str(uuid4())
        connection.execute(
            sa.text(
                """
                INSERT INTO roles (role_id, name, description, is_system_role, is_default, permissions, organization_id, created_at, updated_at)
                VALUES (:role_id, :name, :description, :is_system, :is_default, :permissions, NULL, :created_at, :updated_at)
                """
            ),
            {
                'role_id': role_id,
                'name': role_data['name'],
                'description': role_data['description'],
                'is_system': True,
                'is_default': (role_key == 'viewer'),  # Viewer is default role
                'permissions': json.dumps(role_data['permissions']),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
        )


def downgrade():
    """Drop RBAC tables"""
    op.drop_table('user_roles')
    op.drop_table('roles')
    op.drop_table('users')
    op.drop_table('organizations')

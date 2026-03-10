"""add multi llm routing

Revision ID: 20251218_2100
Revises: 20251218_2000
Create Date: 2025-12-18 21:00:00.000000

P1 Feature #3: Multi-LLM Routing

Creates tables for multi-provider LLM support with intelligent routing:
- llm_providers: Provider configurations (OpenAI, Anthropic, etc.)
- llm_models: Model configs with pricing and capabilities
- llm_requests: Request logging for analytics
- llm_routing_rules: Custom routing rules
- llm_model_comparisons: A/B testing framework
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251218_2100'
down_revision = '20251218_2000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create llm_providers table
    op.create_table(
        'llm_providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.Enum(
            'openai', 'anthropic', 'google', 'azure_openai', 'aws_bedrock',
            'cohere', 'huggingface', 'local_ollama', 'together_ai', 'replicate',
            name='llmprovider'
        ), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=255), nullable=False),
        sa.Column('api_key', sa.Text(), nullable=True),  # Encrypted
        sa.Column('api_endpoint', sa.String(length=500), nullable=True),
        sa.Column('additional_config', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_default', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        # FK disabled - type mismatch (INTEGER vs VARCHAR)
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for llm_providers
    op.create_index('ix_llm_providers_id', 'llm_providers', ['id'])
    op.create_index('ix_llm_providers_provider', 'llm_providers', ['provider'])
    op.create_index('ix_llm_providers_organization_id', 'llm_providers', ['organization_id'])
    op.create_index('ix_llm_providers_is_active', 'llm_providers', ['is_active'])
    op.create_index('ix_llm_providers_org_active', 'llm_providers', ['organization_id', 'is_active'])

    # Create llm_models table
    op.create_table(
        'llm_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('capabilities', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('max_tokens', sa.Integer(), server_default='4096'),
        sa.Column('supports_streaming', sa.Boolean(), server_default='true'),
        sa.Column('supports_function_calling', sa.Boolean(), server_default='false'),
        sa.Column('input_cost_per_1m_tokens', sa.Float(), nullable=False),
        sa.Column('output_cost_per_1m_tokens', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='USD'),
        sa.Column('avg_latency_ms', sa.Float(), server_default='0.0'),
        sa.Column('avg_quality_score', sa.Float(), server_default='0.0'),
        sa.Column('success_rate', sa.Float(), server_default='1.0'),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=True),
        sa.Column('rate_limit_per_day', sa.Integer(), nullable=True),
        sa.Column('max_concurrent_requests', sa.Integer(), server_default='10'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_experimental', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['provider_id'], ['llm_providers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id', 'model_name', name='uq_provider_model')
    )

    # Create indexes for llm_models
    op.create_index('ix_llm_models_id', 'llm_models', ['id'])
    op.create_index('ix_llm_models_provider_id', 'llm_models', ['provider_id'])
    op.create_index('ix_llm_models_model_name', 'llm_models', ['model_name'])
    op.create_index('ix_llm_models_is_active', 'llm_models', ['is_active'])
    op.create_index('ix_llm_models_provider_active', 'llm_models', ['provider_id', 'is_active'])

    # Create llm_requests table
    op.create_table(
        'llm_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('workflow_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('input_cost', sa.Float(), nullable=False),
        sa.Column('output_cost', sa.Float(), nullable=False),
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('was_cached', sa.Boolean(), server_default='false'),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('routing_strategy', sa.Enum(
            'lowest_cost', 'lowest_latency', 'highest_quality', 'balanced',
            'capability_match', 'round_robin', 'manual',
            name='routingstrategy'
        ), nullable=True),
        sa.Column('was_fallback', sa.Boolean(), server_default='false'),
        sa.Column('original_model_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['model_id'], ['llm_models.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for llm_requests
    op.create_index('ix_llm_requests_id', 'llm_requests', ['id'])
    op.create_index('ix_llm_requests_model_id', 'llm_requests', ['model_id'])
    op.create_index('ix_llm_requests_task_id', 'llm_requests', ['task_id'])
    op.create_index('ix_llm_requests_workflow_id', 'llm_requests', ['workflow_id'])
    op.create_index('ix_llm_requests_user_id', 'llm_requests', ['user_id'])
    op.create_index('ix_llm_requests_organization_id', 'llm_requests', ['organization_id'])
    op.create_index('ix_llm_requests_status', 'llm_requests', ['status'])
    op.create_index('ix_llm_requests_routing_strategy', 'llm_requests', ['routing_strategy'])
    op.create_index('ix_llm_requests_created_at', 'llm_requests', ['created_at'])
    op.create_index('ix_llm_requests_user_date', 'llm_requests', ['user_id', 'created_at'])
    op.create_index('ix_llm_requests_org_date', 'llm_requests', ['organization_id', 'created_at'])
    op.create_index('ix_llm_requests_model_status', 'llm_requests', ['model_id', 'status'])

    # Create llm_routing_rules table
    op.create_table(
        'llm_routing_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=255), nullable=False),
        sa.Column('conditions', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('target_model_id', sa.Integer(), nullable=True),
        sa.Column('routing_strategy', sa.Enum(
            'lowest_cost', 'lowest_latency', 'highest_quality', 'balanced',
            'capability_match', 'round_robin', 'manual',
            name='routingstrategy'
        ), nullable=True),
        sa.Column('priority', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        # FK disabled - type mismatch (INTEGER vs VARCHAR)
        sa.ForeignKeyConstraint(['target_model_id'], ['llm_models.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for llm_routing_rules
    op.create_index('ix_llm_routing_rules_id', 'llm_routing_rules', ['id'])
    op.create_index('ix_llm_routing_rules_organization_id', 'llm_routing_rules', ['organization_id'])
    op.create_index('ix_llm_routing_rules_is_active', 'llm_routing_rules', ['is_active'])
    op.create_index('ix_llm_routing_rules_priority', 'llm_routing_rules', ['priority'])
    op.create_index('ix_llm_routing_rules_org_active', 'llm_routing_rules', ['organization_id', 'is_active'])

    # Create llm_model_comparisons table
    op.create_table(
        'llm_model_comparisons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('model_a_id', sa.Integer(), nullable=False),
        sa.Column('model_b_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=255), nullable=False),
        sa.Column('test_cases', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('evaluation_criteria', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('model_a_avg_cost', sa.Float(), nullable=True),
        sa.Column('model_b_avg_cost', sa.Float(), nullable=True),
        sa.Column('model_a_avg_latency', sa.Float(), nullable=True),
        sa.Column('model_b_avg_latency', sa.Float(), nullable=True),
        sa.Column('model_a_avg_quality', sa.Float(), nullable=True),
        sa.Column('model_b_avg_quality', sa.Float(), nullable=True),
        sa.Column('winner_model_id', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['model_a_id'], ['llm_models.id'], ),
        sa.ForeignKeyConstraint(['model_b_id'], ['llm_models.id'], ),
        # FK disabled - type mismatch (INTEGER vs VARCHAR)
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for llm_model_comparisons
    op.create_index('ix_llm_model_comparisons_id', 'llm_model_comparisons', ['id'])
    op.create_index('ix_llm_model_comparisons_organization_id', 'llm_model_comparisons', ['organization_id'])
    op.create_index('ix_llm_comparisons_status', 'llm_model_comparisons', ['status'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('llm_model_comparisons')
    op.drop_table('llm_routing_rules')
    op.drop_table('llm_requests')
    op.drop_table('llm_models')
    op.drop_table('llm_providers')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS llmprovider')
    op.execute('DROP TYPE IF EXISTS routingstrategy')

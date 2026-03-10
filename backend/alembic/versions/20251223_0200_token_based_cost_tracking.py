"""token based cost tracking

Revision ID: 20251223_0200
Revises: 20251223_0100
Create Date: 2025-12-23 02:00:00.000000

Migration: Convert from hardcoded cost storage to token-based cost calculation

Changes:
- Add total_input_tokens, total_output_tokens to agents_registry
- Add primary_model, primary_provider to agents_registry
- Update agent_usage_log to track input/output tokens separately
- Add model_used, provider to agent_usage_log
- Keep legacy cost columns for backward compatibility
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251223_0200'
down_revision = '20251223_0100'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # ========================================================================
    # Update agents_registry table
    # ========================================================================

    # Add token tracking columns
    op.add_column('agents_registry', sa.Column('total_input_tokens', sa.BigInteger(), server_default='0', nullable=False))
    op.add_column('agents_registry', sa.Column('total_output_tokens', sa.BigInteger(), server_default='0', nullable=False))
    op.add_column('agents_registry', sa.Column('primary_model', sa.String(length=100), nullable=True))
    op.add_column('agents_registry', sa.Column('primary_provider', sa.String(length=50), nullable=True))

    # Migrate existing cost data to estimated tokens (if any exists)
    # Note: This is a best-effort migration - actual token counts are not recoverable
    # Using rough estimate: $0.01 per 1000 tokens average
    op.execute("""
        UPDATE agents_registry
        SET total_input_tokens = COALESCE(total_cost_usd::bigint * 50000, 0),
            total_output_tokens = COALESCE(total_cost_usd::bigint * 50000, 0),
            primary_model = 'gpt-4o',
            primary_provider = 'openai'
        WHERE total_cost_usd IS NOT NULL AND total_cost_usd > 0
    """)

    # KEEP total_cost_usd column for backward compatibility
    # It will be maintained alongside token tracking

    # ========================================================================
    # Update agent_usage_log table
    # ========================================================================

    # Add detailed token tracking columns
    op.add_column('agent_usage_log', sa.Column('input_tokens', sa.Integer(), nullable=True))
    op.add_column('agent_usage_log', sa.Column('output_tokens', sa.Integer(), nullable=True))
    op.add_column('agent_usage_log', sa.Column('model_used', sa.String(length=100), nullable=True))
    op.add_column('agent_usage_log', sa.Column('provider', sa.String(length=50), nullable=True))

    # Migrate existing data if any
    op.execute("""
        UPDATE agent_usage_log
        SET input_tokens = COALESCE(tokens_used / 2, 0),
            output_tokens = COALESCE(tokens_used / 2, 0),
            model_used = 'gpt-4o',
            provider = 'openai'
        WHERE tokens_used IS NOT NULL
    """)

    # KEEP legacy columns (tokens_used, cost_usd) for backward compatibility


def downgrade() -> None:
    # ========================================================================
    # Revert agent_usage_log table
    # ========================================================================

    # Remove new columns
    op.drop_column('agent_usage_log', 'provider')
    op.drop_column('agent_usage_log', 'model_used')
    op.drop_column('agent_usage_log', 'output_tokens')
    op.drop_column('agent_usage_log', 'input_tokens')

    # ========================================================================
    # Revert agents_registry table
    # ========================================================================

    # Remove token columns
    op.drop_column('agents_registry', 'primary_provider')
    op.drop_column('agents_registry', 'primary_model')
    op.drop_column('agents_registry', 'total_output_tokens')
    op.drop_column('agents_registry', 'total_input_tokens')

"""add ml routing optimization

Revision ID: 20251219_0900
Revises: 20251219_0800
Create Date: 2025-12-19 09:00:00.000000

P2 Feature #6: ML-Based Routing Optimization
"""
from alembic import op
import sqlalchemy as sa

revision = '20251219_0900'
down_revision = '20251219_0800'

def upgrade() -> None:
    # Create enum types only if they don't exist
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE routingstrategy AS ENUM ('cost_optimized', 'performance_optimized', 'balanced', 'quality_optimized', 'latency_optimized', 'ml_predicted');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;

    DO $$ BEGIN
        CREATE TYPE modelprovider AS ENUM ('openai', 'anthropic', 'google', 'meta', 'cohere', 'mistral', 'local');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;

    DO $$ BEGIN
        CREATE TYPE optimizationgoal AS ENUM ('minimize_cost', 'maximize_quality', 'minimize_latency', 'maximize_throughput', 'balanced');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;

    DO $$ BEGIN
        CREATE TYPE predictionconfidence AS ENUM ('very_low', 'low', 'medium', 'high', 'very_high');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    # Check which tables exist
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Create llm_models table only if it doesn't exist
    if 'llm_models' not in existing_tables:
        op.execute("""
    CREATE TABLE llm_models (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) UNIQUE NOT NULL,
        provider modelprovider NOT NULL,
        model_id VARCHAR(255) NOT NULL,
        max_tokens INTEGER NOT NULL,
        supports_functions BOOLEAN DEFAULT FALSE,
        supports_vision BOOLEAN DEFAULT FALSE,
        supports_streaming BOOLEAN DEFAULT TRUE,
        avg_latency_ms FLOAT DEFAULT 1000.0,
        avg_tokens_per_second FLOAT DEFAULT 50.0,
        cost_per_1m_input_tokens FLOAT NOT NULL,
        cost_per_1m_output_tokens FLOAT NOT NULL,
        quality_score FLOAT DEFAULT 0.0,
        success_rate FLOAT DEFAULT 0.0,
        total_requests INTEGER DEFAULT 0,
        total_tokens_processed INTEGER DEFAULT 0,
        total_cost_usd FLOAT DEFAULT 0.0,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        is_available BOOLEAN DEFAULT TRUE,
        tags JSON DEFAULT '{}',
        metadata JSON DEFAULT '{}',
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now()
    );
    CREATE INDEX ix_llm_models_name ON llm_models(name);
    CREATE INDEX ix_llm_models_provider ON llm_models(provider);
    CREATE INDEX ix_llm_models_active ON llm_models(is_active);
        """)

    # Create routing_policies table only if it doesn't exist
    if 'routing_policies' not in existing_tables:
        op.execute("""
    CREATE TABLE routing_policies (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        strategy routingstrategy NOT NULL,
        optimization_goal optimizationgoal NOT NULL,
        allowed_providers JSON DEFAULT '[]',
        allowed_models JSON DEFAULT '[]',
        excluded_models JSON DEFAULT '[]',
        max_cost_per_request_usd FLOAT,
        target_cost_reduction_percent FLOAT DEFAULT 0.0,
        max_latency_ms FLOAT,
        min_quality_score FLOAT DEFAULT 0.0,
        min_success_rate FLOAT DEFAULT 90.0,
        use_ml_prediction BOOLEAN DEFAULT TRUE NOT NULL,
        ml_model_version VARCHAR(50),
        confidence_threshold FLOAT DEFAULT 0.7,
        fallback_model_id INTEGER REFERENCES llm_models(id),
        enable_fallback BOOLEAN DEFAULT TRUE,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        total_requests INTEGER DEFAULT 0,
        total_cost_saved_usd FLOAT DEFAULT 0.0,
        avg_cost_reduction_percent FLOAT DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now(),
        created_by VARCHAR(255)
    );
    CREATE INDEX ix_routing_policies_name ON routing_policies(name);
    CREATE INDEX ix_routing_policies_strategy ON routing_policies(strategy);
    CREATE INDEX ix_routing_policies_active ON routing_policies(is_active);
        """)

    # Create routing_decisions table only if it doesn't exist
    if 'routing_decisions' not in existing_tables:
        op.execute("""
    CREATE TABLE routing_decisions (
        id SERIAL PRIMARY KEY,
        policy_id INTEGER NOT NULL REFERENCES routing_policies(id),
        request_id VARCHAR(255) UNIQUE,
        workflow_id INTEGER,
        agent_id INTEGER,
        input_length_tokens INTEGER NOT NULL,
        expected_output_tokens INTEGER DEFAULT 0,
        task_type VARCHAR(100),
        task_complexity FLOAT,
        requires_functions BOOLEAN DEFAULT FALSE,
        requires_vision BOOLEAN DEFAULT FALSE,
        predicted_model_id INTEGER NOT NULL REFERENCES llm_models(id),
        prediction_confidence predictionconfidence NOT NULL,
        confidence_score FLOAT NOT NULL,
        prediction_features JSON DEFAULT '{}',
        candidate_models JSON DEFAULT '[]',
        actual_model_id INTEGER NOT NULL REFERENCES llm_models(id),
        was_fallback BOOLEAN DEFAULT FALSE,
        actual_latency_ms FLOAT,
        actual_input_tokens INTEGER,
        actual_output_tokens INTEGER,
        actual_cost_usd FLOAT,
        success BOOLEAN,
        error_message TEXT,
        predicted_latency_ms FLOAT,
        predicted_cost_usd FLOAT,
        latency_error_percent FLOAT,
        cost_error_percent FLOAT,
        baseline_cost_usd FLOAT,
        cost_saved_usd FLOAT DEFAULT 0.0,
        cost_reduction_percent FLOAT DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT now() NOT NULL
    );
    CREATE INDEX ix_routing_decisions_policy ON routing_decisions(policy_id);
    CREATE INDEX ix_routing_decisions_request ON routing_decisions(request_id);
    CREATE INDEX ix_routing_decisions_workflow ON routing_decisions(workflow_id);
    CREATE INDEX ix_routing_decisions_agent ON routing_decisions(agent_id);
    CREATE INDEX ix_routing_decisions_task_type ON routing_decisions(task_type);
    CREATE INDEX ix_routing_decisions_predicted_model ON routing_decisions(predicted_model_id);
    CREATE INDEX ix_routing_decisions_created ON routing_decisions(created_at);
        """)

    # Create model_performance_history table only if it doesn't exist
    if 'model_performance_history' not in existing_tables:
        op.execute("""
    CREATE TABLE model_performance_history (
        id SERIAL PRIMARY KEY,
        model_id INTEGER NOT NULL REFERENCES llm_models(id),
        task_type VARCHAR(100),
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        latency_ms FLOAT NOT NULL,
        cost_usd FLOAT NOT NULL,
        success BOOLEAN NOT NULL,
        quality_score FLOAT,
        time_of_day INTEGER,
        day_of_week INTEGER,
        load_level FLOAT,
        error_type VARCHAR(100),
        error_message TEXT,
        timestamp TIMESTAMP DEFAULT now() NOT NULL
    );
    CREATE INDEX ix_performance_history_model ON model_performance_history(model_id);
    CREATE INDEX ix_performance_history_task ON model_performance_history(task_type);
    CREATE INDEX ix_performance_history_timestamp ON model_performance_history(timestamp);
        """)

    # Create ml_routing_models table only if it doesn't exist
    if 'ml_routing_models' not in existing_tables:
        op.execute("""
    CREATE TABLE ml_routing_models (
        id SERIAL PRIMARY KEY,
        version VARCHAR(50) UNIQUE NOT NULL,
        algorithm VARCHAR(100) NOT NULL,
        training_samples INTEGER DEFAULT 0,
        training_start TIMESTAMP,
        training_end TIMESTAMP,
        validation_accuracy FLOAT,
        validation_cost_savings FLOAT,
        validation_latency_error FLOAT,
        model_path VARCHAR(500),
        feature_importance JSON DEFAULT '{}',
        hyperparameters JSON DEFAULT '{}',
        is_active BOOLEAN DEFAULT FALSE NOT NULL,
        is_production BOOLEAN DEFAULT FALSE NOT NULL,
        total_predictions INTEGER DEFAULT 0,
        avg_confidence FLOAT DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        deployed_at TIMESTAMP
    );
    CREATE INDEX ix_ml_routing_models_version ON ml_routing_models(version);
        """)

    # Create cost_optimization_rules table only if it doesn't exist
    if 'cost_optimization_rules' not in existing_tables:
        op.execute("""
    CREATE TABLE cost_optimization_rules (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        min_input_tokens INTEGER,
        max_input_tokens INTEGER,
        task_types JSON DEFAULT '[]',
        preferred_model_id INTEGER NOT NULL REFERENCES llm_models(id),
        alternative_model_id INTEGER REFERENCES llm_models(id),
        max_acceptable_latency_ms FLOAT,
        min_quality_threshold FLOAT,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        priority INTEGER DEFAULT 100,
        times_applied INTEGER DEFAULT 0,
        total_cost_saved_usd FLOAT DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT now() NOT NULL
    );
        """)

def downgrade() -> None:
    op.drop_table('cost_optimization_rules')
    op.drop_table('ml_routing_models')
    op.drop_table('model_performance_history')
    op.drop_table('routing_decisions')
    op.drop_table('routing_policies')
    op.drop_table('llm_models')
    op.execute('DROP TYPE IF EXISTS routingstrategy')
    op.execute('DROP TYPE IF EXISTS modelprovider')
    op.execute('DROP TYPE IF EXISTS optimizationgoal')
    op.execute('DROP TYPE IF EXISTS predictionconfidence')

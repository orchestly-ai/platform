"""add multi-cloud deployment

Revision ID: 20251219_0800
Revises: 20251219_0700
Create Date: 2025-12-19 08:00:00.000000

P2 Feature #2: Multi-Cloud Deployment
"""
from alembic import op
import sqlalchemy as sa

revision = '20251219_0800'
down_revision = '20251219_0700'

def upgrade() -> None:
    op.execute("""
    CREATE TYPE cloudprovider AS ENUM ('aws', 'azure', 'gcp', 'on_premise', 'hybrid');
    CREATE TYPE deploymentstatus AS ENUM ('pending', 'provisioning', 'deploying', 'running', 'updating', 'stopping', 'stopped', 'failed', 'terminated');
    CREATE TYPE deploymentstrategy AS ENUM ('blue_green', 'canary', 'rolling', 'recreate', 'a_b_test');
    CREATE TYPE healthstatus AS ENUM ('healthy', 'degraded', 'unhealthy', 'unknown');
    CREATE TYPE autoscalingmetric AS ENUM ('cpu_utilization', 'memory_utilization', 'request_count', 'response_time', 'queue_depth', 'custom');
    CREATE TYPE instancetype AS ENUM ('aws_t3_micro', 'aws_t3_small', 'aws_t3_medium', 'aws_m5_large', 'aws_c5_xlarge', 
        'azure_b1s', 'azure_b2s', 'azure_d2s_v3', 'azure_f4s_v2',
        'gcp_e2_micro', 'gcp_e2_small', 'gcp_e2_medium', 'gcp_n1_standard_2',
        'on_prem_small', 'on_prem_medium', 'on_prem_large');
    CREATE TYPE loadbalancertype AS ENUM ('application', 'network', 'gateway', 'internal');

    CREATE TABLE cloud_accounts (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        provider cloudprovider NOT NULL,
        account_id VARCHAR(255) NOT NULL,
        region VARCHAR(100) NOT NULL,
        credentials_encrypted TEXT,
        is_default BOOLEAN DEFAULT FALSE NOT NULL,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        max_instances INTEGER DEFAULT 100,
        max_vcpus INTEGER DEFAULT 200,
        max_memory_gb INTEGER DEFAULT 512,
        current_instances INTEGER DEFAULT 0,
        current_vcpus INTEGER DEFAULT 0,
        current_memory_gb INTEGER DEFAULT 0,
        monthly_budget_usd FLOAT,
        current_month_cost_usd FLOAT DEFAULT 0.0,
        tags JSON DEFAULT '{}',
        metadata JSON DEFAULT '{}',
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now(),
        created_by VARCHAR(255)
    );
    CREATE INDEX ix_cloud_accounts_name ON cloud_accounts(name);
    CREATE INDEX ix_cloud_accounts_provider ON cloud_accounts(provider);
    CREATE INDEX ix_cloud_accounts_active ON cloud_accounts(is_active);

    CREATE TABLE deployments (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        agent_id INTEGER NOT NULL,
        version VARCHAR(50) NOT NULL,
        cloud_account_id INTEGER NOT NULL REFERENCES cloud_accounts(id),
        provider cloudprovider NOT NULL,
        region VARCHAR(100) NOT NULL,
        availability_zones JSON DEFAULT '[]',
        status deploymentstatus DEFAULT 'pending' NOT NULL,
        strategy deploymentstrategy DEFAULT 'rolling' NOT NULL,
        instance_type instancetype NOT NULL,
        min_instances INTEGER DEFAULT 1 NOT NULL,
        max_instances INTEGER DEFAULT 10 NOT NULL,
        desired_instances INTEGER DEFAULT 1 NOT NULL,
        current_instances INTEGER DEFAULT 0 NOT NULL,
        container_image VARCHAR(500) NOT NULL,
        container_port INTEGER DEFAULT 8080,
        environment_variables JSON DEFAULT '{}',
        secrets JSON DEFAULT '{}',
        cpu_units INTEGER DEFAULT 1024,
        memory_mb INTEGER DEFAULT 2048,
        storage_gb INTEGER DEFAULT 10,
        gpu_count INTEGER DEFAULT 0,
        vpc_id VARCHAR(255),
        subnet_ids JSON DEFAULT '[]',
        security_group_ids JSON DEFAULT '[]',
        load_balancer_dns VARCHAR(500),
        internal_endpoint VARCHAR(500),
        external_endpoint VARCHAR(500),
        health_status healthstatus DEFAULT 'unknown' NOT NULL,
        health_check_path VARCHAR(255) DEFAULT '/health',
        health_check_interval_seconds INTEGER DEFAULT 30,
        deployed_at TIMESTAMP,
        deployment_duration_seconds INTEGER,
        last_health_check TIMESTAMP,
        error_message TEXT,
        estimated_hourly_cost_usd FLOAT DEFAULT 0.0,
        actual_cost_usd FLOAT DEFAULT 0.0,
        tags JSON DEFAULT '{}',
        metadata JSON DEFAULT '{}',
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now(),
        created_by VARCHAR(255)
    );
    CREATE INDEX ix_deployments_name ON deployments(name);
    CREATE INDEX ix_deployments_agent ON deployments(agent_id);
    CREATE INDEX ix_deployments_account ON deployments(cloud_account_id);
    CREATE INDEX ix_deployments_provider ON deployments(provider);
    CREATE INDEX ix_deployments_status ON deployments(status);
    CREATE INDEX ix_deployments_created ON deployments(created_at);

    CREATE TABLE autoscaling_policies (
        id SERIAL PRIMARY KEY,
        deployment_id INTEGER NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        metric autoscalingmetric NOT NULL,
        target_value FLOAT NOT NULL,
        scale_up_threshold FLOAT NOT NULL,
        scale_down_threshold FLOAT NOT NULL,
        scale_up_increment INTEGER DEFAULT 1,
        scale_down_increment INTEGER DEFAULT 1,
        cooldown_period_seconds INTEGER DEFAULT 300,
        custom_metric_query TEXT,
        last_scaled_at TIMESTAMP,
        scale_up_count INTEGER DEFAULT 0,
        scale_down_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now()
    );
    CREATE INDEX ix_autoscaling_deployment ON autoscaling_policies(deployment_id);
    CREATE INDEX ix_autoscaling_active ON autoscaling_policies(is_active);

    CREATE TABLE deployment_events (
        id SERIAL PRIMARY KEY,
        deployment_id INTEGER NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
        event_type VARCHAR(100) NOT NULL,
        status VARCHAR(50) NOT NULL,
        message TEXT NOT NULL,
        old_state JSON,
        new_state JSON,
        details JSON DEFAULT '{}',
        triggered_by VARCHAR(255),
        created_at TIMESTAMP DEFAULT now() NOT NULL
    );
    CREATE INDEX ix_deployment_events_deployment ON deployment_events(deployment_id);
    CREATE INDEX ix_deployment_events_type ON deployment_events(event_type);
    CREATE INDEX ix_deployment_events_created ON deployment_events(created_at);

    CREATE TABLE load_balancers (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        lb_type loadbalancertype NOT NULL,
        provider cloudprovider NOT NULL,
        dns_name VARCHAR(500),
        is_public BOOLEAN DEFAULT TRUE NOT NULL,
        ssl_enabled BOOLEAN DEFAULT TRUE NOT NULL,
        ssl_certificate_arn VARCHAR(500),
        deployment_ids JSON DEFAULT '[]',
        routing_algorithm VARCHAR(50) DEFAULT 'round_robin',
        sticky_sessions BOOLEAN DEFAULT FALSE,
        health_check_enabled BOOLEAN DEFAULT TRUE,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        health_status healthstatus DEFAULT 'unknown',
        total_requests INTEGER DEFAULT 0,
        active_connections INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now()
    );
    CREATE INDEX ix_load_balancers_name ON load_balancers(name);
    CREATE INDEX ix_load_balancers_dns ON load_balancers(dns_name);

    CREATE TABLE deployment_metrics (
        id SERIAL PRIMARY KEY,
        deployment_id INTEGER NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
        cpu_utilization_percent FLOAT DEFAULT 0.0,
        memory_utilization_percent FLOAT DEFAULT 0.0,
        disk_utilization_percent FLOAT DEFAULT 0.0,
        network_in_mbps FLOAT DEFAULT 0.0,
        network_out_mbps FLOAT DEFAULT 0.0,
        request_count INTEGER DEFAULT 0,
        error_count INTEGER DEFAULT 0,
        avg_response_time_ms FLOAT DEFAULT 0.0,
        p95_response_time_ms FLOAT DEFAULT 0.0,
        p99_response_time_ms FLOAT DEFAULT 0.0,
        healthy_instances INTEGER DEFAULT 0,
        unhealthy_instances INTEGER DEFAULT 0,
        current_hourly_cost_usd FLOAT DEFAULT 0.0,
        timestamp TIMESTAMP DEFAULT now() NOT NULL
    );
    CREATE INDEX ix_deployment_metrics_deployment ON deployment_metrics(deployment_id);
    CREATE INDEX ix_deployment_metrics_timestamp ON deployment_metrics(timestamp);
    """)

def downgrade() -> None:
    op.drop_table('deployment_metrics')
    op.drop_table('load_balancers')
    op.drop_table('deployment_events')
    op.drop_table('autoscaling_policies')
    op.drop_table('deployments')
    op.drop_table('cloud_accounts')
    op.execute('DROP TYPE IF EXISTS cloudprovider')
    op.execute('DROP TYPE IF EXISTS deploymentstatus')
    op.execute('DROP TYPE IF EXISTS deploymentstrategy')
    op.execute('DROP TYPE IF EXISTS healthstatus')
    op.execute('DROP TYPE IF EXISTS autoscalingmetric')
    op.execute('DROP TYPE IF EXISTS instancetype')
    op.execute('DROP TYPE IF EXISTS loadbalancertype')

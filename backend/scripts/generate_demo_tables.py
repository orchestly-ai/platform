"""
Generate CREATE TABLE SQL for demo cleanup and recreation.

This script analyzes SQLAlchemy models and generates the SQL needed
to drop and recreate tables for clean demo runs.
"""

# Marketplace tables
MARKETPLACE_TABLES = """
-- Drop tables in dependency order
DROP TABLE IF EXISTS agent_analytics CASCADE;
DROP TABLE IF EXISTS agent_collection_items CASCADE;
DROP TABLE IF EXISTS agent_collections CASCADE;
DROP TABLE IF EXISTS agent_reviews CASCADE;
DROP TABLE IF EXISTS agent_installations CASCADE;
DROP TABLE IF EXISTS agent_versions CASCADE;
DROP TABLE IF EXISTS marketplace_agents CASCADE;

-- Create marketplace_agents
CREATE TABLE marketplace_agents (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    long_description TEXT,
    category VARCHAR(50),
    visibility VARCHAR(50) DEFAULT 'private',
    pricing VARCHAR(50) DEFAULT 'free',
    price_amount DECIMAL(10,2),
    price_currency VARCHAR(10) DEFAULT 'USD',
    pricing_model VARCHAR(50),
    tags JSON DEFAULT '[]',
    publisher_id VARCHAR(255),
    publisher_name VARCHAR(255),
    publisher_url VARCHAR(500),
    icon_url VARCHAR(500),
    banner_url VARCHAR(500),
    screenshots JSON DEFAULT '[]',
    demo_url VARCHAR(500),
    documentation_url VARCHAR(500),
    source_url VARCHAR(500),
    support_url VARCHAR(500),
    homepage_url VARCHAR(500),
    version VARCHAR(50),
    compatible_versions JSON DEFAULT '[]',
    dependencies JSON DEFAULT '[]',
    install_count INTEGER DEFAULT 0,
    rating_avg DECIMAL(3,2) DEFAULT 0.0,
    rating_count INTEGER DEFAULT 0,
    featured BOOLEAN DEFAULT FALSE,
    verified BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create agent_versions
CREATE TABLE agent_versions (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES marketplace_agents(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,
    release_notes TEXT,
    config JSON DEFAULT '{}',
    requirements JSON DEFAULT '[]',
    breaking_changes JSON DEFAULT '[]',
    deprecated BOOLEAN DEFAULT FALSE,
    download_url VARCHAR(500),
    size_bytes BIGINT,
    checksum VARCHAR(255),
    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, version)
);

-- Create agent_installations
CREATE TABLE agent_installations (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES marketplace_agents(id) ON DELETE CASCADE,
    version_id INTEGER REFERENCES agent_versions(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    organization_id INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    config JSON DEFAULT '{}',
    last_used_at TIMESTAMP,
    install_source VARCHAR(100),
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, user_id, organization_id)
);

-- Create agent_reviews
CREATE TABLE agent_reviews (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES marketplace_agents(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    comment TEXT,
    verified_purchase BOOLEAN DEFAULT FALSE,
    helpful_count INTEGER DEFAULT 0,
    flagged BOOLEAN DEFAULT FALSE,
    response TEXT,
    responded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, user_id)
);

-- Create agent_collections
CREATE TABLE agent_collections (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    icon VARCHAR(255),
    curator_id VARCHAR(255),
    visibility VARCHAR(50) DEFAULT 'public',
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create agent_collection_items (junction table)
CREATE TABLE agent_collection_items (
    id SERIAL PRIMARY KEY,
    collection_id INTEGER REFERENCES agent_collections(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES marketplace_agents(id) ON DELETE CASCADE,
    sort_order INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_id, agent_id)
);

-- Create agent_analytics
CREATE TABLE agent_analytics (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES marketplace_agents(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    views INTEGER DEFAULT 0,
    installs INTEGER DEFAULT 0,
    uninstalls INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    revenue DECIMAL(10,2) DEFAULT 0.0,
    UNIQUE(agent_id, metric_date)
);
"""

# Real-time tables
REALTIME_TABLES = """
-- Drop tables in dependency order
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS realtime_events CASCADE;
DROP TABLE IF EXISTS user_presence CASCADE;
DROP TABLE IF EXISTS websocket_connections CASCADE;

-- Create websocket_connections
CREATE TABLE websocket_connections (
    id SERIAL PRIMARY KEY,
    connection_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    client_ip VARCHAR(45),
    user_agent VARCHAR(500),
    status VARCHAR(50) DEFAULT 'connected',
    last_ping_at TIMESTAMP,
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMP,
    metadata JSON DEFAULT '{}'
);

-- Create user_presence
CREATE TABLE user_presence (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'offline',
    status_message VARCHAR(500),
    current_workflow_id INTEGER,
    current_page VARCHAR(255),
    last_seen_at TIMESTAMP,
    extra_metadata JSON DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create realtime_events
CREATE TABLE realtime_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    event_data JSON DEFAULT '{}',
    user_id VARCHAR(255),
    workspace_id VARCHAR(255),
    workflow_id INTEGER,
    task_id INTEGER,
    agent_id INTEGER,
    channel_type VARCHAR(50) NOT NULL,
    channel_id VARCHAR(255) NOT NULL,
    delivered_to_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create notifications
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) DEFAULT 'info',
    action_url VARCHAR(500),
    action_label VARCHAR(100),
    workflow_id INTEGER,
    task_id INTEGER,
    approval_id INTEGER,
    read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    dismissed BOOLEAN DEFAULT FALSE,
    dismissed_at TIMESTAMP,
    priority VARCHAR(50) DEFAULT 'normal',
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_user_read ON notifications(user_id, read);
CREATE INDEX idx_notifications_created ON notifications(created_at);
"""

# Security tables
SECURITY_TABLES = """
-- Drop tables in dependency order
DROP TABLE IF EXISTS encryption_keys CASCADE;
DROP TABLE IF EXISTS data_retention_policies CASCADE;
DROP TABLE IF EXISTS security_incidents CASCADE;
DROP TABLE IF EXISTS compliance_controls CASCADE;
DROP TABLE IF EXISTS access_policies CASCADE;
DROP TABLE IF EXISTS user_roles CASCADE;
DROP TABLE IF EXISTS roles CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;

-- Create audit_logs
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) DEFAULT 'info',
    user_id VARCHAR(255),
    organization_id INTEGER,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    request_id VARCHAR(255),
    session_id VARCHAR(255),
    details JSON DEFAULT '{}',
    before_state JSON,
    after_state JSON,
    retention_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_logs(user_id, created_at);
CREATE INDEX idx_audit_severity ON audit_logs(severity, created_at);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);

-- Create roles
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    permissions JSON DEFAULT '[]',
    scope VARCHAR(50) DEFAULT 'organization',
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_roles
CREATE TABLE user_roles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    organization_id INTEGER,
    granted_by VARCHAR(255),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    UNIQUE(user_id, role_id, organization_id)
);

-- Create access_policies
CREATE TABLE access_policies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    effect VARCHAR(20) DEFAULT 'allow',
    conditions JSON DEFAULT '{}',
    priority INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create compliance_controls
CREATE TABLE compliance_controls (
    id SERIAL PRIMARY KEY,
    control_id VARCHAR(100) UNIQUE NOT NULL,
    framework VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    severity VARCHAR(50) DEFAULT 'medium',
    implementation_status VARCHAR(50) DEFAULT 'not_implemented',
    evidence JSON DEFAULT '[]',
    last_assessed_at TIMESTAMP,
    next_assessment_at TIMESTAMP,
    owner VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create security_incidents
CREATE TABLE security_incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    severity VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'open',
    category VARCHAR(100),
    detected_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    affected_systems JSON DEFAULT '[]',
    indicators JSON DEFAULT '{}',
    response_actions JSON DEFAULT '[]',
    assigned_to VARCHAR(255),
    root_cause TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create data_retention_policies
CREATE TABLE data_retention_policies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    retention_days INTEGER NOT NULL,
    archive_after_days INTEGER,
    delete_after_days INTEGER,
    legal_hold BOOLEAN DEFAULT FALSE,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create encryption_keys
CREATE TABLE encryption_keys (
    id SERIAL PRIMARY KEY,
    key_id VARCHAR(255) UNIQUE NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    key_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    rotation_schedule VARCHAR(100),
    last_rotated_at TIMESTAMP,
    next_rotation_at TIMESTAMP,
    created_by VARCHAR(255),
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Multi-cloud tables
MULTICLOUD_TABLES = """
-- Drop tables in dependency order
DROP TABLE IF EXISTS deployment_metrics CASCADE;
DROP TABLE IF EXISTS load_balancers CASCADE;
DROP TABLE IF EXISTS deployment_events CASCADE;
DROP TABLE IF EXISTS autoscaling_policies CASCADE;
DROP TABLE IF EXISTS deployments CASCADE;
DROP TABLE IF EXISTS cloud_accounts CASCADE;

-- Create cloud_accounts
CREATE TABLE cloud_accounts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    account_id VARCHAR(255),
    region VARCHAR(100),
    credentials_encrypted TEXT,
    status VARCHAR(50) DEFAULT 'active',
    is_default BOOLEAN DEFAULT FALSE,
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create deployments
CREATE TABLE deployments (
    id SERIAL PRIMARY KEY,
    deployment_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    cloud_account_id INTEGER REFERENCES cloud_accounts(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    region VARCHAR(100) NOT NULL,
    environment VARCHAR(50) DEFAULT 'production',
    workflow_id INTEGER,
    status VARCHAR(50) DEFAULT 'pending',
    health_status VARCHAR(50),
    instance_type VARCHAR(100),
    instance_count INTEGER DEFAULT 1,
    min_instances INTEGER DEFAULT 1,
    max_instances INTEGER DEFAULT 10,
    auto_scaling_enabled BOOLEAN DEFAULT FALSE,
    endpoint_url VARCHAR(500),
    internal_ip VARCHAR(45),
    external_ip VARCHAR(45),
    config JSON DEFAULT '{}',
    environment_vars JSON DEFAULT '{}',
    tags JSON DEFAULT '{}',
    cost_per_hour DECIMAL(10,4),
    deployed_at TIMESTAMP,
    last_health_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create autoscaling_policies
CREATE TABLE autoscaling_policies (
    id SERIAL PRIMARY KEY,
    deployment_id INTEGER REFERENCES deployments(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    threshold DECIMAL(10,2) NOT NULL,
    comparison_operator VARCHAR(20) NOT NULL,
    scale_direction VARCHAR(10) NOT NULL,
    adjustment_value INTEGER NOT NULL,
    cooldown_seconds INTEGER DEFAULT 300,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create deployment_events
CREATE TABLE deployment_events (
    id SERIAL PRIMARY KEY,
    deployment_id INTEGER REFERENCES deployments(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    message TEXT,
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create load_balancers
CREATE TABLE load_balancers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    cloud_account_id INTEGER REFERENCES cloud_accounts(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    region VARCHAR(100) NOT NULL,
    algorithm VARCHAR(50) DEFAULT 'round_robin',
    health_check_path VARCHAR(255) DEFAULT '/health',
    health_check_interval INTEGER DEFAULT 30,
    target_deployments JSON DEFAULT '[]',
    endpoint_url VARCHAR(500),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create deployment_metrics
CREATE TABLE deployment_metrics (
    id SERIAL PRIMARY KEY,
    deployment_id INTEGER REFERENCES deployments(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    cpu_usage DECIMAL(5,2),
    memory_usage DECIMAL(5,2),
    request_count INTEGER,
    error_count INTEGER,
    response_time_avg DECIMAL(10,2),
    response_time_p95 DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_deployment_metrics_timestamp ON deployment_metrics(deployment_id, timestamp);
"""

if __name__ == "__main__":
    print("=== MARKETPLACE TABLES ===")
    print(MARKETPLACE_TABLES)
    print("\n=== REALTIME TABLES ===")
    print(REALTIME_TABLES)
    print("\n=== SECURITY TABLES ===")
    print(SECURITY_TABLES)
    print("\n=== MULTICLOUD TABLES ===")
    print(MULTICLOUD_TABLES)

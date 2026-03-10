"""
Multi-Cloud Deployment Demo - P2 Feature #2

Demonstrates multi-cloud deployment features:
- Cloud account registration (AWS, Azure, GCP, On-Premise)
- Agent deployment across clouds
- Auto-scaling policies
- Load balancing
- Multi-cloud statistics

Run: python backend/demo_multicloud.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from datetime import datetime

from backend.shared.multicloud_models import *
from backend.shared.multicloud_service import MultiCloudService

DATABASE_URL = "postgresql+asyncpg://localhost/agent_orchestration"

async def demo_multicloud():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Cleanup and recreate tables for clean demo
        for stmt in [
            """DROP TABLE IF EXISTS deployment_metrics CASCADE""",
            """DROP TABLE IF EXISTS load_balancers CASCADE""",
            """DROP TABLE IF EXISTS deployment_events CASCADE""",
            """DROP TABLE IF EXISTS autoscaling_policies CASCADE""",
            """DROP TABLE IF EXISTS deployments CASCADE""",
            """DROP TABLE IF EXISTS cloud_accounts CASCADE""",
            """CREATE TABLE cloud_accounts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
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
    extra_metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255)
)""",
            """CREATE TABLE deployments (
    id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, agent_id INTEGER NOT NULL, version VARCHAR(50) NOT NULL,
    cloud_account_id INTEGER REFERENCES cloud_accounts(id) ON DELETE CASCADE, provider VARCHAR(50) NOT NULL,
    region VARCHAR(100) NOT NULL, availability_zones JSON DEFAULT '[]', status VARCHAR(50) DEFAULT 'PENDING',
    strategy VARCHAR(50) DEFAULT 'ROLLING', instance_type VARCHAR(50) NOT NULL, min_instances INTEGER DEFAULT 1,
    max_instances INTEGER DEFAULT 10, desired_instances INTEGER DEFAULT 1, current_instances INTEGER DEFAULT 0,
    container_image VARCHAR(500) NOT NULL, container_port INTEGER DEFAULT 8080, environment_variables JSON DEFAULT '{}',
    secrets JSON DEFAULT '{}', cpu_units INTEGER DEFAULT 1024, memory_mb INTEGER DEFAULT 2048, storage_gb INTEGER DEFAULT 10,
    gpu_count INTEGER DEFAULT 0, vpc_id VARCHAR(255), subnet_ids JSON DEFAULT '[]', security_group_ids JSON DEFAULT '[]',
    load_balancer_dns VARCHAR(500), internal_endpoint VARCHAR(500), external_endpoint VARCHAR(500),
    health_status VARCHAR(50) DEFAULT 'UNKNOWN', health_check_path VARCHAR(255) DEFAULT '/health',
    health_check_interval_seconds INTEGER DEFAULT 30, deployed_at TIMESTAMP, deployment_duration_seconds INTEGER,
    last_health_check TIMESTAMP, error_message TEXT, estimated_hourly_cost_usd FLOAT DEFAULT 0.0,
    actual_cost_usd FLOAT DEFAULT 0.0, tags JSON DEFAULT '{}', extra_metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, created_by VARCHAR(255)
)""",
            """CREATE TABLE autoscaling_policies (
    id SERIAL PRIMARY KEY, deployment_id INTEGER REFERENCES deployments(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL, is_active BOOLEAN DEFAULT TRUE, metric VARCHAR(100) NOT NULL,
    target_value FLOAT, scale_up_threshold FLOAT, scale_down_threshold FLOAT,
    scale_up_increment INTEGER DEFAULT 1, scale_down_increment INTEGER DEFAULT 1,
    cooldown_period_seconds INTEGER DEFAULT 300, custom_metric_query VARCHAR(500),
    last_scaled_at TIMESTAMP, scale_up_count INTEGER DEFAULT 0, scale_down_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
            """CREATE TABLE deployment_events (
    id SERIAL PRIMARY KEY, deployment_id INTEGER REFERENCES deployments(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL, status VARCHAR(50), message TEXT,
    old_state JSON, new_state JSON, details JSON DEFAULT '{}',
    triggered_by VARCHAR(255), metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
            """CREATE TABLE load_balancers (
    id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, lb_type VARCHAR(50),
    provider VARCHAR(50) NOT NULL, dns_name VARCHAR(500), is_public BOOLEAN DEFAULT TRUE,
    ssl_enabled BOOLEAN DEFAULT FALSE, ssl_certificate_arn VARCHAR(500),
    deployment_ids JSON DEFAULT '[]', routing_algorithm VARCHAR(50) DEFAULT 'round_robin',
    sticky_sessions BOOLEAN DEFAULT FALSE, health_check_enabled BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE, health_status VARCHAR(50) DEFAULT 'healthy',
    total_requests INTEGER DEFAULT 0, active_connections INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
            """CREATE TABLE deployment_metrics (
    id SERIAL PRIMARY KEY, deployment_id INTEGER REFERENCES deployments(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT now(), cpu_utilization_percent FLOAT, memory_utilization_percent FLOAT,
    disk_utilization_percent FLOAT, network_in_mbps FLOAT, network_out_mbps FLOAT,
    request_count INTEGER DEFAULT 0, error_count INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT, p95_response_time_ms FLOAT, p99_response_time_ms FLOAT,
    healthy_instances INTEGER DEFAULT 0, unhealthy_instances INTEGER DEFAULT 0,
    current_hourly_cost_usd FLOAT DEFAULT 0.0
)""",
        ]:
            await db.execute(text(stmt))
        for idx in [
            """CREATE INDEX IF NOT EXISTS idx_deployment_metrics_timestamp ON deployment_metrics(deployment_id, timestamp)""",
        ]:
            await db.execute(text(idx))
        await db.commit()
        print("=" * 80)
        print("MULTI-CLOUD DEPLOYMENT DEMO")
        print("=" * 80)
        print()

        # Demo 1: Cloud Account Registration
        print("☁️  DEMO 1: Cloud Account Registration")
        print("-" * 80)

        print("\n1. Registering AWS account...")
        aws_account = await MultiCloudService.create_cloud_account(
            db,
            CloudAccountCreate(
                name="Production AWS",
                provider=CloudProvider.AWS,
                account_id="123456789012",
                region="us-east-1",
                is_default=True,
                max_instances=50,
                max_vcpus=100,
                monthly_budget_usd=5000.0,
                tags={"environment": "production", "team": "platform"},
            ),
            "admin_user",
        )
        print(f"   ✓ AWS account created: {aws_account.name}")
        print(f"   ✓ Account ID: {aws_account.account_id}")
        print(f"   ✓ Region: {aws_account.region}")
        print(f"   ✓ Monthly budget: ${aws_account.monthly_budget_usd}")

        print("\n2. Registering Azure account...")
        azure_account = await MultiCloudService.create_cloud_account(
            db,
            CloudAccountCreate(
                name="DR Azure",
                provider=CloudProvider.AZURE,
                account_id="azure-sub-001",
                region="eastus",
                max_instances=30,
                monthly_budget_usd=3000.0,
            ),
            "admin_user",
        )
        print(f"   ✓ Azure account created: {azure_account.name}")

        print("\n3. Registering GCP account...")
        gcp_account = await MultiCloudService.create_cloud_account(
            db,
            CloudAccountCreate(
                name="Analytics GCP",
                provider=CloudProvider.GCP,
                account_id="gcp-project-123",
                region="us-central1",
                max_instances=20,
            ),
            "admin_user",
        )
        print(f"   ✓ GCP account created: {gcp_account.name}")

        print("\n4. Registering on-premise infrastructure...")
        onprem_account = await MultiCloudService.create_cloud_account(
            db,
            CloudAccountCreate(
                name="On-Premise Datacenter",
                provider=CloudProvider.ON_PREMISE,
                account_id="dc-sv01",
                region="us-west-datacenter",
                max_instances=10,
            ),
            "admin_user",
        )
        print(f"   ✓ On-premise account created: {onprem_account.name}")

        # Demo 2: Agent Deployment - AWS
        print("\n\n🚀 DEMO 2: Deploy Agent to AWS")
        print("-" * 80)

        print("\n1. Creating deployment configuration...")
        aws_deployment = await MultiCloudService.create_deployment(
            db,
            DeploymentCreate(
                name="customer-service-agent-prod",
                agent_id=1,
                version="v1.2.0",
                cloud_account_id=aws_account.id,
                provider=CloudProvider.AWS,
                region="us-east-1",
                availability_zones=["us-east-1a", "us-east-1b"],
                strategy=DeploymentStrategy.ROLLING,
                instance_type=InstanceType.AWS_M5_LARGE,
                min_instances=2,
                max_instances=10,
                desired_instances=3,
                container_image="acme/customer-service-agent:v1.2.0",
                container_port=8080,
                environment_variables={"LOG_LEVEL": "info", "REGION": "us-east-1"},
                cpu_units=2048,
                memory_mb=4096,
                health_check_path="/health",
                tags={"app": "customer-service", "version": "v1.2.0"},
            ),
            "admin_user",
        )
        print(f"   ✓ Deployment created: {aws_deployment.name}")
        print(f"   ✓ ID: {aws_deployment.id}")
        print(f"   ✓ Provider: {aws_deployment.provider}")
        print(f"   ✓ Instance type: {aws_deployment.instance_type}")
        print(f"   ✓ Desired instances: {aws_deployment.desired_instances}")
        print(f"   ✓ Estimated hourly cost: ${aws_deployment.estimated_hourly_cost_usd:.4f}")
        print(f"   ✓ Estimated monthly cost: ${aws_deployment.estimated_hourly_cost_usd * 730:.2f}")

        print("\n2. Starting deployment...")
        aws_deployment = await MultiCloudService.deploy(db, aws_deployment.id)
        print(f"   ✓ Status: {aws_deployment.status}")
        print(f"   ✓ Deployed at: {aws_deployment.deployed_at}")

        # Demo 3: Multi-Region Deployment
        print("\n\n🌍 DEMO 3: Multi-Region Azure Deployment")
        print("-" * 80)

        print("\n1. Deploying to Azure East US...")
        azure_deployment = await MultiCloudService.create_deployment(
            db,
            DeploymentCreate(
                name="analytics-agent-dr",
                agent_id=2,
                version="v2.0.0",
                cloud_account_id=azure_account.id,
                provider=CloudProvider.AZURE,
                region="eastus",
                strategy=DeploymentStrategy.BLUE_GREEN,
                instance_type=InstanceType.AZURE_D2S_V3,
                min_instances=1,
                max_instances=5,
                desired_instances=2,
                container_image="acme/analytics-agent:v2.0.0",
            ),
            "admin_user",
        )
        print(f"   ✓ Azure deployment created: {azure_deployment.name}")
        print(f"   ✓ Strategy: {azure_deployment.strategy}")

        # Demo 4: Auto-Scaling Policies
        print("\n\n📊 DEMO 4: Auto-Scaling Configuration")
        print("-" * 80)

        print("\n1. Creating CPU-based scaling policy...")
        cpu_policy = await MultiCloudService.create_autoscaling_policy(
            db,
            AutoScalingPolicyCreate(
                deployment_id=aws_deployment.id,
                name="CPU-based scaling",
                metric=AutoScalingMetric.CPU_UTILIZATION,
                target_value=70.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                scale_up_increment=2,
                scale_down_increment=1,
                cooldown_period_seconds=300,
            ),
        )
        print(f"   ✓ Policy created: {cpu_policy.name}")
        print(f"   ✓ Metric: {cpu_policy.metric}")
        print(f"   ✓ Scale up threshold: {cpu_policy.scale_up_threshold}%")
        print(f"   ✓ Scale down threshold: {cpu_policy.scale_down_threshold}%")

        print("\n2. Creating request-based scaling policy...")
        request_policy = await MultiCloudService.create_autoscaling_policy(
            db,
            AutoScalingPolicyCreate(
                deployment_id=aws_deployment.id,
                name="Request count scaling",
                metric=AutoScalingMetric.REQUEST_COUNT,
                target_value=1000.0,
                scale_up_threshold=1500.0,
                scale_down_threshold=500.0,
            ),
        )
        print(f"   ✓ Policy created: {request_policy.name}")

        print("\n3. Simulating high CPU - triggering scale up...")
        new_count = await MultiCloudService.evaluate_autoscaling(
            db,
            aws_deployment.id,
            {"cpu_utilization": 85.0},
        )
        if new_count:
            aws_deployment = await MultiCloudService.scale_deployment(
                db, aws_deployment.id, new_count
            )
            print(f"   ✓ Scaled up to {aws_deployment.desired_instances} instances")

        # Demo 5: Load Balancer
        print("\n\n⚖️  DEMO 5: Load Balancer Configuration")
        print("-" * 80)

        print("\n1. Creating application load balancer...")
        lb = await MultiCloudService.create_load_balancer(
            db,
            LoadBalancerCreate(
                name="customer-service-lb",
                lb_type=LoadBalancerType.APPLICATION,
                provider=CloudProvider.AWS,
                is_public=True,
                ssl_enabled=True,
                deployment_ids=[aws_deployment.id],
                routing_algorithm="least_connections",
                sticky_sessions=True,
            ),
        )
        print(f"   ✓ Load balancer created: {lb.name}")
        print(f"   ✓ Type: {lb.lb_type}")
        print(f"   ✓ DNS: {lb.dns_name}")
        print(f"   ✓ SSL enabled: {lb.ssl_enabled}")
        print(f"   ✓ Routing: {lb.routing_algorithm}")

        # Demo 6: Deployment Metrics
        print("\n\n📈 DEMO 6: Deployment Metrics Tracking")
        print("-" * 80)

        print("\n1. Recording metrics for AWS deployment...")
        metrics1 = await MultiCloudService.record_metrics(
            db,
            aws_deployment.id,
            {
                "cpu_utilization_percent": 65.5,
                "memory_utilization_percent": 72.3,
                "request_count": 1250,
                "error_count": 5,
                "avg_response_time_ms": 145.2,
                "p95_response_time_ms": 320.5,
                "p99_response_time_ms": 450.8,
                "healthy_instances": 3,
                "unhealthy_instances": 0,
                "current_hourly_cost_usd": aws_deployment.estimated_hourly_cost_usd,
            },
        )
        print(f"   ✓ Metrics recorded")
        print(f"   ✓ CPU: {metrics1.cpu_utilization_percent}%")
        print(f"   ✓ Memory: {metrics1.memory_utilization_percent}%")
        print(f"   ✓ Requests: {metrics1.request_count}")
        print(f"   ✓ Avg response time: {metrics1.avg_response_time_ms}ms")
        print(f"   ✓ Healthy instances: {metrics1.healthy_instances}")

        # Demo 7: Deployment Scaling
        print("\n\n📏 DEMO 7: Manual Scaling")
        print("-" * 80)

        print(f"\n1. Current instances: {aws_deployment.desired_instances}")
        print("2. Scaling up to 5 instances...")
        aws_deployment = await MultiCloudService.scale_deployment(
            db, aws_deployment.id, 5
        )
        print(f"   ✓ Desired instances: {aws_deployment.desired_instances}")
        print(f"   ✓ Status: {aws_deployment.status}")

        # Demo 8: GCP Deployment
        print("\n\n🔵 DEMO 8: GCP Deployment")
        print("-" * 80)

        print("\n1. Deploying ML agent to GCP...")
        gcp_deployment = await MultiCloudService.create_deployment(
            db,
            DeploymentCreate(
                name="ml-inference-agent",
                agent_id=3,
                version="v1.0.0",
                cloud_account_id=gcp_account.id,
                provider=CloudProvider.GCP,
                region="us-central1",
                instance_type=InstanceType.GCP_N1_STANDARD_2,
                min_instances=1,
                max_instances=8,
                desired_instances=2,
                container_image="acme/ml-agent:v1.0.0",
                gpu_count=1,
            ),
            "admin_user",
        )
        print(f"   ✓ GCP deployment created: {gcp_deployment.name}")
        print(f"   ✓ GPUs: {gcp_deployment.gpu_count}")

        # Demo 9: Multi-Cloud Statistics
        print("\n\n📊 DEMO 9: Multi-Cloud Statistics")
        print("-" * 80)

        print("\n1. Getting overall statistics...")
        stats = await MultiCloudService.get_multi_cloud_stats(db)
        print(f"   Total deployments: {stats['total_deployments']}")
        print(f"   Running deployments: {stats['running_deployments']}")
        print(f"   Total instances: {stats['total_instances']}")
        print(f"   Estimated hourly cost: ${stats['estimated_hourly_cost_usd']:.2f}")
        print(f"   Estimated monthly cost: ${stats['estimated_monthly_cost_usd']:.2f}")
        print(f"\n   Deployments by provider:")
        for provider, count in stats['deployments_by_provider'].items():
            print(f"      - {provider}: {count}")

        # Demo 10: Deployment Termination
        print("\n\n🛑 DEMO 10: Deployment Lifecycle")
        print("-" * 80)

        print(f"\n1. Terminating deployment: {azure_deployment.name}")
        azure_deployment = await MultiCloudService.terminate_deployment(
            db, azure_deployment.id
        )
        print(f"   ✓ Status: {azure_deployment.status}")
        print(f"   ✓ Instances: {azure_deployment.current_instances}")

        # Summary
        print("\n\n" + "=" * 80)
        print("DEMO SUMMARY")
        print("=" * 80)
        print("\n✅ Multi-Cloud Features Demonstrated:")
        print("   - Cloud account registration (AWS, Azure, GCP, On-Premise)")
        print("   - Multi-region deployments")
        print("   - Multiple deployment strategies (rolling, blue-green)")
        print("   - Instance type selection per provider")
        print("   - Auto-scaling policies (CPU, memory, request-based)")
        print("   - Load balancer configuration")
        print("   - Real-time metrics tracking")
        print("   - Cost estimation and tracking")
        print("   - Deployment lifecycle management")
        print()
        print("✅ Supported Cloud Providers:")
        print("   - AWS (5 instance types)")
        print("   - Azure (4 instance types)")
        print("   - GCP (4 instance types)")
        print("   - On-Premise (3 configurations)")
        print()
        print("✅ Deployment Strategies:")
        print("   - Rolling updates (zero-downtime)")
        print("   - Blue-green deployments")
        print("   - Canary releases")
        print("   - A/B testing")
        print("   - Recreate")
        print()
        print("✅ Auto-Scaling Metrics:")
        print("   - CPU utilization")
        print("   - Memory utilization")
        print("   - Request count")
        print("   - Response time")
        print("   - Queue depth")
        print("   - Custom metrics")
        print()
        print("✅ Business Impact:")
        print("   - Vendor diversification (no lock-in)")
        print("   - High availability across clouds")
        print("   - Cost optimization through multi-cloud")
        print("   - Geographic distribution")
        print("   - Disaster recovery capabilities")
        print()
        print("🎉 Multi-Cloud Deployment enables global scale and resilience!")
        print()

if __name__ == "__main__":
    asyncio.run(demo_multicloud())

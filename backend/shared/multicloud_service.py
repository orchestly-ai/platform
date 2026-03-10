"""
Multi-Cloud Deployment Service - P2 Feature #2

Business logic for managing deployments across AWS, Azure, GCP, and on-premises infrastructure.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, String
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import secrets
import hashlib

from backend.shared.multicloud_models import *


class MultiCloudService:
    """Service for multi-cloud deployment operations"""

    # Cloud Account Management
    @staticmethod
    async def create_cloud_account(
        db: AsyncSession,
        account_data: CloudAccountCreate,
        created_by: str,
    ) -> CloudAccount:
        """Register a cloud provider account"""
        account = CloudAccount(
            **account_data.model_dump(),
            created_by=created_by,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def update_cloud_account(
        db: AsyncSession,
        account_id: int,
        account_data: CloudAccountUpdate,
    ) -> CloudAccount:
        """Update cloud account configuration"""
        result = await db.execute(select(CloudAccount).where(CloudAccount.id == account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError(f"Cloud account {account_id} not found")

        _ALLOWED_ACCOUNT_FIELDS = {
            "name", "provider", "region", "is_active", "credentials",
            "tags", "description", "config",
        }
        update_dict = account_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if key in _ALLOWED_ACCOUNT_FIELDS:
                setattr(account, key, value)

        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def get_cloud_accounts(
        db: AsyncSession,
        provider: Optional[CloudProvider] = None,
        is_active: bool = True,
    ) -> List[CloudAccount]:
        """List cloud accounts"""
        query = select(CloudAccount).where(CloudAccount.is_active == is_active)
        if provider:
            query = query.where(CloudAccount.provider == provider)
        
        result = await db.execute(query.order_by(CloudAccount.created_at.desc()))
        return list(result.scalars().all())

    # Deployment Management
    @staticmethod
    async def create_deployment(
        db: AsyncSession,
        deployment_data: DeploymentCreate,
        created_by: str,
    ) -> Deployment:
        """Create a new agent deployment"""
        # Estimate cost
        hourly_cost = MultiCloudService._estimate_hourly_cost(
            deployment_data.provider,
            deployment_data.instance_type,
            deployment_data.desired_instances,
        )

        deployment = Deployment(
            **deployment_data.model_dump(),
            status=DeploymentStatus.PENDING,
            estimated_hourly_cost_usd=hourly_cost,
            created_by=created_by,
        )
        db.add(deployment)
        await db.commit()
        await db.refresh(deployment)

        # Create deployment event
        await MultiCloudService._create_deployment_event(
            db,
            deployment.id,
            "deployment_created",
            "pending",
            f"Deployment created: {deployment.name}",
            created_by,
        )

        return deployment

    @staticmethod
    async def update_deployment(
        db: AsyncSession,
        deployment_id: int,
        deployment_data: DeploymentUpdate,
    ) -> Deployment:
        """Update deployment configuration"""
        result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        old_state = {"status": deployment.status if deployment.status else None}
        _ALLOWED_DEPLOY_FIELDS = {
            "name", "status", "cloud_account_id", "region", "config",
            "replicas", "instance_type", "tags", "description",
        }
        update_dict = deployment_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            if key in _ALLOWED_DEPLOY_FIELDS:
                setattr(deployment, key, value)

        new_state = {"status": deployment.status if deployment.status else None}

        await db.commit()
        await db.refresh(deployment)

        # Log event
        if old_state != new_state:
            await MultiCloudService._create_deployment_event(
                db,
                deployment.id,
                "deployment_updated",
                deployment.status,
                f"Deployment status changed to {deployment.status}",
                "system",
                old_state,
                new_state,
            )

        return deployment

    @staticmethod
    async def deploy(
        db: AsyncSession,
        deployment_id: int,
    ) -> Deployment:
        """Start deployment process"""
        result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        deployment.status = DeploymentStatus.PROVISIONING
        deployment.deployed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(deployment)

        await MultiCloudService._create_deployment_event(
            db, deployment.id, "deployment_started", "provisioning",
            f"Starting deployment to {deployment.provider} in {deployment.region}", "system"
        )

        return deployment

    @staticmethod
    async def scale_deployment(
        db: AsyncSession,
        deployment_id: int,
        desired_instances: int,
    ) -> Deployment:
        """Scale deployment to desired instance count"""
        result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        if desired_instances < deployment.min_instances or desired_instances > deployment.max_instances:
            raise ValueError(f"Desired instances must be between {deployment.min_instances} and {deployment.max_instances}")

        old_count = deployment.desired_instances
        deployment.desired_instances = desired_instances
        deployment.status = DeploymentStatus.UPDATING

        await db.commit()
        await db.refresh(deployment)

        await MultiCloudService._create_deployment_event(
            db, deployment.id, "deployment_scaled", "updating",
            f"Scaling from {old_count} to {desired_instances} instances", "system"
        )

        return deployment

    @staticmethod
    async def get_deployment(db: AsyncSession, deployment_id: int) -> Optional[Deployment]:
        """Get deployment by ID"""
        result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_deployments(
        db: AsyncSession,
        provider: Optional[CloudProvider] = None,
        status: Optional[DeploymentStatus] = None,
        agent_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Deployment]:
        """List deployments with filters"""
        query = select(Deployment)
        
        conditions = []
        if provider:
            conditions.append(Deployment.provider == provider)
        if status:
            conditions.append(Deployment.status.cast(String) == status.value if hasattr(status, 'value') else status)
        if agent_id:
            conditions.append(Deployment.agent_id == agent_id)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Deployment.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def terminate_deployment(
        db: AsyncSession,
        deployment_id: int,
    ) -> Deployment:
        """Terminate a deployment"""
        result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        deployment.status = DeploymentStatus.TERMINATED
        deployment.current_instances = 0

        await db.commit()
        await db.refresh(deployment)

        await MultiCloudService._create_deployment_event(
            db, deployment.id, "deployment_terminated", "terminated",
            "Deployment terminated", "system"
        )

        return deployment

    # Auto-Scaling Policies
    @staticmethod
    async def create_autoscaling_policy(
        db: AsyncSession,
        policy_data: AutoScalingPolicyCreate,
    ) -> AutoScalingPolicy:
        """Create auto-scaling policy"""
        policy = AutoScalingPolicy(**policy_data.model_dump())
        db.add(policy)
        await db.commit()
        await db.refresh(policy)
        return policy

    @staticmethod
    async def evaluate_autoscaling(
        db: AsyncSession,
        deployment_id: int,
        current_metrics: Dict[str, float],
    ) -> Optional[int]:
        """Evaluate auto-scaling policies and return desired instance count"""
        # Get active policies
        result = await db.execute(
            select(AutoScalingPolicy).where(
                and_(
                    AutoScalingPolicy.deployment_id == deployment_id,
                    AutoScalingPolicy.is_active == True
                )
            )
        )
        policies = list(result.scalars().all())

        # Get deployment
        result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        if not deployment:
            return None

        for policy in policies:
            # Check cooldown
            if policy.last_scaled_at:
                cooldown_end = policy.last_scaled_at + timedelta(seconds=policy.cooldown_period_seconds)
                if datetime.utcnow() < cooldown_end:
                    continue

            # Get metric value
            metric_value = current_metrics.get(policy.metric, 0.0)

            # Scale up
            if metric_value > policy.scale_up_threshold:
                new_count = min(
                    deployment.desired_instances + policy.scale_up_increment,
                    deployment.max_instances
                )
                if new_count != deployment.desired_instances:
                    policy.last_scaled_at = datetime.utcnow()
                    policy.scale_up_count += 1
                    await db.commit()
                    return new_count

            # Scale down
            elif metric_value < policy.scale_down_threshold:
                new_count = max(
                    deployment.desired_instances - policy.scale_down_increment,
                    deployment.min_instances
                )
                if new_count != deployment.desired_instances:
                    policy.last_scaled_at = datetime.utcnow()
                    policy.scale_down_count += 1
                    await db.commit()
                    return new_count

        return None

    # Load Balancers
    @staticmethod
    async def create_load_balancer(
        db: AsyncSession,
        lb_data: LoadBalancerCreate,
    ) -> LoadBalancer:
        """Create load balancer"""
        lb = LoadBalancer(**lb_data.model_dump())
        # Generate DNS name
        lb.dns_name = f"lb-{secrets.token_hex(8)}.{lb.provider}.example.com"
        db.add(lb)
        await db.commit()
        await db.refresh(lb)
        return lb

    @staticmethod
    async def get_load_balancers(
        db: AsyncSession,
        provider: Optional[CloudProvider] = None,
    ) -> List[LoadBalancer]:
        """List load balancers"""
        query = select(LoadBalancer)
        if provider:
            query = query.where(LoadBalancer.provider == provider)
        
        result = await db.execute(query.order_by(LoadBalancer.created_at.desc()))
        return list(result.scalars().all())

    # Metrics
    @staticmethod
    async def record_metrics(
        db: AsyncSession,
        deployment_id: int,
        metrics_data: Dict[str, Any],
    ) -> DeploymentMetrics:
        """Record deployment metrics"""
        metrics = DeploymentMetrics(
            deployment_id=deployment_id,
            **metrics_data
        )
        db.add(metrics)
        await db.commit()
        await db.refresh(metrics)
        return metrics

    @staticmethod
    async def get_deployment_metrics(
        db: AsyncSession,
        deployment_id: int,
        hours: int = 24,
    ) -> List[DeploymentMetrics]:
        """Get deployment metrics for time range"""
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await db.execute(
            select(DeploymentMetrics)
            .where(
                and_(
                    DeploymentMetrics.deployment_id == deployment_id,
                    DeploymentMetrics.timestamp >= since
                )
            )
            .order_by(DeploymentMetrics.timestamp.desc())
        )
        return list(result.scalars().all())

    # Multi-Cloud Statistics
    @staticmethod
    async def get_multi_cloud_stats(db: AsyncSession) -> Dict[str, Any]:
        """Get overall multi-cloud deployment statistics"""
        # Total deployments by provider
        result = await db.execute(
            select(
                Deployment.provider,
                func.count(Deployment.id).label("count")
            )
            .group_by(Deployment.provider)
        )
        deployments_by_provider = {row[0]: row[1] for row in result.all()}

        # Running deployments (cast to text for PostgreSQL enum compatibility)
        result = await db.execute(
            select(func.count(Deployment.id))
            .where(Deployment.status.cast(String) == DeploymentStatus.RUNNING.value)
        )
        running_count = result.scalar() or 0

        # Total instances
        result = await db.execute(
            select(func.sum(Deployment.current_instances))
        )
        total_instances = result.scalar() or 0

        # Total cost
        result = await db.execute(
            select(func.sum(Deployment.actual_cost_usd))
        )
        total_cost = float(result.scalar() or 0)

        # Estimated hourly cost
        result = await db.execute(
            select(func.sum(Deployment.estimated_hourly_cost_usd))
            .where(Deployment.status.cast(String) == DeploymentStatus.RUNNING.value)
        )
        hourly_cost = float(result.scalar() or 0)

        return {
            "deployments_by_provider": deployments_by_provider,
            "total_deployments": sum(deployments_by_provider.values()),
            "running_deployments": running_count,
            "total_instances": int(total_instances),
            "total_cost_usd": total_cost,
            "estimated_hourly_cost_usd": hourly_cost,
            "estimated_monthly_cost_usd": hourly_cost * 730,
        }

    # Helper methods
    @staticmethod
    async def _create_deployment_event(
        db: AsyncSession,
        deployment_id: int,
        event_type: str,
        status: str,
        message: str,
        triggered_by: str,
        old_state: Optional[Dict] = None,
        new_state: Optional[Dict] = None,
    ) -> DeploymentEvent:
        """Create deployment event"""
        event = DeploymentEvent(
            deployment_id=deployment_id,
            event_type=event_type,
            status=status,
            message=message,
            triggered_by=triggered_by,
            old_state=old_state,
            new_state=new_state,
        )
        db.add(event)
        await db.commit()
        return event

    @staticmethod
    def _estimate_hourly_cost(
        provider: CloudProvider,
        instance_type: InstanceType,
        instance_count: int,
    ) -> float:
        """Estimate hourly cost for deployment"""
        # Simplified cost estimation (in production, use cloud provider pricing APIs)
        cost_map = {
            # AWS
            "aws_t3_micro": 0.0104,
            "aws_t3_small": 0.0208,
            "aws_t3_medium": 0.0416,
            "aws_m5_large": 0.096,
            "aws_c5_xlarge": 0.17,
            # Azure
            "azure_b1s": 0.0104,
            "azure_b2s": 0.0416,
            "azure_d2s_v3": 0.096,
            "azure_f4s_v2": 0.169,
            # GCP
            "gcp_e2_micro": 0.008,
            "gcp_e2_small": 0.0167,
            "gcp_e2_medium": 0.0335,
            "gcp_n1_standard_2": 0.095,
            # On-premise (operational cost estimate)
            "on_prem_small": 0.02,
            "on_prem_medium": 0.05,
            "on_prem_large": 0.10,
        }
        
        unit_cost = cost_map.get(instance_type, 0.05)
        return unit_cost * instance_count

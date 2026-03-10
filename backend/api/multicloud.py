"""
Multi-Cloud Deployment API - P2 Feature #2

REST API for managing deployments across AWS, Azure, GCP, and on-premises infrastructure.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from backend.database.session import get_db
from backend.shared.multicloud_models import *
from backend.shared.multicloud_service import MultiCloudService
from backend.shared.auth import get_current_user_id

router = APIRouter(prefix="/api/v1/multicloud", tags=["multicloud"])

# Cloud Accounts
@router.post("/accounts", response_model=CloudAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_cloud_account(
    account_data: CloudAccountCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    account = await MultiCloudService.create_cloud_account(db, account_data, user_id)
    return account

@router.get("/accounts", response_model=List[CloudAccountResponse])
async def list_cloud_accounts(
    provider: Optional[CloudProvider] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    accounts = await MultiCloudService.get_cloud_accounts(db, provider)
    return accounts

# Deployments
@router.post("/deployments", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    deployment_data: DeploymentCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    deployment = await MultiCloudService.create_deployment(db, deployment_data, user_id)
    return deployment

@router.get("/deployments", response_model=List[DeploymentResponse])
async def list_deployments(
    provider: Optional[CloudProvider] = Query(None),
    status: Optional[DeploymentStatus] = Query(None),
    agent_id: Optional[int] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    deployments = await MultiCloudService.list_deployments(db, provider, status, agent_id, limit)
    return deployments

@router.get("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: int,
    db: AsyncSession = Depends(get_db),
):
    deployment = await MultiCloudService.get_deployment(db, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment

@router.post("/deployments/{deployment_id}/deploy")
async def deploy(
    deployment_id: int,
    db: AsyncSession = Depends(get_db),
):
    deployment = await MultiCloudService.deploy(db, deployment_id)
    return {"id": deployment.id, "status": deployment.status.value}

@router.post("/deployments/{deployment_id}/scale")
async def scale_deployment(
    deployment_id: int,
    desired_instances: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
):
    deployment = await MultiCloudService.scale_deployment(db, deployment_id, desired_instances)
    return {"id": deployment.id, "desired_instances": deployment.desired_instances}

@router.delete("/deployments/{deployment_id}")
async def terminate_deployment(
    deployment_id: int,
    db: AsyncSession = Depends(get_db),
):
    deployment = await MultiCloudService.terminate_deployment(db, deployment_id)
    return {"id": deployment.id, "status": deployment.status.value}

# Auto-Scaling
@router.post("/autoscaling", response_model=AutoScalingPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_autoscaling_policy(
    policy_data: AutoScalingPolicyCreate,
    db: AsyncSession = Depends(get_db),
):
    policy = await MultiCloudService.create_autoscaling_policy(db, policy_data)
    return policy

# Load Balancers
@router.post("/load-balancers", response_model=LoadBalancerResponse, status_code=status.HTTP_201_CREATED)
async def create_load_balancer(
    lb_data: LoadBalancerCreate,
    db: AsyncSession = Depends(get_db),
):
    lb = await MultiCloudService.create_load_balancer(db, lb_data)
    return lb

@router.get("/load-balancers", response_model=List[LoadBalancerResponse])
async def list_load_balancers(
    provider: Optional[CloudProvider] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    lbs = await MultiCloudService.get_load_balancers(db, provider)
    return lbs

# Metrics
@router.get("/deployments/{deployment_id}/metrics", response_model=List[DeploymentMetricsResponse])
async def get_deployment_metrics(
    deployment_id: int,
    hours: int = Query(24, le=168),
    db: AsyncSession = Depends(get_db),
):
    metrics = await MultiCloudService.get_deployment_metrics(db, deployment_id, hours)
    return metrics

# Statistics
@router.get("/stats")
async def get_multi_cloud_stats(db: AsyncSession = Depends(get_db)):
    stats = await MultiCloudService.get_multi_cloud_stats(db)
    return stats

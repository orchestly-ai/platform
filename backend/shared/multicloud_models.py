"""
Multi-Cloud Deployment Models - P2 Feature #2

Data models for deploying agents across AWS, Azure, GCP, and on-premises infrastructure.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

from backend.database.base import Base


# Enums
class CloudProvider(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ON_PREMISE = "on_premise"
    HYBRID = "hybrid"


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    DEPLOYING = "deploying"
    RUNNING = "running"
    UPDATING = "updating"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    TERMINATED = "terminated"


class DeploymentStrategy(str, Enum):
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    ROLLING = "rolling"
    RECREATE = "recreate"
    A_B_TEST = "a_b_test"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AutoScalingMetric(str, Enum):
    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_UTILIZATION = "memory_utilization"
    REQUEST_COUNT = "request_count"
    RESPONSE_TIME = "response_time"
    QUEUE_DEPTH = "queue_depth"
    CUSTOM = "custom"


class InstanceType(str, Enum):
    # AWS
    AWS_T3_MICRO = "aws_t3_micro"
    AWS_T3_SMALL = "aws_t3_small"
    AWS_T3_MEDIUM = "aws_t3_medium"
    AWS_M5_LARGE = "aws_m5_large"
    AWS_C5_XLARGE = "aws_c5_xlarge"
    # Azure
    AZURE_B1S = "azure_b1s"
    AZURE_B2S = "azure_b2s"
    AZURE_D2S_V3 = "azure_d2s_v3"
    AZURE_F4S_V2 = "azure_f4s_v2"
    # GCP
    GCP_E2_MICRO = "gcp_e2_micro"
    GCP_E2_SMALL = "gcp_e2_small"
    GCP_E2_MEDIUM = "gcp_e2_medium"
    GCP_N1_STANDARD_2 = "gcp_n1_standard_2"
    # On-premise
    ON_PREM_SMALL = "on_prem_small"
    ON_PREM_MEDIUM = "on_prem_medium"
    ON_PREM_LARGE = "on_prem_large"


class LoadBalancerType(str, Enum):
    APPLICATION = "application"
    NETWORK = "network"
    GATEWAY = "gateway"
    INTERNAL = "internal"


# SQLAlchemy Models
class CloudAccount(Base):
    """Cloud provider account credentials and configuration"""
    __tablename__ = "cloud_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)
    account_id = Column(String(255), nullable=False)
    region = Column(String(100), nullable=False)
    credentials_encrypted = Column(Text, nullable=True)  # Encrypted credentials
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Quotas and limits
    max_instances = Column(Integer, default=100)
    max_vcpus = Column(Integer, default=200)
    max_memory_gb = Column(Integer, default=512)
    
    # Usage tracking
    current_instances = Column(Integer, default=0)
    current_vcpus = Column(Integer, default=0)
    current_memory_gb = Column(Integer, default=0)
    
    # Cost tracking
    monthly_budget_usd = Column(Float, nullable=True)
    current_month_cost_usd = Column(Float, default=0.0)
    
    # Configuration
    tags = Column(JSON, default=dict)
    extra_metadata = Column("metadata", JSON, default=dict)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)


class Deployment(Base):
    """Agent deployment across cloud providers"""
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    agent_id = Column(Integer, nullable=False, index=True)
    version = Column(String(50), nullable=False)
    
    # Cloud configuration
    cloud_account_id = Column(Integer, ForeignKey("cloud_accounts.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)
    region = Column(String(100), nullable=False)
    availability_zones = Column(JSON, default=list)
    
    # Deployment configuration
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    strategy = Column(String(50), default="ROLLING", nullable=False)
    instance_type = Column(String(50), nullable=False)
    min_instances = Column(Integer, default=1, nullable=False)
    max_instances = Column(Integer, default=10, nullable=False)
    desired_instances = Column(Integer, default=1, nullable=False)
    current_instances = Column(Integer, default=0, nullable=False)
    
    # Container configuration
    container_image = Column(String(500), nullable=False)
    container_port = Column(Integer, default=8080)
    environment_variables = Column(JSON, default=dict)
    secrets = Column(JSON, default=dict)  # References to secret manager
    
    # Resource allocation
    cpu_units = Column(Integer, default=1024)  # milli-CPUs
    memory_mb = Column(Integer, default=2048)
    storage_gb = Column(Integer, default=10)
    gpu_count = Column(Integer, default=0)
    
    # Networking
    vpc_id = Column(String(255), nullable=True)
    subnet_ids = Column(JSON, default=list)
    security_group_ids = Column(JSON, default=list)
    load_balancer_dns = Column(String(500), nullable=True)
    internal_endpoint = Column(String(500), nullable=True)
    external_endpoint = Column(String(500), nullable=True)
    
    # Health and monitoring
    health_status = Column(String(50), default="UNKNOWN", nullable=False)
    health_check_path = Column(String(255), default="/health")
    health_check_interval_seconds = Column(Integer, default=30)
    
    # Deployment metadata
    deployed_at = Column(DateTime, nullable=True)
    deployment_duration_seconds = Column(Integer, nullable=True)
    last_health_check = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Cost tracking
    estimated_hourly_cost_usd = Column(Float, default=0.0)
    actual_cost_usd = Column(Float, default=0.0)
    
    # Configuration
    tags = Column(JSON, default=dict)
    extra_metadata = Column("metadata", JSON, default=dict)
    
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)


class AutoScalingPolicy(Base):
    """Auto-scaling policies for deployments"""
    __tablename__ = "autoscaling_policies"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Scaling configuration
    metric = Column(String(50), nullable=False)
    target_value = Column(Float, nullable=False)
    scale_up_threshold = Column(Float, nullable=False)
    scale_down_threshold = Column(Float, nullable=False)
    
    # Scaling behavior
    scale_up_increment = Column(Integer, default=1)
    scale_down_increment = Column(Integer, default=1)
    cooldown_period_seconds = Column(Integer, default=300)
    
    # Custom metric (if metric == CUSTOM)
    custom_metric_query = Column(Text, nullable=True)
    
    # Tracking
    last_scaled_at = Column(DateTime, nullable=True)
    scale_up_count = Column(Integer, default=0)
    scale_down_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class DeploymentEvent(Base):
    """Deployment lifecycle events and audit trail"""
    __tablename__ = "deployment_events"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    
    # Event details
    old_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    details = Column(JSON, default=dict)
    
    # Metadata
    triggered_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)


class LoadBalancer(Base):
    """Load balancer configuration for multi-region deployments"""
    __tablename__ = "load_balancers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    lb_type = Column(String(50), nullable=False)
    provider = Column(String(50), nullable=False)
    
    # Configuration
    dns_name = Column(String(500), nullable=True, index=True)
    is_public = Column(Boolean, default=True, nullable=False)
    ssl_enabled = Column(Boolean, default=True, nullable=False)
    ssl_certificate_arn = Column(String(500), nullable=True)
    
    # Target deployments
    deployment_ids = Column(JSON, default=list)
    
    # Routing
    routing_algorithm = Column(String(50), default="round_robin")
    sticky_sessions = Column(Boolean, default=False)
    health_check_enabled = Column(Boolean, default=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    health_status = Column(String(50), default="UNKNOWN")
    
    # Metrics
    total_requests = Column(Integer, default=0)
    active_connections = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class DeploymentMetrics(Base):
    """Real-time metrics for deployments"""
    __tablename__ = "deployment_metrics"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Resource metrics
    cpu_utilization_percent = Column(Float, default=0.0)
    memory_utilization_percent = Column(Float, default=0.0)
    disk_utilization_percent = Column(Float, default=0.0)
    network_in_mbps = Column(Float, default=0.0)
    network_out_mbps = Column(Float, default=0.0)
    
    # Performance metrics
    request_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    avg_response_time_ms = Column(Float, default=0.0)
    p95_response_time_ms = Column(Float, default=0.0)
    p99_response_time_ms = Column(Float, default=0.0)
    
    # Instance metrics
    healthy_instances = Column(Integer, default=0)
    unhealthy_instances = Column(Integer, default=0)
    
    # Cost
    current_hourly_cost_usd = Column(Float, default=0.0)
    
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)


# Pydantic Schemas
class CloudAccountCreate(BaseModel):
    name: str
    provider: CloudProvider
    account_id: str
    region: str
    credentials_encrypted: Optional[str] = None
    is_default: bool = False
    max_instances: int = 100
    max_vcpus: int = 200
    max_memory_gb: int = 512
    monthly_budget_usd: Optional[float] = None
    tags: Dict[str, Any] = Field(default_factory=dict)


class CloudAccountUpdate(BaseModel):
    name: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    max_instances: Optional[int] = None
    monthly_budget_usd: Optional[float] = None
    tags: Optional[Dict[str, Any]] = None


class CloudAccountResponse(BaseModel):
    id: int
    name: str
    provider: CloudProvider
    account_id: str
    region: str
    is_default: bool
    is_active: bool
    max_instances: int
    current_instances: int
    max_vcpus: int
    current_vcpus: int
    max_memory_gb: int
    current_memory_gb: int
    monthly_budget_usd: Optional[float]
    current_month_cost_usd: float
    created_at: datetime

    class Config:
        from_attributes = True


class DeploymentCreate(BaseModel):
    name: str
    agent_id: int
    version: str
    cloud_account_id: int
    provider: CloudProvider
    region: str
    availability_zones: List[str] = Field(default_factory=list)
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    instance_type: InstanceType
    min_instances: int = 1
    max_instances: int = 10
    desired_instances: int = 1
    container_image: str
    container_port: int = 8080
    environment_variables: Dict[str, str] = Field(default_factory=dict)
    cpu_units: int = 1024
    memory_mb: int = 2048
    storage_gb: int = 10
    gpu_count: int = 0
    health_check_path: str = "/health"
    tags: Dict[str, Any] = Field(default_factory=dict)


class DeploymentUpdate(BaseModel):
    status: Optional[DeploymentStatus] = None
    desired_instances: Optional[int] = None
    health_status: Optional[HealthStatus] = None
    error_message: Optional[str] = None
    external_endpoint: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None


class DeploymentResponse(BaseModel):
    id: int
    name: str
    agent_id: int
    version: str
    provider: CloudProvider
    region: str
    status: DeploymentStatus
    strategy: DeploymentStrategy
    instance_type: InstanceType
    min_instances: int
    max_instances: int
    desired_instances: int
    current_instances: int
    container_image: str
    health_status: HealthStatus
    external_endpoint: Optional[str]
    internal_endpoint: Optional[str]
    deployed_at: Optional[datetime]
    estimated_hourly_cost_usd: float
    actual_cost_usd: float
    created_at: datetime

    class Config:
        from_attributes = True


class AutoScalingPolicyCreate(BaseModel):
    deployment_id: int
    name: str
    metric: AutoScalingMetric
    target_value: float
    scale_up_threshold: float
    scale_down_threshold: float
    scale_up_increment: int = 1
    scale_down_increment: int = 1
    cooldown_period_seconds: int = 300
    custom_metric_query: Optional[str] = None


class AutoScalingPolicyResponse(BaseModel):
    id: int
    deployment_id: int
    name: str
    metric: AutoScalingMetric
    target_value: float
    scale_up_threshold: float
    scale_down_threshold: float
    is_active: bool
    last_scaled_at: Optional[datetime]
    scale_up_count: int
    scale_down_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class LoadBalancerCreate(BaseModel):
    name: str
    lb_type: LoadBalancerType
    provider: CloudProvider
    is_public: bool = True
    ssl_enabled: bool = True
    ssl_certificate_arn: Optional[str] = None
    deployment_ids: List[int] = Field(default_factory=list)
    routing_algorithm: str = "round_robin"
    sticky_sessions: bool = False


class LoadBalancerResponse(BaseModel):
    id: int
    name: str
    lb_type: LoadBalancerType
    provider: CloudProvider
    dns_name: Optional[str]
    is_public: bool
    ssl_enabled: bool
    deployment_ids: List[int]
    is_active: bool
    health_status: HealthStatus
    total_requests: int
    active_connections: int
    created_at: datetime

    class Config:
        from_attributes = True


class DeploymentMetricsResponse(BaseModel):
    deployment_id: int
    cpu_utilization_percent: float
    memory_utilization_percent: float
    request_count: int
    error_count: int
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    healthy_instances: int
    unhealthy_instances: int
    current_hourly_cost_usd: float
    timestamp: datetime

    class Config:
        from_attributes = True

"""
ML-Based Routing Optimization Models - P2 Feature #6

Data models for intelligent LLM routing using machine learning.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

from backend.database.base import Base


# Enums
class RoutingStrategy(str, Enum):
    COST_OPTIMIZED = "cost_optimized"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    BALANCED = "balanced"
    QUALITY_OPTIMIZED = "quality_optimized"
    LATENCY_OPTIMIZED = "latency_optimized"
    ML_PREDICTED = "ml_predicted"


class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    META = "meta"
    COHERE = "cohere"
    MISTRAL = "mistral"
    LOCAL = "local"


class OptimizationGoal(str, Enum):
    MINIMIZE_COST = "minimize_cost"
    MAXIMIZE_QUALITY = "maximize_quality"
    MINIMIZE_LATENCY = "minimize_latency"
    MAXIMIZE_THROUGHPUT = "maximize_throughput"
    BALANCED = "balanced"


class PredictionConfidence(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# SQLAlchemy Models
# NOTE: Renamed table from "llm_models" to "ml_routing_llm_models" to avoid conflict
# with the llm_models table in llm_models.py

class LLMModel(Base):
    """LLM model registry with capabilities and pricing for ML routing"""
    __tablename__ = "ml_routing_llm_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    provider = Column(String(50), nullable=False, index=True)  # Uses modelprovider PostgreSQL enum
    model_id = Column(String(255), nullable=False)

    # Capabilities
    max_tokens = Column(Integer, nullable=False)
    supports_functions = Column(Boolean, default=False)
    supports_vision = Column(Boolean, default=False)
    supports_streaming = Column(Boolean, default=True)

    # Performance characteristics
    avg_latency_ms = Column(Float, default=1000.0)
    avg_tokens_per_second = Column(Float, default=50.0)

    # Pricing (per 1M tokens)
    cost_per_1m_input_tokens = Column(Float, nullable=False)
    cost_per_1m_output_tokens = Column(Float, nullable=False)

    # Quality metrics
    quality_score = Column(Float, default=0.0)  # 0-100 scale
    success_rate = Column(Float, default=99.0)  # percentage (optimistic default for new models)

    # Usage statistics
    total_requests = Column(Integer, default=0)
    total_tokens_processed = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)

    # Availability
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_available = Column(Boolean, default=True)

    # Configuration
    tags = Column(JSON, default=dict)
    extra_metadata = Column(JSON, default=dict)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class RoutingPolicy(Base):
    """ML-based routing policy configuration"""
    __tablename__ = "routing_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Policy configuration
    strategy = Column(String(50), nullable=False, index=True)  # Uses routingstrategy PostgreSQL enum
    optimization_goal = Column(String(50), nullable=False)  # Uses optimizationgoal PostgreSQL enum
    
    # Model selection constraints
    allowed_providers = Column(JSON, default=list)  # List of ModelProvider
    allowed_models = Column(JSON, default=list)  # List of model IDs
    excluded_models = Column(JSON, default=list)
    
    # Cost constraints
    max_cost_per_request_usd = Column(Float, nullable=True)
    target_cost_reduction_percent = Column(Float, default=0.0)
    
    # Performance constraints
    max_latency_ms = Column(Float, nullable=True)
    min_quality_score = Column(Float, default=0.0)
    min_success_rate = Column(Float, default=90.0)
    
    # ML model configuration
    use_ml_prediction = Column(Boolean, default=True, nullable=False)
    ml_model_version = Column(String(50), nullable=True)
    confidence_threshold = Column(Float, default=0.7)
    
    # Fallback configuration
    fallback_model_id = Column(Integer, ForeignKey("ml_routing_llm_models.id"), nullable=True)
    fallback_strategy = Column(String(50), nullable=True)  # Strategy to use when primary fails
    enable_fallback = Column(Boolean, default=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Usage statistics
    total_requests = Column(Integer, default=0)
    total_cost_saved_usd = Column(Float, default=0.0)
    avg_cost_reduction_percent = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)


class RoutingDecision(Base):
    """Individual routing decisions made by ML model"""
    __tablename__ = "routing_decisions"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("routing_policies.id"), nullable=False, index=True)
    
    # Request context
    request_id = Column(String(255), unique=True, index=True)
    workflow_id = Column(Integer, nullable=True, index=True)
    agent_id = Column(Integer, nullable=True, index=True)
    
    # Input characteristics
    input_length_tokens = Column(Integer, nullable=False)
    expected_output_tokens = Column(Integer, default=0)
    task_type = Column(String(100), nullable=True, index=True)
    task_complexity = Column(Float, nullable=True)  # 0-1 scale
    requires_functions = Column(Boolean, default=False)
    requires_vision = Column(Boolean, default=False)
    
    # ML prediction
    predicted_model_id = Column(Integer, ForeignKey("ml_routing_llm_models.id"), nullable=False, index=True)
    prediction_confidence = Column(String(50), nullable=False)  # Uses predictionconfidence PostgreSQL enum
    confidence_score = Column(Float, nullable=False)  # 0-1
    prediction_features = Column(JSON, default=dict)
    
    # Alternative models considered
    candidate_models = Column(JSON, default=list)  # List of model IDs with scores
    
    # Actual execution
    actual_model_id = Column(Integer, ForeignKey("ml_routing_llm_models.id"), nullable=False)
    was_fallback = Column(Boolean, default=False)
    
    # Execution metrics
    actual_latency_ms = Column(Float, nullable=True)
    actual_input_tokens = Column(Integer, nullable=True)
    actual_output_tokens = Column(Integer, nullable=True)
    actual_cost_usd = Column(Float, nullable=True)
    success = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Predicted vs actual
    predicted_latency_ms = Column(Float, nullable=True)
    predicted_cost_usd = Column(Float, nullable=True)
    latency_error_percent = Column(Float, nullable=True)
    cost_error_percent = Column(Float, nullable=True)
    
    # Cost savings
    baseline_cost_usd = Column(Float, nullable=True)  # Cost if using default model
    cost_saved_usd = Column(Float, default=0.0)
    cost_reduction_percent = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)


class ModelPerformanceHistory(Base):
    """Historical performance data for ML training"""
    __tablename__ = "model_performance_history"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_routing_llm_models.id"), nullable=False, index=True)
    
    # Request characteristics
    task_type = Column(String(100), nullable=True, index=True)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    
    # Performance metrics
    latency_ms = Column(Float, nullable=False)
    cost_usd = Column(Float, nullable=False)
    success = Column(Boolean, nullable=False)
    quality_score = Column(Float, nullable=True)  # 0-1 if available
    
    # Context features
    time_of_day = Column(Integer, nullable=True)  # 0-23
    day_of_week = Column(Integer, nullable=True)  # 0-6
    load_level = Column(Float, nullable=True)  # System load 0-1
    
    # Error tracking
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)


class MLRoutingModel(Base):
    """ML model versions for routing optimization"""
    __tablename__ = "ml_routing_models"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(50), unique=True, nullable=False, index=True)
    algorithm = Column(String(100), nullable=False)
    
    # Training data
    training_samples = Column(Integer, default=0)
    training_start = Column(DateTime, nullable=True)
    training_end = Column(DateTime, nullable=True)
    
    # Model performance
    validation_accuracy = Column(Float, nullable=True)
    validation_cost_savings = Column(Float, nullable=True)
    validation_latency_error = Column(Float, nullable=True)
    
    # Model artifacts
    model_path = Column(String(500), nullable=True)
    feature_importance = Column(JSON, default=dict)
    hyperparameters = Column(JSON, default=dict)
    
    # Status
    is_active = Column(Boolean, default=False, nullable=False)
    is_production = Column(Boolean, default=False, nullable=False)
    
    # Usage
    total_predictions = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    deployed_at = Column(DateTime, nullable=True)


class CostOptimizationRule(Base):
    """Rule-based cost optimization fallbacks"""
    __tablename__ = "cost_optimization_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Rule conditions
    min_input_tokens = Column(Integer, nullable=True)
    max_input_tokens = Column(Integer, nullable=True)
    task_types = Column(JSON, default=list)
    
    # Model selection
    preferred_model_id = Column(Integer, ForeignKey("ml_routing_llm_models.id"), nullable=False)
    alternative_model_id = Column(Integer, ForeignKey("ml_routing_llm_models.id"), nullable=True)
    
    # Conditions
    max_acceptable_latency_ms = Column(Float, nullable=True)
    min_quality_threshold = Column(Float, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=100)
    
    # Usage
    times_applied = Column(Integer, default=0)
    total_cost_saved_usd = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)


# Pydantic Schemas
class LLMModelCreate(BaseModel):
    name: str
    provider: ModelProvider
    model_id: str
    max_tokens: int
    supports_functions: bool = False
    supports_vision: bool = False
    cost_per_1m_input_tokens: float
    cost_per_1m_output_tokens: float
    quality_score: float = 0.0
    tags: Dict[str, Any] = Field(default_factory=dict)


class LLMModelResponse(BaseModel):
    id: int
    name: str
    provider: ModelProvider
    model_id: str
    max_tokens: int
    supports_functions: bool
    supports_vision: bool
    avg_latency_ms: float
    cost_per_1m_input_tokens: float
    cost_per_1m_output_tokens: float
    quality_score: float
    success_rate: float
    total_requests: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RoutingPolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    strategy: RoutingStrategy
    optimization_goal: OptimizationGoal
    allowed_providers: List[ModelProvider] = Field(default_factory=list)
    allowed_models: List[int] = Field(default_factory=list)
    max_cost_per_request_usd: Optional[float] = None
    max_latency_ms: Optional[float] = None
    min_quality_score: float = 0.0
    use_ml_prediction: bool = True
    confidence_threshold: float = 0.7


class RoutingPolicyResponse(BaseModel):
    id: int
    name: str
    strategy: RoutingStrategy
    optimization_goal: OptimizationGoal
    use_ml_prediction: bool
    is_active: bool
    total_requests: int
    total_cost_saved_usd: float
    avg_cost_reduction_percent: float
    created_at: datetime

    class Config:
        from_attributes = True


class RouteRequest(BaseModel):
    policy_id: int
    request_id: str
    input_length_tokens: int
    expected_output_tokens: int = 0
    task_type: Optional[str] = None
    task_complexity: Optional[float] = None
    requires_functions: bool = False
    requires_vision: bool = False
    workflow_id: Optional[int] = None
    agent_id: Optional[int] = None


class RouteResponse(BaseModel):
    model_id: int
    model_name: str
    provider: str
    prediction_confidence: PredictionConfidence
    confidence_score: float
    estimated_latency_ms: float
    estimated_cost_usd: float
    decision_id: int
    reasoning: Dict[str, Any]


class RoutingDecisionResponse(BaseModel):
    id: int
    request_id: str
    predicted_model_id: int
    actual_model_id: int
    prediction_confidence: PredictionConfidence
    confidence_score: float
    actual_latency_ms: Optional[float]
    actual_cost_usd: Optional[float]
    cost_saved_usd: float
    success: Optional[bool]
    created_at: datetime

    class Config:
        from_attributes = True


class OptimizationStatsResponse(BaseModel):
    total_requests: int
    total_cost_saved_usd: float
    avg_cost_reduction_percent: float
    total_requests_by_provider: Dict[str, int]
    avg_latency_by_provider: Dict[str, float]
    success_rate_by_provider: Dict[str, float]

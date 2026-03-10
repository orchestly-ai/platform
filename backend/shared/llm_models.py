"""
Multi-LLM Routing Models - P1 Feature #3

Data models for multi-provider LLM support with smart routing.

Key Features:
- LLM provider registry (OpenAI, Anthropic, Google, Azure, local models)
- Smart routing based on cost/capability/latency
- Automatic fallback on failure
- Cost comparison across providers
- Quality scoring system
- A/B testing between models
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float, JSON,
    ForeignKey, Index, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from backend.database.base import Base


# Enums
class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    LOCAL_OLLAMA = "local_ollama"
    TOGETHER_AI = "together_ai"
    REPLICATE = "replicate"


class RoutingStrategy(str, Enum):
    """Routing strategies for LLM selection."""
    PRIMARY_ONLY = "PRIMARY_ONLY"
    PRIMARY_WITH_BACKUP = "PRIMARY_WITH_BACKUP"
    BEST_AVAILABLE = "BEST_AVAILABLE"
    COST_OPTIMIZED = "COST_OPTIMIZED"
    LATENCY_OPTIMIZED = "LATENCY_OPTIMIZED"


class ModelCapability(str, Enum):
    """Model capabilities for routing."""
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    FUNCTION_CALLING = "function_calling"
    JSON_MODE = "json_mode"
    VISION = "vision"
    LONG_CONTEXT = "long_context"  # >32K tokens
    REASONING = "reasoning"
    MULTILINGUAL = "multilingual"


# Database Models
class LLMProviderConfig(Base):
    """
    LLM provider configuration and credentials.
    """
    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, index=True)

    # Provider info
    provider = Column(SQLEnum(LLMProvider, name='llmprovider', values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    name = Column(String(255), nullable=False)  # Custom name
    description = Column(Text, nullable=True)

    # Organization
    organization_id = Column(Integer, nullable=True, index=True)
    created_by_user_id = Column(String(255), nullable=False)

    # Credentials (encrypted)
    api_key = Column(Text, nullable=True)  # Should be encrypted
    api_endpoint = Column(String(500), nullable=True)  # Custom endpoint
    additional_config = Column(JSON, default=dict)  # Provider-specific config

    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_default = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    models = relationship("LLMModelConfig", back_populates="provider")

    __table_args__ = (
        Index("ix_llm_providers_org_active", "organization_id", "is_active"),
    )


class LLMModelConfig(Base):
    """
    Individual LLM model configuration and pricing.
    """
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)

    # Provider reference
    provider_id = Column(Integer, ForeignKey("llm_providers.id"), nullable=False, index=True)

    # Model info
    model_name = Column(String(255), nullable=False, index=True)  # e.g., "gpt-4", "claude-3-opus"
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Capabilities
    capabilities = Column(JSON, default=list)  # List of ModelCapability values
    max_tokens = Column(Integer, default=4096)
    supports_streaming = Column(Boolean, default=True)
    supports_function_calling = Column(Boolean, default=False)

    # Pricing (per 1M tokens)
    input_cost_per_1m_tokens = Column(Float, nullable=False)
    output_cost_per_1m_tokens = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")

    # Performance metrics
    avg_latency_ms = Column(Float, default=0.0)  # Updated from actual usage
    avg_quality_score = Column(Float, default=0.0)  # 0.0-1.0
    success_rate = Column(Float, default=1.0)  # 0.0-1.0

    # Limits
    rate_limit_per_minute = Column(Integer, nullable=True)
    rate_limit_per_day = Column(Integer, nullable=True)
    max_concurrent_requests = Column(Integer, default=10)

    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_experimental = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    provider = relationship("LLMProviderConfig", back_populates="models")
    requests = relationship("LLMRequest", back_populates="model")

    __table_args__ = (
        Index("ix_llm_models_provider_active", "provider_id", "is_active"),
        Index("ix_llm_models_name", "model_name"),
        UniqueConstraint("provider_id", "model_name", name="uq_provider_model"),
    )


class LLMRequest(Base):
    """
    Tracks all LLM API requests for analytics and routing optimization.
    """
    __tablename__ = "llm_requests"

    id = Column(Integer, primary_key=True, index=True)

    # Model reference
    model_id = Column(Integer, ForeignKey("llm_models.id"), nullable=False, index=True)

    # Request info
    task_id = Column(Integer, nullable=True, index=True)  # Associated task
    workflow_id = Column(Integer, nullable=True, index=True)  # Associated workflow
    user_id = Column(String(255), nullable=False, index=True)
    organization_id = Column(Integer, nullable=True, index=True)

    # Request details
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)

    # Costs (calculated from model pricing)
    input_cost = Column(Float, nullable=False)
    output_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)

    # Performance
    latency_ms = Column(Float, nullable=False)
    was_cached = Column(Boolean, default=False)

    # Quality (if evaluated)
    quality_score = Column(Float, nullable=True)  # 0.0-1.0

    # Status
    status = Column(String(50), nullable=False, index=True)  # success, error, timeout
    error_message = Column(Text, nullable=True)

    # Routing info
    routing_strategy = Column(String(50), nullable=True, index=True)
    was_fallback = Column(Boolean, default=False)
    original_model_id = Column(Integer, nullable=True)  # If fallback occurred

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    model = relationship("LLMModelConfig", back_populates="requests")

    __table_args__ = (
        Index("ix_llm_requests_user_date", "user_id", "created_at"),
        Index("ix_llm_requests_org_date", "organization_id", "created_at"),
        Index("ix_llm_requests_model_status", "model_id", "status"),
    )


class LLMRoutingRule(Base):
    """
    Custom routing rules for specific use cases.
    """
    __tablename__ = "llm_routing_rules"

    id = Column(Integer, primary_key=True, index=True)

    # Rule info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Organization
    organization_id = Column(Integer, nullable=True, index=True)
    created_by_user_id = Column(String(255), nullable=False)

    # Rule conditions (JSON query)
    conditions = Column(JSON, nullable=False)  # e.g., {"task_type": "code_generation"}

    # Route to
    target_model_id = Column(Integer, ForeignKey("llm_models.id"), nullable=True)
    routing_strategy = Column(String(50), nullable=True)

    # Priority
    priority = Column(Integer, default=0, index=True)  # Higher = evaluated first

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_llm_routing_rules_org_active", "organization_id", "is_active"),
    )


class LLMModelComparison(Base):
    """
    A/B testing results for model comparisons.
    """
    __tablename__ = "llm_model_comparisons"

    id = Column(Integer, primary_key=True, index=True)

    # Comparison info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Models being compared
    model_a_id = Column(Integer, ForeignKey("llm_models.id"), nullable=False)
    model_b_id = Column(Integer, ForeignKey("llm_models.id"), nullable=False)

    # Organization
    organization_id = Column(Integer, nullable=True, index=True)
    created_by_user_id = Column(String(255), nullable=False)

    # Test configuration
    test_cases = Column(JSON, nullable=False)  # List of test prompts
    evaluation_criteria = Column(JSON, default=list)  # Criteria for scoring

    # Results
    model_a_avg_cost = Column(Float, nullable=True)
    model_b_avg_cost = Column(Float, nullable=True)
    model_a_avg_latency = Column(Float, nullable=True)
    model_b_avg_latency = Column(Float, nullable=True)
    model_a_avg_quality = Column(Float, nullable=True)
    model_b_avg_quality = Column(Float, nullable=True)

    # Winner
    winner_model_id = Column(Integer, nullable=True)
    confidence_score = Column(Float, nullable=True)  # 0.0-1.0

    # Status
    status = Column(String(50), default="pending", index=True)  # pending, running, completed
    completed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_llm_comparisons_status", "status"),
    )


# Pydantic Models for API
class LLMProviderCreate(BaseModel):
    """Create LLM provider config."""
    provider: LLMProvider
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    api_key: str  # Will be encrypted
    api_endpoint: Optional[str] = None
    additional_config: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class LLMProviderResponse(BaseModel):
    """LLM provider response."""
    id: int
    provider: LLMProvider
    name: str
    description: Optional[str]
    organization_id: Optional[int]
    api_endpoint: Optional[str]
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LLMModelCreate(BaseModel):
    """Create LLM model config."""
    provider_id: int
    model_name: str = Field(..., min_length=1, max_length=255)
    display_name: str
    description: Optional[str] = None
    capabilities: List[ModelCapability] = Field(default_factory=list)
    max_tokens: int = 4096
    supports_streaming: bool = True
    supports_function_calling: bool = False
    input_cost_per_1m_tokens: float
    output_cost_per_1m_tokens: float
    rate_limit_per_minute: Optional[int] = None
    rate_limit_per_day: Optional[int] = None


class LLMModelResponse(BaseModel):
    """LLM model response."""
    id: int
    provider_id: int
    model_name: str
    display_name: str
    description: Optional[str]
    capabilities: List[str]
    max_tokens: int
    supports_streaming: bool
    supports_function_calling: bool
    input_cost_per_1m_tokens: float
    output_cost_per_1m_tokens: float
    avg_latency_ms: float
    avg_quality_score: float
    success_rate: float
    is_active: bool
    is_experimental: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LLMRequestCreate(BaseModel):
    """Create LLM request (for logging)."""
    model_id: int
    task_id: Optional[int] = None
    workflow_id: Optional[int] = None
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    status: str
    error_message: Optional[str] = None
    routing_strategy: Optional[RoutingStrategy] = None
    was_fallback: bool = False
    original_model_id: Optional[int] = None


class LLMRoutingRequest(BaseModel):
    """Request LLM routing decision."""
    task_type: Optional[str] = None
    prompt: str
    max_tokens: int = 2000
    required_capabilities: List[ModelCapability] = Field(default_factory=list)
    routing_strategy: RoutingStrategy = RoutingStrategy.BEST_AVAILABLE
    max_cost: Optional[float] = None  # Maximum acceptable cost
    max_latency_ms: Optional[float] = None  # Maximum acceptable latency


class LLMRoutingResponse(BaseModel):
    """LLM routing decision."""
    selected_model_id: int
    selected_model_name: str
    provider: LLMProvider
    estimated_cost: float
    estimated_latency_ms: float
    estimated_quality_score: float
    routing_strategy_used: RoutingStrategy
    reasoning: str  # Why this model was selected
    fallback_model_ids: List[int]  # Fallback options


class LLMCostEstimate(BaseModel):
    """Cost estimate for LLM request."""
    model_id: int
    model_name: str
    provider: LLMProvider
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    currency: str


class ModelComparisonCreate(BaseModel):
    """Create model comparison test."""
    name: str
    description: Optional[str] = None
    model_a_id: int
    model_b_id: int
    test_cases: List[Dict[str, Any]]
    evaluation_criteria: List[str] = Field(default_factory=list)


class ModelComparisonResponse(BaseModel):
    """Model comparison results."""
    id: int
    name: str
    model_a_id: int
    model_b_id: int
    model_a_avg_cost: Optional[float]
    model_b_avg_cost: Optional[float]
    model_a_avg_latency: Optional[float]
    model_b_avg_latency: Optional[float]
    model_a_avg_quality: Optional[float]
    model_b_avg_quality: Optional[float]
    winner_model_id: Optional[int]
    confidence_score: Optional[float]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class RoutingStrategyRequest(BaseModel):
    """Request to set routing strategy."""
    strategy: RoutingStrategy
    config: Dict[str, Any] = Field(default_factory=dict)


class RoutingStrategyResponse(BaseModel):
    """Routing strategy response."""
    id: str
    organization_id: str
    strategy: RoutingStrategy
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

"""
Agent Memory Models - BYOS (Bring Your Own Storage)

Supports connecting to customer's own vector databases:
- Pinecone
- Weaviate
- Qdrant
- Redis (with vector search)
- Chroma (self-hosted)
- PostgreSQL with pgvector

We store ONLY the connection configuration (encrypted).
Actual memories are stored in customer's infrastructure.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Text, Integer,
    Float, Index
)

from backend.database.session import Base
from backend.shared.workflow_models import UniversalUUID, UniversalJSON


class MemoryProviderType(Enum):
    """Supported vector database providers"""
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    QDRANT = "qdrant"
    REDIS = "redis"
    CHROMA = "chroma"
    PGVECTOR = "pgvector"
    CUSTOM = "custom"  # For custom HTTP endpoints


class MemoryType(Enum):
    """Types of memories"""
    SHORT_TERM = "short_term"      # Within conversation/session
    LONG_TERM = "long_term"        # Across conversations
    EPISODIC = "episodic"          # Specific events/interactions
    SEMANTIC = "semantic"          # Facts and knowledge
    PROCEDURAL = "procedural"      # How to do things


class MemoryProviderConfigModel(Base):
    """
    Memory provider configuration per organization.

    Stores encrypted connection details for customer's vector DB.
    We never store the actual memories - just how to connect.
    """
    __tablename__ = "memory_provider_configs"

    # Primary key
    config_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Provider details
    provider_type = Column(String(50), nullable=False)  # pinecone, weaviate, etc.
    name = Column(String(255), nullable=False)  # Human-readable name
    description = Column(Text, nullable=True)

    # Connection configuration (encrypted at rest)
    # Structure varies by provider:
    # Pinecone: {"api_key": "...", "environment": "...", "index_name": "..."}
    # Weaviate: {"url": "...", "api_key": "...", "class_name": "..."}
    # Qdrant: {"url": "...", "api_key": "...", "collection_name": "..."}
    connection_config = Column(JSON, nullable=False)

    # Embedding configuration
    embedding_provider = Column(String(50), nullable=False, default="openai")
    embedding_model = Column(String(100), nullable=False, default="text-embedding-3-small")
    embedding_dimensions = Column(Integer, nullable=False, default=1536)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)  # Default for org
    last_health_check = Column(DateTime, nullable=True)
    health_status = Column(String(50), nullable=True)  # healthy, unhealthy, unknown

    # Usage stats
    total_memories = Column(Integer, nullable=False, default=0)
    total_queries = Column(Integer, nullable=False, default=0)

    # Metadata
    tags = Column(UniversalJSON(), nullable=True)
    extra_metadata = Column(JSON, nullable=True)

    # Audit
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_memory_provider_org', 'organization_id'),
        Index('idx_memory_provider_type', 'provider_type'),
        Index('idx_memory_provider_active', 'is_active'),
        Index('idx_memory_provider_default', 'organization_id', 'is_default'),
    )

    def __repr__(self):
        return f"<MemoryProviderConfig(id={self.config_id}, provider={self.provider_type}, name={self.name})>"


class AgentMemoryNamespaceModel(Base):
    """
    Memory namespaces for organizing memories.

    Allows separating memories by:
    - Agent (each agent has its own namespace)
    - User (memories about specific users)
    - Session (conversation-specific memories)
    - Custom (any user-defined namespace)
    """
    __tablename__ = "agent_memory_namespaces"

    # Primary key
    namespace_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Organization and provider
    organization_id = Column(String(255), nullable=False, index=True)
    provider_config_id = Column(UniversalUUID(), nullable=False, index=True)

    # Namespace details
    namespace = Column(String(255), nullable=False)  # e.g., "agent:sales-bot", "user:123"
    namespace_type = Column(String(50), nullable=False)  # agent, user, session, custom
    description = Column(Text, nullable=True)

    # Memory type configuration
    memory_types = Column(JSON, nullable=False, default=["long_term"])
    # Which memory types are enabled: ["short_term", "long_term", "episodic"]

    # Retention policy
    retention_days = Column(Integer, nullable=True)  # null = forever
    max_memories = Column(Integer, nullable=True)    # null = unlimited

    # Stats
    memory_count = Column(Integer, nullable=False, default=0)
    last_accessed = Column(DateTime, nullable=True)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_namespace_org', 'organization_id'),
        Index('idx_namespace_provider', 'provider_config_id'),
        Index('idx_namespace_name', 'organization_id', 'namespace'),
    )

    def __repr__(self):
        return f"<AgentMemoryNamespace(id={self.namespace_id}, namespace={self.namespace})>"


# Provider configuration schemas (for validation)
PROVIDER_CONFIG_SCHEMAS = {
    "pinecone": {
        "required": ["api_key", "index_name"],
        "optional": ["environment", "project_id", "namespace", "host"],
        "example": {
            "api_key": "your-pinecone-api-key",
            "index_name": "agent-memories",
            "environment": "us-east-1-aws",
        }
    },
    "weaviate": {
        "required": ["url"],
        "optional": ["api_key", "class_name", "additional_headers"],
        "example": {
            "url": "https://your-cluster.weaviate.network",
            "api_key": "your-weaviate-api-key",
            "class_name": "AgentMemory",
        }
    },
    "qdrant": {
        "required": ["url", "collection_name"],
        "optional": ["api_key", "grpc_port", "prefer_grpc"],
        "example": {
            "url": "https://your-cluster.qdrant.io",
            "api_key": "your-qdrant-api-key",
            "collection_name": "agent_memories",
        }
    },
    "redis": {
        "required": ["url", "index_name"],
        "optional": ["password", "ssl"],
        "example": {
            "url": "redis://localhost:6379",
            "index_name": "agent_memories",
            "password": "your-redis-password",
        }
    },
    "chroma": {
        "required": ["url"],
        "optional": ["api_key", "collection_name", "tenant", "database"],
        "example": {
            "url": "http://localhost:8000",
            "collection_name": "agent_memories",
        }
    },
    "pgvector": {
        "required": ["connection_string", "table_name"],
        "optional": ["schema"],
        "example": {
            "connection_string": "postgresql://user:pass@host:5432/db",
            "table_name": "agent_memories",
            "schema": "public",
        }
    },
    "custom": {
        "required": ["base_url"],
        "optional": ["api_key", "headers"],
        "example": {
            "base_url": "https://your-vector-api.com",
            "api_key": "your-api-key",
            "headers": {"X-Custom-Header": "value"},
        }
    },
    "demo": {
        "required": [],
        "optional": ["namespace_prefix"],
        "example": {
            "namespace_prefix": "demo",
        },
        "description": "Demo provider with in-memory storage for testing (no external services needed)"
    },
}


# Embedding provider configurations
EMBEDDING_PROVIDERS = {
    "openai": {
        "models": {
            "text-embedding-3-small": {"dimensions": 1536, "cost_per_1k": 0.00002},
            "text-embedding-3-large": {"dimensions": 3072, "cost_per_1k": 0.00013},
            "text-embedding-ada-002": {"dimensions": 1536, "cost_per_1k": 0.0001},
        }
    },
    "cohere": {
        "models": {
            "embed-english-v3.0": {"dimensions": 1024, "cost_per_1k": 0.0001},
            "embed-multilingual-v3.0": {"dimensions": 1024, "cost_per_1k": 0.0001},
        }
    },
    "voyage": {
        "models": {
            "voyage-2": {"dimensions": 1024, "cost_per_1k": 0.0001},
            "voyage-large-2": {"dimensions": 1536, "cost_per_1k": 0.00012},
        }
    },
    "local": {
        "models": {
            "all-MiniLM-L6-v2": {"dimensions": 384, "cost_per_1k": 0},
            "all-mpnet-base-v2": {"dimensions": 768, "cost_per_1k": 0},
        }
    },
}

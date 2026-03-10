"""
Memory API Endpoints - BYOS Memory Configuration and Operations

Endpoints for:
- Configuring memory providers (BYOS - Bring Your Own Storage)
- Managing memory namespaces
- Storing and retrieving agent memories

All memory data is stored in customer's infrastructure.
We only store the configuration for connecting.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from backend.database.session import AsyncSessionLocal
from backend.shared.memory_service import (
    MemoryService,
    MemoryServiceError,
    ProviderNotConfiguredError,
    InvalidProviderConfigError,
)
from backend.shared.memory_models import (
    PROVIDER_CONFIG_SCHEMAS,
    EMBEDDING_PROVIDERS,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


# ==================== Pydantic Models ====================

class ProviderConfigCreate(BaseModel):
    """Create a new memory provider configuration"""
    provider_type: str = Field(..., description="Type of vector database (pinecone, qdrant, weaviate, etc.)")
    name: str = Field(..., description="Human-readable name for this configuration")
    connection_config: Dict[str, Any] = Field(..., description="Connection configuration for the provider")
    embedding_provider: str = Field(default="openai", description="Embedding provider to use")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model to use")
    description: Optional[str] = None
    is_default: bool = Field(default=False, description="Set as default provider for organization")
    tags: Optional[List[str]] = None


class ProviderConfigUpdate(BaseModel):
    """Update a memory provider configuration"""
    name: Optional[str] = None
    description: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    tags: Optional[List[str]] = None


class ProviderConfigResponse(BaseModel):
    """Memory provider configuration response"""
    config_id: str
    organization_id: str
    provider_type: str
    name: str
    description: Optional[str]
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    is_active: bool
    is_default: bool
    health_status: Optional[str]
    last_health_check: Optional[datetime]
    total_memories: int
    total_queries: int
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime


class NamespaceCreate(BaseModel):
    """Create a memory namespace"""
    provider_config_id: str = Field(..., description="UUID of the provider config")
    namespace: str = Field(..., description="Namespace name (e.g., 'agent:sales-bot')")
    namespace_type: str = Field(default="custom", description="Type: agent, user, session, custom")
    description: Optional[str] = None
    memory_types: Optional[List[str]] = Field(default=["long_term"])
    retention_days: Optional[int] = None
    max_memories: Optional[int] = None


class NamespaceResponse(BaseModel):
    """Memory namespace response"""
    namespace_id: str
    organization_id: str
    provider_config_id: str
    namespace: str
    namespace_type: str
    description: Optional[str]
    memory_types: List[str]
    retention_days: Optional[int]
    max_memories: Optional[int]
    memory_count: int
    last_accessed: Optional[datetime]
    created_at: datetime


class MemoryStore(BaseModel):
    """Store a memory"""
    content: str = Field(..., description="The memory content to store")
    namespace: str = Field(default="default", description="Namespace to store in")
    memory_type: str = Field(default="long_term", description="Type of memory")
    metadata: Optional[Dict[str, Any]] = None
    provider_config_id: Optional[str] = None


class MemoryStoreBatch(BaseModel):
    """Store multiple memories"""
    memories: List[Dict[str, Any]] = Field(..., description="List of memories to store")
    provider_config_id: Optional[str] = None


class MemoryQuery(BaseModel):
    """Query for retrieving memories"""
    query: str = Field(..., description="Query text for similarity search")
    namespace: str = Field(default="default")
    memory_types: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    provider_config_id: Optional[str] = None


class MemoryResponse(BaseModel):
    """Memory response"""
    id: str
    content: str
    memory_type: str
    namespace: str
    metadata: Optional[Dict[str, Any]]
    created_at: Optional[datetime]
    score: Optional[float] = None


# ==================== Helper Functions ====================

async def get_db():
    """Get database session"""
    async with AsyncSessionLocal() as session:
        yield session


def get_org_id(x_organization_id: str = Header(default="default-org")) -> str:
    """Get organization ID from header"""
    return x_organization_id


def get_embedding_key(x_embedding_api_key: Optional[str] = Header(default=None)) -> Optional[str]:
    """Get embedding API key from header"""
    return x_embedding_api_key


# ==================== Provider Configuration Endpoints ====================

@router.get("/providers/schemas")
async def get_provider_schemas():
    """
    Get configuration schemas for all supported providers.

    Returns the required and optional fields for each provider type.
    """
    return {
        "providers": PROVIDER_CONFIG_SCHEMAS,
        "embedding_providers": EMBEDDING_PROVIDERS,
    }


@router.post("/providers", response_model=ProviderConfigResponse)
async def create_provider_config(
    config: ProviderConfigCreate,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """
    Create a new memory provider configuration.

    Configure your own vector database (BYOS - Bring Your Own Storage).
    Supports Pinecone, Qdrant, Weaviate, and more.
    """
    service = MemoryService(db)

    try:
        result = await service.create_provider_config(
            organization_id=org_id,
            provider_type=config.provider_type,
            name=config.name,
            connection_config=config.connection_config,
            embedding_provider=config.embedding_provider,
            embedding_model=config.embedding_model,
            description=config.description,
            is_default=config.is_default,
            tags=config.tags,
        )

        return ProviderConfigResponse(
            config_id=str(result.config_id),
            organization_id=result.organization_id,
            provider_type=result.provider_type,
            name=result.name,
            description=result.description,
            embedding_provider=result.embedding_provider,
            embedding_model=result.embedding_model,
            embedding_dimensions=result.embedding_dimensions,
            is_active=result.is_active,
            is_default=result.is_default,
            health_status=result.health_status,
            last_health_check=result.last_health_check,
            total_memories=result.total_memories,
            total_queries=result.total_queries,
            tags=result.tags,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    except InvalidProviderConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers", response_model=List[ProviderConfigResponse])
async def list_provider_configs(
    provider_type: Optional[str] = None,
    active_only: bool = True,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """
    List all memory provider configurations for the organization.
    """
    service = MemoryService(db)

    configs = await service.get_provider_configs(
        organization_id=org_id,
        provider_type=provider_type,
        active_only=active_only,
    )

    return [
        ProviderConfigResponse(
            config_id=str(c.config_id),
            organization_id=c.organization_id,
            provider_type=c.provider_type,
            name=c.name,
            description=c.description,
            embedding_provider=c.embedding_provider,
            embedding_model=c.embedding_model,
            embedding_dimensions=c.embedding_dimensions,
            is_active=c.is_active,
            is_default=c.is_default,
            health_status=c.health_status,
            last_health_check=c.last_health_check,
            total_memories=c.total_memories,
            total_queries=c.total_queries,
            tags=c.tags,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ]


@router.get("/providers/{config_id}", response_model=ProviderConfigResponse)
async def get_provider_config(
    config_id: str,
    db=Depends(get_db),
):
    """
    Get a specific memory provider configuration.
    """
    service = MemoryService(db)

    config = await service.get_provider_config(UUID(config_id))
    if not config:
        raise HTTPException(status_code=404, detail="Provider config not found")

    return ProviderConfigResponse(
        config_id=str(config.config_id),
        organization_id=config.organization_id,
        provider_type=config.provider_type,
        name=config.name,
        description=config.description,
        embedding_provider=config.embedding_provider,
        embedding_model=config.embedding_model,
        embedding_dimensions=config.embedding_dimensions,
        is_active=config.is_active,
        is_default=config.is_default,
        health_status=config.health_status,
        last_health_check=config.last_health_check,
        total_memories=config.total_memories,
        total_queries=config.total_queries,
        tags=config.tags,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.patch("/providers/{config_id}", response_model=ProviderConfigResponse)
async def update_provider_config(
    config_id: str,
    updates: ProviderConfigUpdate,
    db=Depends(get_db),
):
    """
    Update a memory provider configuration.
    """
    service = MemoryService(db)

    config = await service.update_provider_config(
        UUID(config_id),
        **updates.model_dump(exclude_none=True),
    )

    if not config:
        raise HTTPException(status_code=404, detail="Provider config not found")

    return ProviderConfigResponse(
        config_id=str(config.config_id),
        organization_id=config.organization_id,
        provider_type=config.provider_type,
        name=config.name,
        description=config.description,
        embedding_provider=config.embedding_provider,
        embedding_model=config.embedding_model,
        embedding_dimensions=config.embedding_dimensions,
        is_active=config.is_active,
        is_default=config.is_default,
        health_status=config.health_status,
        last_health_check=config.last_health_check,
        total_memories=config.total_memories,
        total_queries=config.total_queries,
        tags=config.tags,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.delete("/providers/{config_id}")
async def delete_provider_config(
    config_id: str,
    db=Depends(get_db),
):
    """
    Delete a memory provider configuration.
    """
    service = MemoryService(db)

    deleted = await service.delete_provider_config(UUID(config_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider config not found")

    return {"status": "deleted", "config_id": config_id}


@router.post("/providers/{config_id}/test")
async def test_provider_connection(
    config_id: str,
    db=Depends(get_db),
):
    """
    Test connection to a memory provider.

    Returns health status and latency.
    """
    service = MemoryService(db)

    result = await service.test_provider_connection(UUID(config_id))
    return result


# ==================== Namespace Endpoints ====================

@router.post("/namespaces", response_model=NamespaceResponse)
async def create_namespace(
    namespace: NamespaceCreate,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """
    Create a memory namespace.

    Namespaces organize memories by agent, user, session, or custom grouping.
    """
    service = MemoryService(db)

    result = await service.create_namespace(
        organization_id=org_id,
        provider_config_id=UUID(namespace.provider_config_id),
        namespace=namespace.namespace,
        namespace_type=namespace.namespace_type,
        description=namespace.description,
        memory_types=namespace.memory_types,
        retention_days=namespace.retention_days,
        max_memories=namespace.max_memories,
    )

    return NamespaceResponse(
        namespace_id=str(result.namespace_id),
        organization_id=result.organization_id,
        provider_config_id=str(result.provider_config_id),
        namespace=result.namespace,
        namespace_type=result.namespace_type,
        description=result.description,
        memory_types=result.memory_types,
        retention_days=result.retention_days,
        max_memories=result.max_memories,
        memory_count=result.memory_count,
        last_accessed=result.last_accessed,
        created_at=result.created_at,
    )


@router.get("/namespaces", response_model=List[NamespaceResponse])
async def list_namespaces(
    provider_config_id: Optional[str] = None,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """
    List all memory namespaces for the organization.
    """
    service = MemoryService(db)

    provider_uuid = UUID(provider_config_id) if provider_config_id else None
    namespaces = await service.get_namespaces(org_id, provider_uuid)

    return [
        NamespaceResponse(
            namespace_id=str(ns.namespace_id),
            organization_id=ns.organization_id,
            provider_config_id=str(ns.provider_config_id),
            namespace=ns.namespace,
            namespace_type=ns.namespace_type,
            description=ns.description,
            memory_types=ns.memory_types,
            retention_days=ns.retention_days,
            max_memories=ns.max_memories,
            memory_count=ns.memory_count,
            last_accessed=ns.last_accessed,
            created_at=ns.created_at,
        )
        for ns in namespaces
    ]


@router.delete("/namespaces/{namespace_id}")
async def delete_namespace(
    namespace_id: str,
    delete_memories: bool = False,
    db=Depends(get_db),
):
    """
    Delete a memory namespace.

    Optionally delete all memories in the namespace.
    """
    service = MemoryService(db)

    deleted = await service.delete_namespace(UUID(namespace_id), delete_memories)
    if not deleted:
        raise HTTPException(status_code=404, detail="Namespace not found")

    return {"status": "deleted", "namespace_id": namespace_id}


# ==================== Memory Operations ====================

@router.post("/store", response_model=Dict[str, str])
async def store_memory(
    memory: MemoryStore,
    org_id: str = Depends(get_org_id),
    embedding_key: Optional[str] = Depends(get_embedding_key),
    db=Depends(get_db),
):
    """
    Store a memory in the customer's vector database.

    The memory is embedded using the configured embedding model
    and stored in the configured vector database (BYOS).

    Pass the embedding API key in the X-Embedding-Api-Key header.
    """
    service = MemoryService(db)

    try:
        provider_uuid = UUID(memory.provider_config_id) if memory.provider_config_id else None

        memory_id = await service.store_memory(
            organization_id=org_id,
            content=memory.content,
            namespace=memory.namespace,
            memory_type=memory.memory_type,
            metadata=memory.metadata,
            provider_config_id=provider_uuid,
            embedding_api_key=embedding_key,
        )

        return {"memory_id": memory_id, "status": "stored"}
    except ProviderNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MemoryServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store/batch", response_model=Dict[str, Any])
async def store_memories_batch(
    batch: MemoryStoreBatch,
    org_id: str = Depends(get_org_id),
    embedding_key: Optional[str] = Depends(get_embedding_key),
    db=Depends(get_db),
):
    """
    Store multiple memories in batch.

    More efficient than storing one at a time.
    """
    service = MemoryService(db)

    try:
        provider_uuid = UUID(batch.provider_config_id) if batch.provider_config_id else None

        memory_ids = await service.store_memories_batch(
            organization_id=org_id,
            memories=batch.memories,
            provider_config_id=provider_uuid,
            embedding_api_key=embedding_key,
        )

        return {"memory_ids": memory_ids, "count": len(memory_ids), "status": "stored"}
    except ProviderNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MemoryServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=List[MemoryResponse])
async def query_memories(
    query: MemoryQuery,
    org_id: str = Depends(get_org_id),
    embedding_key: Optional[str] = Depends(get_embedding_key),
    db=Depends(get_db),
):
    """
    Query memories using semantic similarity search.

    Returns memories ranked by similarity to the query.
    """
    service = MemoryService(db)

    try:
        provider_uuid = UUID(query.provider_config_id) if query.provider_config_id else None

        memories = await service.retrieve_memories(
            organization_id=org_id,
            query=query.query,
            namespace=query.namespace,
            memory_types=query.memory_types,
            filters=query.filters,
            top_k=query.top_k,
            min_score=query.min_score,
            provider_config_id=provider_uuid,
            embedding_api_key=embedding_key,
        )

        return [
            MemoryResponse(
                id=m.id,
                content=m.content,
                memory_type=m.memory_type,
                namespace=m.namespace,
                metadata=m.metadata,
                created_at=m.created_at,
                score=m.score,
            )
            for m in memories
        ]
    except ProviderNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MemoryServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    namespace: str = "default",
    provider_config_id: Optional[str] = None,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """
    Get a specific memory by ID.
    """
    service = MemoryService(db)

    provider_uuid = UUID(provider_config_id) if provider_config_id else None

    memory = await service.get_memory(
        organization_id=org_id,
        memory_id=memory_id,
        namespace=namespace,
        provider_config_id=provider_uuid,
    )

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return MemoryResponse(
        id=memory.id,
        content=memory.content,
        memory_type=memory.memory_type,
        namespace=memory.namespace,
        metadata=memory.metadata,
        created_at=memory.created_at,
        score=None,
    )


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
    namespace: str = "default",
    provider_config_id: Optional[str] = None,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """
    Delete a specific memory.
    """
    service = MemoryService(db)

    provider_uuid = UUID(provider_config_id) if provider_config_id else None

    deleted = await service.delete_memory(
        organization_id=org_id,
        memory_id=memory_id,
        namespace=namespace,
        provider_config_id=provider_uuid,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found or failed to delete")

    return {"status": "deleted", "memory_id": memory_id}

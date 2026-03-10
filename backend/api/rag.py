"""
RAG API Endpoints - BYOD Document Retrieval

Endpoints for:
- Configuring document connectors (BYOD - Bring Your Own Data)
- Syncing and indexing documents
- Querying documents using semantic search

All document data remains in customer's infrastructure.
We only store configuration and index metadata.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from backend.database.session import AsyncSessionLocal
from backend.shared.rag_service import (
    RAGService,
    RAGServiceError,
    ConnectorNotConfiguredError,
    InvalidConnectorConfigError,
)
from backend.shared.rag_models import (
    RAG_PROVIDER_CONFIG_SCHEMAS,
    CHUNKING_CONFIGS,
)

router = APIRouter(prefix="/api/rag", tags=["rag"])


# ==================== Pydantic Models ====================

class ConnectorConfigCreate(BaseModel):
    """Create a new RAG connector configuration"""
    provider_type: str = Field(..., description="Type of document store (s3, elasticsearch, notion, etc.)")
    name: str = Field(..., description="Human-readable name")
    connection_config: Dict[str, Any] = Field(default_factory=dict, description="Connection configuration")
    chunking_strategy: str = Field(default="recursive", description="How to chunk documents")
    chunk_size: int = Field(default=1000, ge=100, le=10000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    memory_provider_id: Optional[str] = Field(None, description="Memory provider for vector storage")
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    description: Optional[str] = None
    is_default: bool = False
    tags: Optional[List[str]] = None


class ConnectorConfigUpdate(BaseModel):
    """Update a RAG connector configuration"""
    name: Optional[str] = None
    description: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    chunking_strategy: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    memory_provider_id: Optional[str] = None
    sync_enabled: Optional[bool] = None
    sync_interval_hours: Optional[int] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    tags: Optional[List[str]] = None


class ConnectorConfigResponse(BaseModel):
    """RAG connector configuration response"""
    config_id: str
    organization_id: str
    provider_type: str
    name: str
    description: Optional[str]
    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int
    memory_provider_id: Optional[str]
    embedding_provider: Optional[str]
    embedding_model: Optional[str]
    sync_enabled: bool
    sync_interval_hours: Optional[int]
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    last_sync_documents: Optional[int]
    is_active: bool
    is_default: bool
    health_status: Optional[str]
    last_health_check: Optional[datetime]
    total_documents: int
    total_chunks: int
    total_queries: int
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime


class DocumentIndexResponse(BaseModel):
    """Document index entry response"""
    document_id: str
    connector_id: str
    source_id: str
    source_path: Optional[str]
    source_type: str
    title: Optional[str]
    chunk_count: int
    index_status: str
    index_error: Optional[str]
    indexed_at: Optional[datetime]
    source_modified_at: Optional[datetime]
    needs_reindex: bool
    created_at: datetime


class RAGQueryRequest(BaseModel):
    """Query request for RAG search"""
    query: str = Field(..., description="Query text for semantic search")
    connector_id: Optional[str] = None
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = None


class RAGResultResponse(BaseModel):
    """RAG query result"""
    chunk_id: str
    document_id: str
    content: str
    score: float
    document_title: Optional[str]
    source_path: Optional[str]
    metadata: Optional[Dict[str, Any]]


class DocumentResponse(BaseModel):
    """Document from connector"""
    id: str
    source_id: str
    source_path: Optional[str]
    title: Optional[str]
    doc_type: str
    size_bytes: Optional[int]
    modified_at: Optional[datetime]


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


# ==================== Connector Configuration Endpoints ====================

@router.get("/connectors/schemas")
async def get_connector_schemas():
    """
    Get configuration schemas for all supported connectors.

    Returns the required and optional fields for each connector type.
    """
    return {
        "connectors": RAG_PROVIDER_CONFIG_SCHEMAS,
        "chunking_strategies": CHUNKING_CONFIGS,
    }


@router.post("/connectors", response_model=ConnectorConfigResponse)
async def create_connector_config(
    config: ConnectorConfigCreate,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """
    Create a new RAG connector configuration.

    Configure your own document store (BYOD - Bring Your Own Data).
    Supports S3, Elasticsearch, Notion, Confluence, and more.
    """
    service = RAGService(db)

    try:
        memory_uuid = UUID(config.memory_provider_id) if config.memory_provider_id else None

        result = await service.create_connector_config(
            organization_id=org_id,
            provider_type=config.provider_type,
            name=config.name,
            connection_config=config.connection_config,
            chunking_strategy=config.chunking_strategy,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            memory_provider_id=memory_uuid,
            embedding_provider=config.embedding_provider,
            embedding_model=config.embedding_model,
            description=config.description,
            is_default=config.is_default,
            tags=config.tags,
        )

        return ConnectorConfigResponse(
            config_id=str(result.config_id),
            organization_id=result.organization_id,
            provider_type=result.provider_type,
            name=result.name,
            description=result.description,
            chunking_strategy=result.chunking_strategy,
            chunk_size=result.chunk_size,
            chunk_overlap=result.chunk_overlap,
            memory_provider_id=str(result.memory_provider_id) if result.memory_provider_id else None,
            embedding_provider=result.embedding_provider,
            embedding_model=result.embedding_model,
            sync_enabled=result.sync_enabled,
            sync_interval_hours=result.sync_interval_hours,
            last_sync_at=result.last_sync_at,
            last_sync_status=result.last_sync_status,
            last_sync_documents=result.last_sync_documents,
            is_active=result.is_active,
            is_default=result.is_default,
            health_status=result.health_status,
            last_health_check=result.last_health_check,
            total_documents=result.total_documents,
            total_chunks=result.total_chunks,
            total_queries=result.total_queries,
            tags=result.tags,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    except InvalidConnectorConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connectors", response_model=List[ConnectorConfigResponse])
async def list_connector_configs(
    provider_type: Optional[str] = None,
    active_only: bool = True,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """List all RAG connector configurations for the organization."""
    service = RAGService(db)

    configs = await service.get_connector_configs(
        organization_id=org_id,
        provider_type=provider_type,
        active_only=active_only,
    )

    return [
        ConnectorConfigResponse(
            config_id=str(c.config_id),
            organization_id=c.organization_id,
            provider_type=c.provider_type,
            name=c.name,
            description=c.description,
            chunking_strategy=c.chunking_strategy,
            chunk_size=c.chunk_size,
            chunk_overlap=c.chunk_overlap,
            memory_provider_id=str(c.memory_provider_id) if c.memory_provider_id else None,
            embedding_provider=c.embedding_provider,
            embedding_model=c.embedding_model,
            sync_enabled=c.sync_enabled,
            sync_interval_hours=c.sync_interval_hours,
            last_sync_at=c.last_sync_at,
            last_sync_status=c.last_sync_status,
            last_sync_documents=c.last_sync_documents,
            is_active=c.is_active,
            is_default=c.is_default,
            health_status=c.health_status,
            last_health_check=c.last_health_check,
            total_documents=c.total_documents,
            total_chunks=c.total_chunks,
            total_queries=c.total_queries,
            tags=c.tags,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ]


@router.get("/connectors/{config_id}", response_model=ConnectorConfigResponse)
async def get_connector_config(
    config_id: str,
    db=Depends(get_db),
):
    """Get a specific RAG connector configuration."""
    service = RAGService(db)

    config = await service.get_connector_config(UUID(config_id))
    if not config:
        raise HTTPException(status_code=404, detail="Connector config not found")

    return ConnectorConfigResponse(
        config_id=str(config.config_id),
        organization_id=config.organization_id,
        provider_type=config.provider_type,
        name=config.name,
        description=config.description,
        chunking_strategy=config.chunking_strategy,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        memory_provider_id=str(config.memory_provider_id) if config.memory_provider_id else None,
        embedding_provider=config.embedding_provider,
        embedding_model=config.embedding_model,
        sync_enabled=config.sync_enabled,
        sync_interval_hours=config.sync_interval_hours,
        last_sync_at=config.last_sync_at,
        last_sync_status=config.last_sync_status,
        last_sync_documents=config.last_sync_documents,
        is_active=config.is_active,
        is_default=config.is_default,
        health_status=config.health_status,
        last_health_check=config.last_health_check,
        total_documents=config.total_documents,
        total_chunks=config.total_chunks,
        total_queries=config.total_queries,
        tags=config.tags,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.patch("/connectors/{config_id}", response_model=ConnectorConfigResponse)
async def update_connector_config(
    config_id: str,
    updates: ConnectorConfigUpdate,
    db=Depends(get_db),
):
    """Update a RAG connector configuration."""
    service = RAGService(db)

    update_data = updates.model_dump(exclude_none=True)
    if "memory_provider_id" in update_data:
        update_data["memory_provider_id"] = UUID(update_data["memory_provider_id"])

    config = await service.update_connector_config(UUID(config_id), **update_data)

    if not config:
        raise HTTPException(status_code=404, detail="Connector config not found")

    return ConnectorConfigResponse(
        config_id=str(config.config_id),
        organization_id=config.organization_id,
        provider_type=config.provider_type,
        name=config.name,
        description=config.description,
        chunking_strategy=config.chunking_strategy,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        memory_provider_id=str(config.memory_provider_id) if config.memory_provider_id else None,
        embedding_provider=config.embedding_provider,
        embedding_model=config.embedding_model,
        sync_enabled=config.sync_enabled,
        sync_interval_hours=config.sync_interval_hours,
        last_sync_at=config.last_sync_at,
        last_sync_status=config.last_sync_status,
        last_sync_documents=config.last_sync_documents,
        is_active=config.is_active,
        is_default=config.is_default,
        health_status=config.health_status,
        last_health_check=config.last_health_check,
        total_documents=config.total_documents,
        total_chunks=config.total_chunks,
        total_queries=config.total_queries,
        tags=config.tags,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.delete("/connectors/{config_id}")
async def delete_connector_config(
    config_id: str,
    db=Depends(get_db),
):
    """Delete a RAG connector configuration."""
    service = RAGService(db)

    deleted = await service.delete_connector_config(UUID(config_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Connector config not found")

    return {"status": "deleted", "config_id": config_id}


@router.post("/connectors/{config_id}/test")
async def test_connector_connection(
    config_id: str,
    db=Depends(get_db),
):
    """Test connection to a RAG connector."""
    service = RAGService(db)

    result = await service.test_connector_connection(UUID(config_id))
    return result


# ==================== Document Operations ====================

@router.get("/connectors/{config_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    config_id: str,
    prefix: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """List documents from a connector."""
    service = RAGService(db)

    try:
        documents = await service.list_documents(
            organization_id=org_id,
            connector_id=UUID(config_id),
            prefix=prefix,
            limit=limit,
            offset=offset,
        )

        return [
            DocumentResponse(
                id=doc.id,
                source_id=doc.source_id,
                source_path=doc.source_path,
                title=doc.title,
                doc_type=doc.doc_type,
                size_bytes=doc.size_bytes,
                modified_at=doc.modified_at,
            )
            for doc in documents
        ]
    except ConnectorNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connectors/{config_id}/sync")
async def sync_documents(
    config_id: str,
    full_sync: bool = False,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """
    Sync documents from connector to index.

    Discovers new documents and marks changed ones for reindexing.
    """
    service = RAGService(db)

    try:
        stats = await service.sync_documents(
            organization_id=org_id,
            connector_id=UUID(config_id),
            full_sync=full_sync,
        )
        return stats
    except ConnectorNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RAGServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connectors/{config_id}/documents/{source_id}/index")
async def index_document(
    config_id: str,
    source_id: str,
    org_id: str = Depends(get_org_id),
    embedding_key: Optional[str] = Depends(get_embedding_key),
    db=Depends(get_db),
):
    """
    Index a specific document.

    Fetches content, chunks it, generates embeddings, and stores in vector DB.
    """
    service = RAGService(db)

    try:
        result = await service.index_document(
            organization_id=org_id,
            connector_id=UUID(config_id),
            source_id=source_id,
            embedding_api_key=embedding_key,
        )
        return result
    except ConnectorNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RAGServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Index Management ====================

@router.get("/index", response_model=List[DocumentIndexResponse])
async def get_document_index(
    connector_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """Get document index entries."""
    service = RAGService(db)

    connector_uuid = UUID(connector_id) if connector_id else None

    entries = await service.get_document_index(
        organization_id=org_id,
        connector_id=connector_uuid,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [
        DocumentIndexResponse(
            document_id=str(e.document_id),
            connector_id=str(e.connector_id),
            source_id=e.source_id,
            source_path=e.source_path,
            source_type=e.source_type,
            title=e.title,
            chunk_count=e.chunk_count,
            index_status=e.index_status,
            index_error=e.index_error,
            indexed_at=e.indexed_at,
            source_modified_at=e.source_modified_at,
            needs_reindex=e.needs_reindex,
            created_at=e.created_at,
        )
        for e in entries
    ]


@router.get("/index/pending", response_model=List[DocumentIndexResponse])
async def get_pending_documents(
    connector_id: Optional[str] = None,
    limit: int = 100,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """Get documents pending indexing."""
    service = RAGService(db)

    connector_uuid = UUID(connector_id) if connector_id else None

    entries = await service.get_pending_documents(
        organization_id=org_id,
        connector_id=connector_uuid,
        limit=limit,
    )

    return [
        DocumentIndexResponse(
            document_id=str(e.document_id),
            connector_id=str(e.connector_id),
            source_id=e.source_id,
            source_path=e.source_path,
            source_type=e.source_type,
            title=e.title,
            chunk_count=e.chunk_count,
            index_status=e.index_status,
            index_error=e.index_error,
            indexed_at=e.indexed_at,
            source_modified_at=e.source_modified_at,
            needs_reindex=e.needs_reindex,
            created_at=e.created_at,
        )
        for e in entries
    ]


# ==================== Query Endpoints ====================

@router.post("/query", response_model=List[RAGResultResponse])
async def query_documents(
    query: RAGQueryRequest,
    org_id: str = Depends(get_org_id),
    embedding_key: Optional[str] = Depends(get_embedding_key),
    db=Depends(get_db),
):
    """
    Query documents using semantic search.

    Searches indexed documents using vector similarity.
    """
    service = RAGService(db)

    try:
        connector_uuid = UUID(query.connector_id) if query.connector_id else None

        results = await service.query(
            organization_id=org_id,
            query=query.query,
            connector_id=connector_uuid,
            top_k=query.top_k,
            min_score=query.min_score,
            filters=query.filters,
            embedding_api_key=embedding_key,
        )

        return [
            RAGResultResponse(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                content=r.content,
                score=r.score,
                document_title=r.document_title,
                source_path=r.source_path,
                metadata=r.metadata,
            )
            for r in results
        ]
    except ConnectorNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RAGServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connectors/{config_id}/search", response_model=List[DocumentResponse])
async def native_search(
    config_id: str,
    query: str,
    top_k: int = 10,
    org_id: str = Depends(get_org_id),
    db=Depends(get_db),
):
    """
    Search documents using the connector's native search.

    This is keyword/full-text search, not semantic search.
    """
    service = RAGService(db)

    try:
        documents = await service.native_search(
            organization_id=org_id,
            connector_id=UUID(config_id),
            query=query,
            top_k=top_k,
        )

        return [
            DocumentResponse(
                id=doc.id,
                source_id=doc.source_id,
                source_path=doc.source_path,
                title=doc.title,
                doc_type=doc.doc_type,
                size_bytes=doc.size_bytes,
                modified_at=doc.modified_at,
            )
            for doc in documents
        ]
    except ConnectorNotConfiguredError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

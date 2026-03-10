"""
RAG Service - BYOD Document Management

Service layer for RAG operations.
Handles document indexing, chunking, and retrieval coordination.

Key BYOD principles:
- We store only configuration and index metadata, not document content
- Documents remain in customer's infrastructure
- Embeddings are stored in customer's vector DB (BYOS)
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.rag_models import (
    RAGConnectorConfigModel,
    RAGDocumentIndexModel,
    RAGQueryHistoryModel,
    RAG_PROVIDER_CONFIG_SCHEMAS,
)
from backend.shared.rag_providers import (
    Document,
    DocumentChunk,
    RAGQuery,
    RAGResult,
    RAGProviderConfig,
    RAGProvider,
    RAGProviderError,
    TextChunker,
    create_rag_provider,
)
from backend.shared.memory_service import MemoryService, EmbeddingService
from backend.shared.memory_providers import Memory, MemoryQuery

logger = logging.getLogger(__name__)


class RAGServiceError(Exception):
    """Base exception for RAG service errors"""
    pass


class ConnectorNotConfiguredError(RAGServiceError):
    """Raised when no connector is configured"""
    pass


class InvalidConnectorConfigError(RAGServiceError):
    """Raised when connector configuration is invalid"""
    pass


class RAGService:
    """
    RAG service for managing document retrieval.

    Orchestrates:
    - Connector configuration management
    - Document listing and indexing
    - Chunking and embedding
    - Query execution
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._providers: Dict[str, RAGProvider] = {}

    # ==================== Connector Configuration ====================

    async def create_connector_config(
        self,
        organization_id: str,
        provider_type: str,
        name: str,
        connection_config: Dict[str, Any],
        chunking_strategy: str = "recursive",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        memory_provider_id: Optional[UUID] = None,
        embedding_provider: Optional[str] = None,
        embedding_model: Optional[str] = None,
        description: Optional[str] = None,
        is_default: bool = False,
        created_by: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> RAGConnectorConfigModel:
        """Create a new RAG connector configuration."""
        # Validate provider type
        if provider_type not in RAG_PROVIDER_CONFIG_SCHEMAS:
            raise InvalidConnectorConfigError(
                f"Unknown provider type: {provider_type}. "
                f"Supported: {list(RAG_PROVIDER_CONFIG_SCHEMAS.keys())}"
            )

        # Validate connection config
        schema = RAG_PROVIDER_CONFIG_SCHEMAS[provider_type]
        for required_field in schema["required"]:
            if required_field not in connection_config:
                raise InvalidConnectorConfigError(
                    f"Missing required field '{required_field}' for {provider_type}. "
                    f"Required: {schema['required']}"
                )

        # If setting as default, unset other defaults
        if is_default:
            await self.db.execute(
                update(RAGConnectorConfigModel)
                .where(RAGConnectorConfigModel.organization_id == organization_id)
                .where(RAGConnectorConfigModel.is_default == True)
                .values(is_default=False)
            )

        # Create config
        config = RAGConnectorConfigModel(
            config_id=uuid4(),
            organization_id=organization_id,
            provider_type=provider_type,
            name=name,
            description=description,
            connection_config=connection_config,
            chunking_strategy=chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            memory_provider_id=memory_provider_id,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            is_default=is_default,
            created_by=created_by,
            tags=tags,
        )

        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)

        # Test connection
        try:
            provider = await self._get_provider(config)
            health = await provider.health_check()
            config.health_status = health.get("status", "unknown")
            config.last_health_check = datetime.utcnow()
            await self.db.commit()
        except Exception as e:
            logger.warning(f"Connector health check failed: {e}")
            config.health_status = "unhealthy"
            await self.db.commit()

        return config

    async def get_connector_configs(
        self,
        organization_id: str,
        provider_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[RAGConnectorConfigModel]:
        """Get all connector configs for an organization."""
        query = select(RAGConnectorConfigModel).where(
            RAGConnectorConfigModel.organization_id == organization_id
        )

        if provider_type:
            query = query.where(RAGConnectorConfigModel.provider_type == provider_type)

        if active_only:
            query = query.where(RAGConnectorConfigModel.is_active == True)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_connector_config(
        self,
        config_id: UUID,
    ) -> Optional[RAGConnectorConfigModel]:
        """Get a specific connector config."""
        result = await self.db.execute(
            select(RAGConnectorConfigModel)
            .where(RAGConnectorConfigModel.config_id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_default_connector(
        self,
        organization_id: str,
    ) -> Optional[RAGConnectorConfigModel]:
        """Get the default connector for an organization."""
        result = await self.db.execute(
            select(RAGConnectorConfigModel)
            .where(RAGConnectorConfigModel.organization_id == organization_id)
            .where(RAGConnectorConfigModel.is_default == True)
            .where(RAGConnectorConfigModel.is_active == True)
        )
        return result.scalar_one_or_none()

    async def update_connector_config(
        self,
        config_id: UUID,
        **updates,
    ) -> Optional[RAGConnectorConfigModel]:
        """Update a connector configuration."""
        config = await self.get_connector_config(config_id)
        if not config:
            return None

        allowed_fields = {
            "name", "description", "connection_config", "chunking_strategy",
            "chunk_size", "chunk_overlap", "memory_provider_id",
            "embedding_provider", "embedding_model", "sync_enabled",
            "sync_interval_hours", "is_active", "is_default", "tags", "extra_metadata"
        }

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(config, field, value)

        config.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(config)

        return config

    async def delete_connector_config(self, config_id: UUID) -> bool:
        """Delete a connector configuration."""
        config = await self.get_connector_config(config_id)
        if not config:
            return False

        await self.db.delete(config)
        await self.db.commit()
        return True

    async def test_connector_connection(
        self,
        config_id: UUID,
    ) -> Dict[str, Any]:
        """Test connection to a connector."""
        config = await self.get_connector_config(config_id)
        if not config:
            return {"status": "error", "error": "Config not found"}

        try:
            provider = await self._get_provider(config)
            health = await provider.health_check()

            config.health_status = health.get("status", "unknown")
            config.last_health_check = datetime.utcnow()
            await self.db.commit()

            return health
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    # ==================== Document Operations ====================

    async def list_documents(
        self,
        organization_id: str,
        connector_id: UUID,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Document]:
        """List documents from a connector."""
        config = await self.get_connector_config(connector_id)
        if not config:
            raise ConnectorNotConfiguredError("Connector not found")

        provider = await self._get_provider(config)
        return await provider.list_documents(prefix, limit, offset)

    async def get_document(
        self,
        organization_id: str,
        connector_id: UUID,
        source_id: str,
    ) -> Optional[Document]:
        """Get a specific document from a connector."""
        config = await self.get_connector_config(connector_id)
        if not config:
            return None

        provider = await self._get_provider(config)
        return await provider.get_document(source_id)

    async def sync_documents(
        self,
        organization_id: str,
        connector_id: UUID,
        full_sync: bool = False,
    ) -> Dict[str, Any]:
        """
        Sync documents from connector to index.

        Returns stats about the sync operation.
        """
        config = await self.get_connector_config(connector_id)
        if not config:
            raise ConnectorNotConfiguredError("Connector not found")

        provider = await self._get_provider(config)

        stats = {
            "total_documents": 0,
            "new_documents": 0,
            "updated_documents": 0,
            "unchanged_documents": 0,
            "errors": 0,
        }

        try:
            # List all documents
            documents = await provider.list_documents(limit=10000)
            stats["total_documents"] = len(documents)

            for doc in documents:
                try:
                    # Check if document exists in index
                    existing = await self._get_document_index(
                        connector_id, doc.source_id
                    )

                    if existing:
                        # Check if document changed
                        if doc.modified_at and existing.source_modified_at:
                            if doc.modified_at > existing.source_modified_at:
                                existing.needs_reindex = True
                                existing.source_modified_at = doc.modified_at
                                stats["updated_documents"] += 1
                            else:
                                stats["unchanged_documents"] += 1
                        else:
                            stats["unchanged_documents"] += 1
                        existing.last_checked_at = datetime.utcnow()
                    else:
                        # Create new index entry
                        index_entry = RAGDocumentIndexModel(
                            document_id=uuid4(),
                            organization_id=organization_id,
                            connector_id=connector_id,
                            source_id=doc.source_id,
                            source_path=doc.source_path,
                            source_type=doc.doc_type,
                            title=doc.title,
                            size_bytes=doc.size_bytes,
                            source_modified_at=doc.modified_at,
                            last_checked_at=datetime.utcnow(),
                            index_status="pending",
                            source_metadata=doc.metadata,
                        )
                        self.db.add(index_entry)
                        stats["new_documents"] += 1

                except Exception as e:
                    logger.error(f"Error syncing document {doc.source_id}: {e}")
                    stats["errors"] += 1

            # Update sync status
            config.last_sync_at = datetime.utcnow()
            config.last_sync_status = "success" if stats["errors"] == 0 else "partial"
            config.last_sync_documents = stats["total_documents"]
            config.total_documents = stats["total_documents"]

            await self.db.commit()

        except Exception as e:
            config.last_sync_status = "failed"
            config.last_sync_at = datetime.utcnow()
            await self.db.commit()
            raise RAGServiceError(f"Sync failed: {e}")

        return stats

    async def index_document(
        self,
        organization_id: str,
        connector_id: UUID,
        source_id: str,
        embedding_api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Index a specific document: fetch, chunk, embed, store.

        Uses the configured memory provider (BYOS) for vector storage.
        """
        config = await self.get_connector_config(connector_id)
        if not config:
            raise ConnectorNotConfiguredError("Connector not found")

        # Get document index entry
        index_entry = await self._get_document_index(connector_id, source_id)
        if not index_entry:
            raise RAGServiceError(f"Document {source_id} not found in index")

        try:
            index_entry.index_status = "indexing"
            await self.db.commit()

            # Get document content
            provider = await self._get_provider(config)
            content = await provider.get_document_content(source_id)

            if not content:
                raise RAGServiceError("Failed to get document content")

            # Generate content hash
            content_hash = provider._generate_content_hash(content)

            # Check if content changed
            if index_entry.content_hash == content_hash and not index_entry.needs_reindex:
                index_entry.index_status = "indexed"
                index_entry.indexed_at = datetime.utcnow()
                await self.db.commit()
                return {"status": "unchanged", "chunks": index_entry.chunk_count}

            # Chunk the document
            chunks = TextChunker.chunk_recursive(
                content,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
            )

            # Store chunks in memory provider (BYOS)
            if config.memory_provider_id:
                memory_service = MemoryService(self.db)

                memories = []
                for i, chunk_text in enumerate(chunks):
                    memories.append({
                        "content": chunk_text,
                        "namespace": f"rag:{connector_id}:{source_id}",
                        "memory_type": "semantic",
                        "metadata": {
                            "document_id": str(index_entry.document_id),
                            "source_id": source_id,
                            "source_path": index_entry.source_path,
                            "title": index_entry.title,
                            "chunk_index": i,
                            "connector_id": str(connector_id),
                        },
                    })

                chunk_ids = await memory_service.store_memories_batch(
                    organization_id=organization_id,
                    memories=memories,
                    provider_config_id=config.memory_provider_id,
                    embedding_api_key=embedding_api_key,
                )

                index_entry.chunk_count = len(chunk_ids)
            else:
                index_entry.chunk_count = len(chunks)

            # Update index entry
            index_entry.content_hash = content_hash
            index_entry.index_status = "indexed"
            index_entry.indexed_at = datetime.utcnow()
            index_entry.needs_reindex = False
            index_entry.index_error = None

            # Update connector stats
            config.total_chunks += index_entry.chunk_count

            await self.db.commit()

            return {
                "status": "indexed",
                "chunks": index_entry.chunk_count,
                "content_hash": content_hash,
            }

        except Exception as e:
            index_entry.index_status = "error"
            index_entry.index_error = str(e)
            await self.db.commit()
            raise RAGServiceError(f"Indexing failed: {e}")

    # ==================== Query Operations ====================

    async def query(
        self,
        organization_id: str,
        query: str,
        connector_id: Optional[UUID] = None,
        top_k: int = 10,
        min_score: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
        embedding_api_key: Optional[str] = None,
        workflow_execution_id: Optional[UUID] = None,
        agent_id: Optional[str] = None,
    ) -> List[RAGResult]:
        """
        Query documents using semantic search.

        Uses the memory provider (BYOS) for vector search.
        """
        # Get connector config
        if connector_id:
            config = await self.get_connector_config(connector_id)
        else:
            config = await self.get_default_connector(organization_id)

        if not config:
            raise ConnectorNotConfiguredError("No connector configured")

        if not config.memory_provider_id:
            raise RAGServiceError("Connector has no memory provider configured for vector search")

        start_time = datetime.utcnow()

        # Use memory service for vector search
        memory_service = MemoryService(self.db)

        # Build namespace filter for this connector
        namespace = f"rag:{config.config_id}:"

        memories = await memory_service.retrieve_memories(
            organization_id=organization_id,
            query=query,
            namespace=namespace,
            top_k=top_k,
            min_score=min_score,
            filters=filters,
            provider_config_id=config.memory_provider_id,
            embedding_api_key=embedding_api_key,
        )

        # Convert to RAG results
        results = []
        for mem in memories:
            results.append(RAGResult(
                chunk_id=mem.id,
                document_id=mem.metadata.get("document_id", "") if mem.metadata else "",
                content=mem.content,
                score=mem.score or 0.0,
                metadata=mem.metadata,
                document_title=mem.metadata.get("title") if mem.metadata else None,
                source_path=mem.metadata.get("source_path") if mem.metadata else None,
            ))

        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Log query history
        query_history = RAGQueryHistoryModel(
            query_id=uuid4(),
            organization_id=organization_id,
            connector_id=connector_id,
            query_text=query,
            query_type="similarity",
            results_count=len(results),
            top_score=results[0].score if results else None,
            avg_score=sum(r.score for r in results) / len(results) if results else None,
            latency_ms=latency_ms,
            workflow_execution_id=workflow_execution_id,
            agent_id=agent_id,
        )
        self.db.add(query_history)

        # Update connector stats
        config.total_queries += 1
        await self.db.commit()

        return results

    async def native_search(
        self,
        organization_id: str,
        connector_id: UUID,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Search documents using the provider's native search.

        This is keyword/full-text search, not semantic search.
        """
        config = await self.get_connector_config(connector_id)
        if not config:
            raise ConnectorNotConfiguredError("Connector not found")

        provider = await self._get_provider(config)
        return await provider.search(query, top_k, filters)

    # ==================== Index Management ====================

    async def get_document_index(
        self,
        organization_id: str,
        connector_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RAGDocumentIndexModel]:
        """Get document index entries."""
        query = select(RAGDocumentIndexModel).where(
            RAGDocumentIndexModel.organization_id == organization_id
        )

        if connector_id:
            query = query.where(RAGDocumentIndexModel.connector_id == connector_id)

        if status:
            query = query.where(RAGDocumentIndexModel.index_status == status)

        query = query.order_by(RAGDocumentIndexModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_pending_documents(
        self,
        organization_id: str,
        connector_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> List[RAGDocumentIndexModel]:
        """Get documents pending indexing."""
        query = select(RAGDocumentIndexModel).where(
            RAGDocumentIndexModel.organization_id == organization_id
        ).where(
            (RAGDocumentIndexModel.index_status == "pending") |
            (RAGDocumentIndexModel.needs_reindex == True)
        )

        if connector_id:
            query = query.where(RAGDocumentIndexModel.connector_id == connector_id)

        query = query.limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ==================== Private Methods ====================

    async def _get_document_index(
        self,
        connector_id: UUID,
        source_id: str,
    ) -> Optional[RAGDocumentIndexModel]:
        """Get a document index entry by connector and source ID."""
        result = await self.db.execute(
            select(RAGDocumentIndexModel)
            .where(RAGDocumentIndexModel.connector_id == connector_id)
            .where(RAGDocumentIndexModel.source_id == source_id)
        )
        return result.scalar_one_or_none()

    async def _get_provider(
        self,
        config: RAGConnectorConfigModel,
    ) -> RAGProvider:
        """Get or create a provider instance."""
        cache_key = str(config.config_id)

        if cache_key not in self._providers:
            provider_config = RAGProviderConfig(
                provider_type=config.provider_type,
                connection_config=config.connection_config,
                chunking_strategy=config.chunking_strategy,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
            )

            provider = create_rag_provider(provider_config)
            connected = await provider.connect()

            if not connected:
                raise RAGProviderError(
                    f"Failed to connect to {config.provider_type} provider"
                )

            self._providers[cache_key] = provider

        return self._providers[cache_key]

    async def close(self):
        """Close all provider connections."""
        for provider in self._providers.values():
            try:
                await provider.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting provider: {e}")

        self._providers.clear()

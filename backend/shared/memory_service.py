"""
Memory Service - BYOS Memory Management

Service layer for agent memory operations.
Handles embedding generation and coordinates with memory providers.

Key BYOS principles:
- We store only configuration, not memory data
- Embeddings are generated using customer's API keys
- All vector data lives in customer's infrastructure
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.memory_models import (
    MemoryProviderConfigModel,
    AgentMemoryNamespaceModel,
    PROVIDER_CONFIG_SCHEMAS,
    EMBEDDING_PROVIDERS,
)
from backend.shared.memory_providers import (
    Memory,
    MemoryQuery,
    MemoryProviderConfig,
    MemoryProvider,
    MemoryProviderError,
    create_memory_provider,
)

logger = logging.getLogger(__name__)


class MemoryServiceError(Exception):
    """Base exception for memory service errors"""
    pass


class ProviderNotConfiguredError(MemoryServiceError):
    """Raised when no provider is configured"""
    pass


class InvalidProviderConfigError(MemoryServiceError):
    """Raised when provider configuration is invalid"""
    pass


class EmbeddingService:
    """
    Generate embeddings using customer's configured provider.

    Supports:
    - OpenAI (text-embedding-3-small, text-embedding-3-large, ada-002)
    - Cohere (embed-english-v3.0, embed-multilingual-v3.0)
    - Voyage AI (voyage-2, voyage-large-2)
    - Local models (via sentence-transformers)
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key

    async def generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""

        if self.provider == "openai":
            return await self._generate_openai(texts)
        elif self.provider == "cohere":
            return await self._generate_cohere(texts)
        elif self.provider == "voyage":
            return await self._generate_voyage(texts)
        elif self.provider == "local":
            return await self._generate_local(texts)
        else:
            raise MemoryServiceError(f"Unsupported embedding provider: {self.provider}")

    async def _generate_openai(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API"""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": texts,
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                raise MemoryServiceError(f"OpenAI embedding failed: {response.text}")

            data = response.json()
            # Sort by index to ensure correct order
            embeddings = sorted(data["data"], key=lambda x: x["index"])
            return [e["embedding"] for e in embeddings]

    async def _generate_cohere(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Cohere API"""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.cohere.ai/v1/embed",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "texts": texts,
                    "input_type": "search_document",
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                raise MemoryServiceError(f"Cohere embedding failed: {response.text}")

            data = response.json()
            return data["embeddings"]

    async def _generate_voyage(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Voyage AI API"""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": texts,
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                raise MemoryServiceError(f"Voyage embedding failed: {response.text}")

            data = response.json()
            return [e["embedding"] for e in data["data"]]

    async def _generate_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local sentence-transformers model"""
        # For local models, we'd use sentence-transformers
        # This would run on customer's compute (BYOC)
        raise NotImplementedError(
            "Local embedding models require customer's compute infrastructure (BYOC)"
        )


class MemoryService:
    """
    Memory service for managing agent memories.

    Orchestrates:
    - Provider configuration management
    - Namespace management
    - Embedding generation
    - Memory CRUD operations via providers
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._providers: Dict[str, MemoryProvider] = {}

    # ==================== Provider Configuration ====================

    async def create_provider_config(
        self,
        organization_id: str,
        provider_type: str,
        name: str,
        connection_config: Dict[str, Any],
        embedding_provider: str = "openai",
        embedding_model: str = "text-embedding-3-small",
        description: Optional[str] = None,
        is_default: bool = False,
        created_by: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> MemoryProviderConfigModel:
        """
        Create a new memory provider configuration.

        Validates the connection config against provider schema.
        """
        # Validate provider type
        if provider_type not in PROVIDER_CONFIG_SCHEMAS:
            raise InvalidProviderConfigError(
                f"Unknown provider type: {provider_type}. "
                f"Supported: {list(PROVIDER_CONFIG_SCHEMAS.keys())}"
            )

        # Validate connection config
        schema = PROVIDER_CONFIG_SCHEMAS[provider_type]
        for required_field in schema["required"]:
            if required_field not in connection_config:
                raise InvalidProviderConfigError(
                    f"Missing required field '{required_field}' for {provider_type}. "
                    f"Required: {schema['required']}"
                )

        # Validate embedding provider/model
        if embedding_provider not in EMBEDDING_PROVIDERS:
            raise InvalidProviderConfigError(
                f"Unknown embedding provider: {embedding_provider}. "
                f"Supported: {list(EMBEDDING_PROVIDERS.keys())}"
            )

        embedding_config = EMBEDDING_PROVIDERS[embedding_provider]
        if embedding_model not in embedding_config["models"]:
            raise InvalidProviderConfigError(
                f"Unknown model '{embedding_model}' for {embedding_provider}. "
                f"Supported: {list(embedding_config['models'].keys())}"
            )

        embedding_dimensions = embedding_config["models"][embedding_model]["dimensions"]

        # If setting as default, unset other defaults
        if is_default:
            await self.db.execute(
                update(MemoryProviderConfigModel)
                .where(MemoryProviderConfigModel.organization_id == organization_id)
                .where(MemoryProviderConfigModel.is_default == True)
                .values(is_default=False)
            )

        # Create config
        config = MemoryProviderConfigModel(
            config_id=uuid4(),
            organization_id=organization_id,
            provider_type=provider_type,
            name=name,
            description=description,
            connection_config=connection_config,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
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
            logger.warning(f"Provider health check failed: {e}")
            config.health_status = "unhealthy"
            await self.db.commit()

        return config

    async def get_provider_configs(
        self,
        organization_id: str,
        provider_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[MemoryProviderConfigModel]:
        """Get all provider configs for an organization"""
        query = select(MemoryProviderConfigModel).where(
            MemoryProviderConfigModel.organization_id == organization_id
        )

        if provider_type:
            query = query.where(MemoryProviderConfigModel.provider_type == provider_type)

        if active_only:
            query = query.where(MemoryProviderConfigModel.is_active == True)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_provider_config(
        self,
        config_id: UUID,
    ) -> Optional[MemoryProviderConfigModel]:
        """Get a specific provider config"""
        result = await self.db.execute(
            select(MemoryProviderConfigModel)
            .where(MemoryProviderConfigModel.config_id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_default_provider(
        self,
        organization_id: str,
    ) -> Optional[MemoryProviderConfigModel]:
        """Get the default provider for an organization"""
        result = await self.db.execute(
            select(MemoryProviderConfigModel)
            .where(MemoryProviderConfigModel.organization_id == organization_id)
            .where(MemoryProviderConfigModel.is_default == True)
            .where(MemoryProviderConfigModel.is_active == True)
        )
        return result.scalar_one_or_none()

    async def update_provider_config(
        self,
        config_id: UUID,
        **updates,
    ) -> Optional[MemoryProviderConfigModel]:
        """Update a provider configuration"""
        config = await self.get_provider_config(config_id)
        if not config:
            return None

        allowed_fields = {
            "name", "description", "connection_config", "embedding_provider",
            "embedding_model", "is_active", "is_default", "tags", "extra_metadata"
        }

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(config, field, value)

        config.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(config)

        return config

    async def delete_provider_config(self, config_id: UUID) -> bool:
        """Delete a provider configuration"""
        config = await self.get_provider_config(config_id)
        if not config:
            return False

        await self.db.delete(config)
        await self.db.commit()
        return True

    async def test_provider_connection(
        self,
        config_id: UUID,
    ) -> Dict[str, Any]:
        """Test connection to a provider"""
        config = await self.get_provider_config(config_id)
        if not config:
            return {"status": "error", "error": "Config not found"}

        try:
            provider = await self._get_provider(config)
            health = await provider.health_check()

            # Update health status
            config.health_status = health.get("status", "unknown")
            config.last_health_check = datetime.utcnow()
            await self.db.commit()

            return health
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    # ==================== Namespace Management ====================

    async def create_namespace(
        self,
        organization_id: str,
        provider_config_id: UUID,
        namespace: str,
        namespace_type: str = "custom",
        description: Optional[str] = None,
        memory_types: Optional[List[str]] = None,
        retention_days: Optional[int] = None,
        max_memories: Optional[int] = None,
    ) -> AgentMemoryNamespaceModel:
        """Create a memory namespace"""
        ns = AgentMemoryNamespaceModel(
            namespace_id=uuid4(),
            organization_id=organization_id,
            provider_config_id=provider_config_id,
            namespace=namespace,
            namespace_type=namespace_type,
            description=description,
            memory_types=memory_types or ["long_term"],
            retention_days=retention_days,
            max_memories=max_memories,
        )

        self.db.add(ns)
        await self.db.commit()
        await self.db.refresh(ns)

        return ns

    async def get_namespaces(
        self,
        organization_id: str,
        provider_config_id: Optional[UUID] = None,
    ) -> List[AgentMemoryNamespaceModel]:
        """Get namespaces for an organization"""
        query = select(AgentMemoryNamespaceModel).where(
            AgentMemoryNamespaceModel.organization_id == organization_id
        )

        if provider_config_id:
            query = query.where(
                AgentMemoryNamespaceModel.provider_config_id == provider_config_id
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_namespace(
        self,
        namespace_id: UUID,
    ) -> Optional[AgentMemoryNamespaceModel]:
        """Get a specific namespace"""
        result = await self.db.execute(
            select(AgentMemoryNamespaceModel)
            .where(AgentMemoryNamespaceModel.namespace_id == namespace_id)
        )
        return result.scalar_one_or_none()

    async def delete_namespace(
        self,
        namespace_id: UUID,
        delete_memories: bool = False,
    ) -> bool:
        """Delete a namespace (optionally delete all memories in it)"""
        ns = await self.get_namespace(namespace_id)
        if not ns:
            return False

        if delete_memories:
            config = await self.get_provider_config(ns.provider_config_id)
            if config:
                try:
                    provider = await self._get_provider(config)
                    await provider.delete_namespace(ns.namespace)
                except Exception as e:
                    logger.error(f"Failed to delete memories in namespace: {e}")

        await self.db.delete(ns)
        await self.db.commit()
        return True

    # ==================== Memory Operations ====================

    async def store_memory(
        self,
        organization_id: str,
        content: str,
        namespace: str = "default",
        memory_type: str = "long_term",
        metadata: Optional[Dict[str, Any]] = None,
        provider_config_id: Optional[UUID] = None,
        embedding_api_key: Optional[str] = None,
    ) -> str:
        """
        Store a memory in the customer's vector database.

        1. Get or use default provider config
        2. Generate embedding using customer's embedding API key
        3. Store in customer's vector DB
        """
        # Get provider config
        if provider_config_id:
            config = await self.get_provider_config(provider_config_id)
        else:
            config = await self.get_default_provider(organization_id)

        if not config:
            raise ProviderNotConfiguredError(
                "No memory provider configured. Please configure a vector database first."
            )

        # Generate embedding
        embedding_service = EmbeddingService(
            provider=config.embedding_provider,
            model=config.embedding_model,
            api_key=embedding_api_key,
        )

        embeddings = await embedding_service.generate([content])
        embedding = embeddings[0]

        # Get provider
        provider = await self._get_provider(config)

        # Create memory object
        memory = Memory(
            id="",  # Will be generated
            content=content,
            embedding=embedding,
            metadata=metadata,
            memory_type=memory_type,
            namespace=namespace,
            created_at=datetime.utcnow(),
        )

        # Store in vector DB
        memory_id = await provider.store(memory)

        # Update stats
        config.total_memories += 1
        await self.db.commit()

        return memory_id

    async def store_memories_batch(
        self,
        organization_id: str,
        memories: List[Dict[str, Any]],
        provider_config_id: Optional[UUID] = None,
        embedding_api_key: Optional[str] = None,
    ) -> List[str]:
        """Store multiple memories in batch"""
        # Get provider config
        if provider_config_id:
            config = await self.get_provider_config(provider_config_id)
        else:
            config = await self.get_default_provider(organization_id)

        if not config:
            raise ProviderNotConfiguredError(
                "No memory provider configured. Please configure a vector database first."
            )

        # Generate embeddings in batch
        embedding_service = EmbeddingService(
            provider=config.embedding_provider,
            model=config.embedding_model,
            api_key=embedding_api_key,
        )

        contents = [m["content"] for m in memories]
        embeddings = await embedding_service.generate(contents)

        # Get provider
        provider = await self._get_provider(config)

        # Create memory objects
        memory_objects = []
        for m, embedding in zip(memories, embeddings):
            memory_objects.append(Memory(
                id="",
                content=m["content"],
                embedding=embedding,
                metadata=m.get("metadata"),
                memory_type=m.get("memory_type", "long_term"),
                namespace=m.get("namespace", "default"),
                created_at=datetime.utcnow(),
            ))

        # Store batch
        memory_ids = await provider.store_batch(memory_objects)

        # Update stats
        config.total_memories += len(memory_ids)
        await self.db.commit()

        return memory_ids

    async def retrieve_memories(
        self,
        organization_id: str,
        query: str,
        namespace: str = "default",
        memory_types: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        min_score: float = 0.0,
        provider_config_id: Optional[UUID] = None,
        embedding_api_key: Optional[str] = None,
    ) -> List[Memory]:
        """
        Retrieve memories similar to the query.

        Uses vector similarity search in customer's vector DB.
        """
        # Get provider config
        if provider_config_id:
            config = await self.get_provider_config(provider_config_id)
        else:
            config = await self.get_default_provider(organization_id)

        if not config:
            raise ProviderNotConfiguredError(
                "No memory provider configured. Please configure a vector database first."
            )

        # Generate query embedding
        embedding_service = EmbeddingService(
            provider=config.embedding_provider,
            model=config.embedding_model,
            api_key=embedding_api_key,
        )

        embeddings = await embedding_service.generate([query])
        query_embedding = embeddings[0]

        # Get provider
        provider = await self._get_provider(config)

        # Query
        memory_query = MemoryQuery(
            query=query,
            query_embedding=query_embedding,
            namespace=namespace,
            memory_types=memory_types,
            filters=filters,
            top_k=top_k,
            min_score=min_score,
        )

        memories = await provider.retrieve(memory_query)

        # Update stats
        config.total_queries += 1
        await self.db.commit()

        return memories

    async def get_memory(
        self,
        organization_id: str,
        memory_id: str,
        namespace: str = "default",
        provider_config_id: Optional[UUID] = None,
    ) -> Optional[Memory]:
        """Get a specific memory by ID"""
        # Get provider config
        if provider_config_id:
            config = await self.get_provider_config(provider_config_id)
        else:
            config = await self.get_default_provider(organization_id)

        if not config:
            return None

        provider = await self._get_provider(config)
        return await provider.get(memory_id, namespace)

    async def delete_memory(
        self,
        organization_id: str,
        memory_id: str,
        namespace: str = "default",
        provider_config_id: Optional[UUID] = None,
    ) -> bool:
        """Delete a specific memory"""
        # Get provider config
        if provider_config_id:
            config = await self.get_provider_config(provider_config_id)
        else:
            config = await self.get_default_provider(organization_id)

        if not config:
            return False

        provider = await self._get_provider(config)
        success = await provider.delete(memory_id, namespace)

        if success:
            config.total_memories = max(0, config.total_memories - 1)
            await self.db.commit()

        return success

    # ==================== Provider Instance Management ====================

    async def _get_provider(
        self,
        config: MemoryProviderConfigModel,
    ) -> MemoryProvider:
        """Get or create a provider instance"""
        cache_key = str(config.config_id)

        if cache_key not in self._providers:
            provider_config = MemoryProviderConfig(
                provider_type=config.provider_type,
                connection_config=config.connection_config,
                embedding_provider=config.embedding_provider,
                embedding_model=config.embedding_model,
                embedding_dimensions=config.embedding_dimensions,
            )

            provider = create_memory_provider(provider_config)
            connected = await provider.connect()

            if not connected:
                raise MemoryProviderError(
                    f"Failed to connect to {config.provider_type} provider"
                )

            self._providers[cache_key] = provider

        return self._providers[cache_key]

    async def close(self):
        """Close all provider connections"""
        for provider in self._providers.values():
            try:
                await provider.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting provider: {e}")

        self._providers.clear()

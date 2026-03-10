"""
Memory Provider Interfaces - BYOS Connectors

Abstract interface for vector database providers.
Customers connect their own vector DBs - we just provide the interface.

Supported providers:
- Pinecone
- Weaviate
- Qdrant
- Redis (with RediSearch)
- Chroma
- PostgreSQL with pgvector
- Custom HTTP endpoints
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import hashlib

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """A single memory entry"""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    memory_type: str = "long_term"
    namespace: str = "default"
    created_at: Optional[datetime] = None
    score: Optional[float] = None  # Similarity score when retrieved


@dataclass
class MemoryQuery:
    """Query for retrieving memories"""
    query: str
    query_embedding: Optional[List[float]] = None
    namespace: str = "default"
    memory_types: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    top_k: int = 10
    min_score: float = 0.0


@dataclass
class MemoryProviderConfig:
    """Configuration for a memory provider"""
    provider_type: str
    connection_config: Dict[str, Any]
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536


class MemoryProviderError(Exception):
    """Base exception for memory provider errors"""
    pass


class MemoryProvider(ABC):
    """
    Abstract base class for memory providers.

    All memory providers must implement these methods.
    This allows us to support any vector database without storing data ourselves.
    """

    def __init__(self, config: MemoryProviderConfig):
        self.config = config
        self.provider_type = config.provider_type

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the vector database.
        Returns True if connection successful.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the vector database."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of the vector database connection.
        Returns: {"status": "healthy|unhealthy", "latency_ms": float, "error": str|None}
        """
        pass

    @abstractmethod
    async def store(self, memory: Memory) -> str:
        """
        Store a memory in the vector database.
        Returns: The ID of the stored memory.
        """
        pass

    @abstractmethod
    async def store_batch(self, memories: List[Memory]) -> List[str]:
        """
        Store multiple memories in batch.
        Returns: List of IDs of stored memories.
        """
        pass

    @abstractmethod
    async def retrieve(self, query: MemoryQuery) -> List[Memory]:
        """
        Retrieve memories matching the query.
        Uses vector similarity search.
        """
        pass

    @abstractmethod
    async def get(self, memory_id: str, namespace: str = "default") -> Optional[Memory]:
        """
        Get a specific memory by ID.
        """
        pass

    @abstractmethod
    async def delete(self, memory_id: str, namespace: str = "default") -> bool:
        """
        Delete a specific memory.
        Returns True if deleted.
        """
        pass

    @abstractmethod
    async def delete_namespace(self, namespace: str) -> int:
        """
        Delete all memories in a namespace.
        Returns count of deleted memories.
        """
        pass

    @abstractmethod
    async def count(self, namespace: Optional[str] = None) -> int:
        """
        Count memories, optionally filtered by namespace.
        """
        pass

    def _generate_id(self, content: str, namespace: str) -> str:
        """Generate a deterministic ID for a memory"""
        hash_input = f"{namespace}:{content}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


class PineconeProvider(MemoryProvider):
    """Pinecone vector database provider"""

    def __init__(self, config: MemoryProviderConfig):
        super().__init__(config)
        self.http_client = None
        self.api_key = None
        self.index_name = None
        self.host = None

    async def connect(self) -> bool:
        try:
            self.api_key = self.config.connection_config.get("api_key")
            self.index_name = self.config.connection_config.get("index_name")
            self.environment = self.config.connection_config.get("environment", "")
            self.host = self.config.connection_config.get("host")

            if not self.host:
                # Construct host from environment
                self.host = f"https://{self.index_name}.svc.{self.environment}.pinecone.io"

            self.http_client = httpx.AsyncClient(
                headers={"Api-Key": self.api_key},
                timeout=30.0
            )

            # Test connection
            health = await self.health_check()
            return health.get("status") == "healthy"

        except Exception as e:
            logger.error(f"Failed to connect to Pinecone: {e}")
            return False

    async def disconnect(self) -> None:
        if self.http_client:
            await self.http_client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        try:
            start = datetime.utcnow()
            response = await self.http_client.get(f"{self.host}/describe_index_stats")
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            if response.status_code == 200:
                return {"status": "healthy", "latency_ms": latency, "error": None}
            else:
                return {"status": "unhealthy", "latency_ms": latency, "error": response.text}
        except Exception as e:
            return {"status": "unhealthy", "latency_ms": 0, "error": str(e)}

    async def store(self, memory: Memory) -> str:
        memory_id = memory.id or self._generate_id(memory.content, memory.namespace)

        vector = {
            "id": memory_id,
            "values": memory.embedding,
            "metadata": {
                "content": memory.content,
                "memory_type": memory.memory_type,
                "namespace": memory.namespace,
                "created_at": memory.created_at.isoformat() if memory.created_at else datetime.utcnow().isoformat(),
                **(memory.metadata or {})
            }
        }

        response = await self.http_client.post(
            f"{self.host}/vectors/upsert",
            json={"vectors": [vector], "namespace": memory.namespace}
        )

        if response.status_code != 200:
            raise MemoryProviderError(f"Failed to store memory: {response.text}")

        return memory_id

    async def store_batch(self, memories: List[Memory]) -> List[str]:
        ids = []
        vectors = []
        for memory in memories:
            memory_id = memory.id or self._generate_id(memory.content, memory.namespace)
            ids.append(memory_id)
            vectors.append({
                "id": memory_id,
                "values": memory.embedding,
                "metadata": {
                    "content": memory.content,
                    "memory_type": memory.memory_type,
                    "namespace": memory.namespace,
                    "created_at": memory.created_at.isoformat() if memory.created_at else datetime.utcnow().isoformat(),
                    **(memory.metadata or {})
                }
            })

        # Group by namespace
        by_namespace: Dict[str, List[Dict]] = {}
        for v, m in zip(vectors, memories):
            ns = m.namespace
            if ns not in by_namespace:
                by_namespace[ns] = []
            by_namespace[ns].append(v)

        for ns, vecs in by_namespace.items():
            response = await self.http_client.post(
                f"{self.host}/vectors/upsert",
                json={"vectors": vecs, "namespace": ns}
            )
            if response.status_code != 200:
                raise MemoryProviderError(f"Failed to store memories: {response.text}")

        return ids

    async def retrieve(self, query: MemoryQuery) -> List[Memory]:
        request_body = {
            "vector": query.query_embedding,
            "topK": query.top_k,
            "includeMetadata": True,
            "namespace": query.namespace,
        }

        if query.filters:
            request_body["filter"] = query.filters

        response = await self.http_client.post(
            f"{self.host}/query",
            json=request_body
        )

        if response.status_code != 200:
            raise MemoryProviderError(f"Failed to query memories: {response.text}")

        data = response.json()
        memories = []

        for match in data.get("matches", []):
            if match["score"] >= query.min_score:
                metadata = match.get("metadata", {})
                memories.append(Memory(
                    id=match["id"],
                    content=metadata.get("content", ""),
                    metadata={k: v for k, v in metadata.items() if k not in ["content", "memory_type", "namespace", "created_at"]},
                    memory_type=metadata.get("memory_type", "long_term"),
                    namespace=metadata.get("namespace", query.namespace),
                    created_at=datetime.fromisoformat(metadata["created_at"]) if metadata.get("created_at") else None,
                    score=match["score"]
                ))

        return memories

    async def get(self, memory_id: str, namespace: str = "default") -> Optional[Memory]:
        response = await self.http_client.get(
            f"{self.host}/vectors/fetch",
            params={"ids": memory_id, "namespace": namespace}
        )

        if response.status_code != 200:
            return None

        data = response.json()
        vectors = data.get("vectors", {})

        if memory_id in vectors:
            v = vectors[memory_id]
            metadata = v.get("metadata", {})
            return Memory(
                id=memory_id,
                content=metadata.get("content", ""),
                embedding=v.get("values"),
                metadata={k: val for k, val in metadata.items() if k not in ["content", "memory_type", "namespace", "created_at"]},
                memory_type=metadata.get("memory_type", "long_term"),
                namespace=namespace,
                created_at=datetime.fromisoformat(metadata["created_at"]) if metadata.get("created_at") else None,
            )

        return None

    async def delete(self, memory_id: str, namespace: str = "default") -> bool:
        response = await self.http_client.post(
            f"{self.host}/vectors/delete",
            json={"ids": [memory_id], "namespace": namespace}
        )
        return response.status_code == 200

    async def delete_namespace(self, namespace: str) -> int:
        response = await self.http_client.post(
            f"{self.host}/vectors/delete",
            json={"deleteAll": True, "namespace": namespace}
        )
        # Pinecone doesn't return count, so we return -1 to indicate unknown
        return -1 if response.status_code == 200 else 0

    async def count(self, namespace: Optional[str] = None) -> int:
        response = await self.http_client.get(f"{self.host}/describe_index_stats")
        if response.status_code == 200:
            data = response.json()
            if namespace:
                namespaces = data.get("namespaces", {})
                return namespaces.get(namespace, {}).get("vectorCount", 0)
            return data.get("totalVectorCount", 0)
        return 0


class QdrantProvider(MemoryProvider):
    """Qdrant vector database provider"""

    def __init__(self, config: MemoryProviderConfig):
        super().__init__(config)
        self.http_client = None
        self.url = None
        self.collection_name = None

    async def connect(self) -> bool:
        try:
            self.url = self.config.connection_config.get("url")
            self.api_key = self.config.connection_config.get("api_key")
            self.collection_name = self.config.connection_config.get("collection_name", "agent_memories")

            headers = {}
            if self.api_key:
                headers["api-key"] = self.api_key

            self.http_client = httpx.AsyncClient(
                base_url=self.url,
                headers=headers,
                timeout=30.0
            )

            health = await self.health_check()
            return health.get("status") == "healthy"

        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            return False

    async def disconnect(self) -> None:
        if self.http_client:
            await self.http_client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        try:
            start = datetime.utcnow()
            response = await self.http_client.get("/collections")
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            if response.status_code == 200:
                return {"status": "healthy", "latency_ms": latency, "error": None}
            else:
                return {"status": "unhealthy", "latency_ms": latency, "error": response.text}
        except Exception as e:
            return {"status": "unhealthy", "latency_ms": 0, "error": str(e)}

    async def store(self, memory: Memory) -> str:
        memory_id = memory.id or self._generate_id(memory.content, memory.namespace)

        point = {
            "id": memory_id,
            "vector": memory.embedding,
            "payload": {
                "content": memory.content,
                "memory_type": memory.memory_type,
                "namespace": memory.namespace,
                "created_at": memory.created_at.isoformat() if memory.created_at else datetime.utcnow().isoformat(),
                **(memory.metadata or {})
            }
        }

        response = await self.http_client.put(
            f"/collections/{self.collection_name}/points",
            json={"points": [point]}
        )

        if response.status_code not in [200, 201]:
            raise MemoryProviderError(f"Failed to store memory: {response.text}")

        return memory_id

    async def store_batch(self, memories: List[Memory]) -> List[str]:
        ids = []
        points = []

        for memory in memories:
            memory_id = memory.id or self._generate_id(memory.content, memory.namespace)
            ids.append(memory_id)
            points.append({
                "id": memory_id,
                "vector": memory.embedding,
                "payload": {
                    "content": memory.content,
                    "memory_type": memory.memory_type,
                    "namespace": memory.namespace,
                    "created_at": memory.created_at.isoformat() if memory.created_at else datetime.utcnow().isoformat(),
                    **(memory.metadata or {})
                }
            })

        response = await self.http_client.put(
            f"/collections/{self.collection_name}/points",
            json={"points": points}
        )

        if response.status_code not in [200, 201]:
            raise MemoryProviderError(f"Failed to store memories: {response.text}")

        return ids

    async def retrieve(self, query: MemoryQuery) -> List[Memory]:
        request_body = {
            "vector": query.query_embedding,
            "limit": query.top_k,
            "with_payload": True,
            "score_threshold": query.min_score,
        }

        # Build filter
        must_conditions = [{"key": "namespace", "match": {"value": query.namespace}}]

        if query.memory_types:
            must_conditions.append({
                "key": "memory_type",
                "match": {"any": query.memory_types}
            })

        if query.filters:
            for key, value in query.filters.items():
                must_conditions.append({"key": key, "match": {"value": value}})

        request_body["filter"] = {"must": must_conditions}

        response = await self.http_client.post(
            f"/collections/{self.collection_name}/points/search",
            json=request_body
        )

        if response.status_code != 200:
            raise MemoryProviderError(f"Failed to query memories: {response.text}")

        data = response.json()
        memories = []

        for result in data.get("result", []):
            payload = result.get("payload", {})
            memories.append(Memory(
                id=str(result["id"]),
                content=payload.get("content", ""),
                metadata={k: v for k, v in payload.items() if k not in ["content", "memory_type", "namespace", "created_at"]},
                memory_type=payload.get("memory_type", "long_term"),
                namespace=payload.get("namespace", query.namespace),
                created_at=datetime.fromisoformat(payload["created_at"]) if payload.get("created_at") else None,
                score=result.get("score", 0)
            ))

        return memories

    async def get(self, memory_id: str, namespace: str = "default") -> Optional[Memory]:
        response = await self.http_client.get(
            f"/collections/{self.collection_name}/points/{memory_id}"
        )

        if response.status_code != 200:
            return None

        data = response.json()
        result = data.get("result")

        if result:
            payload = result.get("payload", {})
            return Memory(
                id=str(result["id"]),
                content=payload.get("content", ""),
                embedding=result.get("vector"),
                metadata={k: v for k, v in payload.items() if k not in ["content", "memory_type", "namespace", "created_at"]},
                memory_type=payload.get("memory_type", "long_term"),
                namespace=payload.get("namespace", namespace),
                created_at=datetime.fromisoformat(payload["created_at"]) if payload.get("created_at") else None,
            )

        return None

    async def delete(self, memory_id: str, namespace: str = "default") -> bool:
        response = await self.http_client.post(
            f"/collections/{self.collection_name}/points/delete",
            json={"points": [memory_id]}
        )
        return response.status_code == 200

    async def delete_namespace(self, namespace: str) -> int:
        response = await self.http_client.post(
            f"/collections/{self.collection_name}/points/delete",
            json={
                "filter": {
                    "must": [{"key": "namespace", "match": {"value": namespace}}]
                }
            }
        )
        return -1 if response.status_code == 200 else 0

    async def count(self, namespace: Optional[str] = None) -> int:
        if namespace:
            response = await self.http_client.post(
                f"/collections/{self.collection_name}/points/count",
                json={
                    "filter": {
                        "must": [{"key": "namespace", "match": {"value": namespace}}]
                    }
                }
            )
        else:
            response = await self.http_client.post(
                f"/collections/{self.collection_name}/points/count",
                json={}
            )

        if response.status_code == 200:
            return response.json().get("result", {}).get("count", 0)
        return 0


class WeaviateProvider(MemoryProvider):
    """Weaviate vector database provider"""

    def __init__(self, config: MemoryProviderConfig):
        super().__init__(config)
        self.http_client = None
        self.url = None
        self.class_name = None

    async def connect(self) -> bool:
        try:
            self.url = self.config.connection_config.get("url")
            self.api_key = self.config.connection_config.get("api_key")
            self.class_name = self.config.connection_config.get("class_name", "AgentMemory")

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self.http_client = httpx.AsyncClient(
                base_url=self.url,
                headers=headers,
                timeout=30.0
            )

            health = await self.health_check()
            return health.get("status") == "healthy"

        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            return False

    async def disconnect(self) -> None:
        if self.http_client:
            await self.http_client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        try:
            start = datetime.utcnow()
            response = await self.http_client.get("/v1/.well-known/ready")
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            if response.status_code == 200:
                return {"status": "healthy", "latency_ms": latency, "error": None}
            else:
                return {"status": "unhealthy", "latency_ms": latency, "error": response.text}
        except Exception as e:
            return {"status": "unhealthy", "latency_ms": 0, "error": str(e)}

    async def store(self, memory: Memory) -> str:
        memory_id = memory.id or self._generate_id(memory.content, memory.namespace)

        obj = {
            "class": self.class_name,
            "id": memory_id,
            "properties": {
                "content": memory.content,
                "memoryType": memory.memory_type,
                "namespace": memory.namespace,
                "createdAt": memory.created_at.isoformat() if memory.created_at else datetime.utcnow().isoformat(),
                **(memory.metadata or {})
            },
            "vector": memory.embedding
        }

        response = await self.http_client.post("/v1/objects", json=obj)

        if response.status_code not in [200, 201]:
            raise MemoryProviderError(f"Failed to store memory: {response.text}")

        return memory_id

    async def store_batch(self, memories: List[Memory]) -> List[str]:
        ids = []
        objects = []

        for memory in memories:
            memory_id = memory.id or self._generate_id(memory.content, memory.namespace)
            ids.append(memory_id)
            objects.append({
                "class": self.class_name,
                "id": memory_id,
                "properties": {
                    "content": memory.content,
                    "memoryType": memory.memory_type,
                    "namespace": memory.namespace,
                    "createdAt": memory.created_at.isoformat() if memory.created_at else datetime.utcnow().isoformat(),
                    **(memory.metadata or {})
                },
                "vector": memory.embedding
            })

        response = await self.http_client.post("/v1/batch/objects", json={"objects": objects})

        if response.status_code not in [200, 201]:
            raise MemoryProviderError(f"Failed to store memories: {response.text}")

        return ids

    async def retrieve(self, query: MemoryQuery) -> List[Memory]:
        graphql_query = {
            "query": f"""
            {{
                Get {{
                    {self.class_name}(
                        nearVector: {{
                            vector: {query.query_embedding}
                        }}
                        limit: {query.top_k}
                        where: {{
                            path: ["namespace"]
                            operator: Equal
                            valueText: "{query.namespace}"
                        }}
                    ) {{
                        _additional {{
                            id
                            certainty
                        }}
                        content
                        memoryType
                        namespace
                        createdAt
                    }}
                }}
            }}
            """
        }

        response = await self.http_client.post("/v1/graphql", json=graphql_query)

        if response.status_code != 200:
            raise MemoryProviderError(f"Failed to query memories: {response.text}")

        data = response.json()
        results = data.get("data", {}).get("Get", {}).get(self.class_name, [])
        memories = []

        for result in results:
            score = result.get("_additional", {}).get("certainty", 0)
            if score >= query.min_score:
                memories.append(Memory(
                    id=result.get("_additional", {}).get("id", ""),
                    content=result.get("content", ""),
                    metadata={k: v for k, v in result.items() if k not in ["content", "memoryType", "namespace", "createdAt", "_additional"]},
                    memory_type=result.get("memoryType", "long_term"),
                    namespace=result.get("namespace", query.namespace),
                    created_at=datetime.fromisoformat(result["createdAt"]) if result.get("createdAt") else None,
                    score=score
                ))

        return memories

    async def get(self, memory_id: str, namespace: str = "default") -> Optional[Memory]:
        response = await self.http_client.get(f"/v1/objects/{self.class_name}/{memory_id}")

        if response.status_code != 200:
            return None

        data = response.json()
        props = data.get("properties", {})

        return Memory(
            id=data.get("id", memory_id),
            content=props.get("content", ""),
            embedding=data.get("vector"),
            metadata={k: v for k, v in props.items() if k not in ["content", "memoryType", "namespace", "createdAt"]},
            memory_type=props.get("memoryType", "long_term"),
            namespace=props.get("namespace", namespace),
            created_at=datetime.fromisoformat(props["createdAt"]) if props.get("createdAt") else None,
        )

    async def delete(self, memory_id: str, namespace: str = "default") -> bool:
        response = await self.http_client.delete(f"/v1/objects/{self.class_name}/{memory_id}")
        return response.status_code in [200, 204]

    async def delete_namespace(self, namespace: str) -> int:
        # Weaviate batch delete with where filter
        response = await self.http_client.delete(
            f"/v1/batch/objects",
            json={
                "match": {
                    "class": self.class_name,
                    "where": {
                        "path": ["namespace"],
                        "operator": "Equal",
                        "valueText": namespace
                    }
                }
            }
        )
        return -1 if response.status_code == 200 else 0

    async def count(self, namespace: Optional[str] = None) -> int:
        where_clause = ""
        if namespace:
            where_clause = f"""
            where: {{
                path: ["namespace"]
                operator: Equal
                valueText: "{namespace}"
            }}
            """

        graphql_query = {
            "query": f"""
            {{
                Aggregate {{
                    {self.class_name}({where_clause}) {{
                        meta {{
                            count
                        }}
                    }}
                }}
            }}
            """
        }

        response = await self.http_client.post("/v1/graphql", json=graphql_query)
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get("Aggregate", {}).get(self.class_name, [{}])[0].get("meta", {}).get("count", 0)
        return 0


class DemoMemoryProvider(MemoryProvider):
    """
    Demo memory provider for testing.
    Stores memories in-memory - no external services needed.
    Supports basic vector similarity search using cosine similarity.
    """

    def __init__(self, config: MemoryProviderConfig):
        super().__init__(config)
        self.namespace_prefix = config.connection_config.get("namespace_prefix", "demo")
        self._memories: Dict[str, Dict[str, Memory]] = {}  # namespace -> {id -> Memory}
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        logger.info("Demo memory provider connected (in-memory storage)")
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def health_check(self) -> Dict[str, Any]:
        total_memories = sum(len(ns) for ns in self._memories.values())
        return {
            "status": "healthy" if self._connected else "unhealthy",
            "latency_ms": 0.5,
            "error": None,
            "namespaces": len(self._memories),
            "total_memories": total_memories,
        }

    async def store(self, memory: Memory) -> str:
        memory_id = memory.id or self._generate_id(memory.content, memory.namespace)
        ns = memory.namespace

        if ns not in self._memories:
            self._memories[ns] = {}

        stored = Memory(
            id=memory_id,
            content=memory.content,
            embedding=memory.embedding,
            metadata=memory.metadata,
            memory_type=memory.memory_type,
            namespace=ns,
            created_at=memory.created_at or datetime.utcnow(),
        )
        self._memories[ns][memory_id] = stored
        return memory_id

    async def store_batch(self, memories: List[Memory]) -> List[str]:
        ids = []
        for memory in memories:
            mem_id = await self.store(memory)
            ids.append(mem_id)
        return ids

    async def retrieve(self, query: MemoryQuery) -> List[Memory]:
        """Retrieve memories using cosine similarity"""
        if not query.query_embedding:
            return []

        results = []
        ns = query.namespace

        # Search in specified namespace
        if ns in self._memories:
            for memory in self._memories[ns].values():
                if memory.embedding:
                    score = self._cosine_similarity(query.query_embedding, memory.embedding)
                    if score >= query.min_score:
                        # Filter by memory types if specified
                        if query.memory_types and memory.memory_type not in query.memory_types:
                            continue
                        results.append((score, memory))

        # Sort by score and return top_k
        results.sort(key=lambda x: x[0], reverse=True)
        return [
            Memory(
                id=m.id,
                content=m.content,
                embedding=m.embedding,
                metadata=m.metadata,
                memory_type=m.memory_type,
                namespace=m.namespace,
                created_at=m.created_at,
                score=score,
            )
            for score, m in results[:query.top_k]
        ]

    async def get(self, memory_id: str, namespace: str = "default") -> Optional[Memory]:
        if namespace in self._memories:
            return self._memories[namespace].get(memory_id)
        return None

    async def delete(self, memory_id: str, namespace: str = "default") -> bool:
        if namespace in self._memories and memory_id in self._memories[namespace]:
            del self._memories[namespace][memory_id]
            return True
        return False

    async def delete_namespace(self, namespace: str) -> int:
        if namespace in self._memories:
            count = len(self._memories[namespace])
            del self._memories[namespace]
            return count
        return 0

    async def count(self, namespace: Optional[str] = None) -> int:
        if namespace:
            return len(self._memories.get(namespace, {}))
        return sum(len(ns) for ns in self._memories.values())

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors"""
        if len(a) != len(b):
            return 0.0
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)


# Provider factory
def create_memory_provider(config: MemoryProviderConfig) -> MemoryProvider:
    """
    Factory function to create the appropriate memory provider.
    """
    providers = {
        "pinecone": PineconeProvider,
        "qdrant": QdrantProvider,
        "weaviate": WeaviateProvider,
        "demo": DemoMemoryProvider,
    }

    provider_class = providers.get(config.provider_type)
    if not provider_class:
        raise MemoryProviderError(f"Unsupported provider type: {config.provider_type}")

    return provider_class(config)

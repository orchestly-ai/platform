"""
RAG Provider Interfaces - BYOD Connectors

Abstract interface for document store providers.
Customers connect their own document stores - we just provide the interface.

Supported providers:
- S3/GCS/Azure Blob storage
- Elasticsearch/OpenSearch
- MongoDB
- Notion, Confluence, Google Drive
- Custom HTTP endpoints
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass
from datetime import datetime
import hashlib

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A document from a data source"""
    id: str
    source_id: str  # ID in the source system
    source_path: Optional[str] = None
    content: str = ""
    title: Optional[str] = None
    doc_type: str = "text"
    metadata: Optional[Dict[str, Any]] = None
    size_bytes: Optional[int] = None
    modified_at: Optional[datetime] = None
    content_hash: Optional[str] = None


@dataclass
class DocumentChunk:
    """A chunk of a document for embedding"""
    id: str
    document_id: str
    content: str
    chunk_index: int
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RAGQuery:
    """Query for retrieving documents"""
    query: str
    query_embedding: Optional[List[float]] = None
    top_k: int = 10
    min_score: float = 0.0
    filters: Optional[Dict[str, Any]] = None
    include_content: bool = True


@dataclass
class RAGResult:
    """Result from a RAG query"""
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: Optional[Dict[str, Any]] = None
    document_title: Optional[str] = None
    source_path: Optional[str] = None


@dataclass
class RAGProviderConfig:
    """Configuration for a RAG provider"""
    provider_type: str
    connection_config: Dict[str, Any]
    chunking_strategy: str = "recursive"
    chunk_size: int = 1000
    chunk_overlap: int = 200


class RAGProviderError(Exception):
    """Base exception for RAG provider errors"""
    pass


class RAGProvider(ABC):
    """
    Abstract base class for RAG providers.

    All RAG providers must implement these methods.
    This allows us to support any document store without storing data ourselves.
    """

    def __init__(self, config: RAGProviderConfig):
        self.config = config
        self.provider_type = config.provider_type

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the document store."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the document store."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check health of the document store connection."""
        pass

    @abstractmethod
    async def list_documents(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Document]:
        """List documents in the store."""
        pass

    @abstractmethod
    async def get_document(self, source_id: str) -> Optional[Document]:
        """Get a specific document by source ID."""
        pass

    @abstractmethod
    async def get_document_content(self, source_id: str) -> Optional[str]:
        """Get the content of a document."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Search documents using native search."""
        pass

    def _generate_content_hash(self, content: str) -> str:
        """Generate a hash of document content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()


class S3Provider(RAGProvider):
    """AWS S3 document store provider - supports both aioboto3 (async) and boto3 (sync)"""

    def __init__(self, config: RAGProviderConfig):
        super().__init__(config)
        self.client = None
        self.bucket = None
        self.prefix = ""
        self._use_async = False  # Track whether we're using async or sync boto3

    async def connect(self) -> bool:
        self.bucket = self.config.connection_config.get("bucket")
        self.prefix = self.config.connection_config.get("prefix", "")
        self.region = self.config.connection_config.get("region", "us-east-1")
        self.access_key = self.config.connection_config.get("access_key")
        self.secret_key = self.config.connection_config.get("secret_key")
        # Support custom endpoint for MinIO/LocalStack/etc
        self.endpoint_url = self.config.connection_config.get("endpoint_url")

        # Try aioboto3 first (async), fall back to boto3 (sync)
        try:
            import aioboto3
            session = aioboto3.Session(
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )
            self.session = session
            self._use_async = True
            logger.info("Using aioboto3 for async S3 operations")

            # Test connection
            health = await self.health_check()
            return health.get("status") == "healthy"

        except ImportError:
            logger.info("aioboto3 not available, falling back to boto3 (sync)")
            try:
                import boto3
                client_kwargs = {
                    "aws_access_key_id": self.access_key,
                    "aws_secret_access_key": self.secret_key,
                    "region_name": self.region,
                }
                if self.endpoint_url:
                    client_kwargs["endpoint_url"] = self.endpoint_url
                self.client = boto3.client("s3", **client_kwargs)
                self._use_async = False

                # Test connection
                health = await self.health_check()
                return health.get("status") == "healthy"

            except ImportError:
                logger.error("Neither aioboto3 nor boto3 installed. Install with: pip install boto3")
                return False
            except Exception as e:
                logger.error(f"Failed to connect to S3 with boto3: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to S3: {e}")
            return False

    async def disconnect(self) -> None:
        pass  # Session-based, no persistent connection

    def _get_client_kwargs(self) -> Dict[str, Any]:
        """Get kwargs for S3 client (supports custom endpoint for MinIO/LocalStack)"""
        kwargs = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return kwargs

    async def health_check(self) -> Dict[str, Any]:
        import asyncio
        try:
            start = datetime.utcnow()

            if self._use_async:
                async with self.session.client("s3", **self._get_client_kwargs()) as s3:
                    await s3.head_bucket(Bucket=self.bucket)
            else:
                # Run sync boto3 in thread pool
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.client.head_bucket(Bucket=self.bucket)
                )

            latency = (datetime.utcnow() - start).total_seconds() * 1000
            return {"status": "healthy", "latency_ms": latency, "error": None}
        except Exception as e:
            return {"status": "unhealthy", "latency_ms": 0, "error": str(e)}

    async def list_documents(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Document]:
        import asyncio
        documents = []
        search_prefix = prefix or self.prefix

        try:
            if self._use_async:
                async with self.session.client("s3", **self._get_client_kwargs()) as s3:
                    paginator = s3.get_paginator("list_objects_v2")

                    count = 0
                    async for page in paginator.paginate(
                        Bucket=self.bucket,
                        Prefix=search_prefix,
                        MaxKeys=limit + offset,
                    ):
                        for obj in page.get("Contents", []):
                            if count < offset:
                                count += 1
                                continue
                            if len(documents) >= limit:
                                break

                            key = obj["Key"]
                            doc_type = self._get_doc_type(key)

                            documents.append(Document(
                                id=key,
                                source_id=key,
                                source_path=f"s3://{self.bucket}/{key}",
                                title=key.split("/")[-1],
                                doc_type=doc_type,
                                size_bytes=obj.get("Size"),
                                modified_at=obj.get("LastModified"),
                                metadata={"etag": obj.get("ETag")},
                            ))
                            count += 1
            else:
                # Sync boto3 with run_in_executor
                def list_sync():
                    docs = []
                    paginator = self.client.get_paginator("list_objects_v2")
                    count = 0
                    for page in paginator.paginate(
                        Bucket=self.bucket,
                        Prefix=search_prefix,
                        MaxKeys=limit + offset,
                    ):
                        for obj in page.get("Contents", []):
                            if count < offset:
                                count += 1
                                continue
                            if len(docs) >= limit:
                                return docs

                            key = obj["Key"]
                            doc_type = self._get_doc_type(key)

                            docs.append(Document(
                                id=key,
                                source_id=key,
                                source_path=f"s3://{self.bucket}/{key}",
                                title=key.split("/")[-1],
                                doc_type=doc_type,
                                size_bytes=obj.get("Size"),
                                modified_at=obj.get("LastModified"),
                                metadata={"etag": obj.get("ETag")},
                            ))
                            count += 1
                    return docs

                documents = await asyncio.get_event_loop().run_in_executor(None, list_sync)

        except Exception as e:
            logger.error(f"Error listing S3 documents: {e}")
            raise RAGProviderError(f"Failed to list documents: {e}")

        return documents

    async def get_document(self, source_id: str) -> Optional[Document]:
        import asyncio
        try:
            if self._use_async:
                async with self.session.client("s3", **self._get_client_kwargs()) as s3:
                    response = await s3.head_object(Bucket=self.bucket, Key=source_id)
            else:
                response = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.client.head_object(Bucket=self.bucket, Key=source_id)
                )

            return Document(
                id=source_id,
                source_id=source_id,
                source_path=f"s3://{self.bucket}/{source_id}",
                title=source_id.split("/")[-1],
                doc_type=self._get_doc_type(source_id),
                size_bytes=response.get("ContentLength"),
                modified_at=response.get("LastModified"),
                metadata={"etag": response.get("ETag")},
            )
        except Exception:
            return None

    async def get_document_content(self, source_id: str) -> Optional[str]:
        import asyncio
        try:
            if self._use_async:
                async with self.session.client("s3", **self._get_client_kwargs()) as s3:
                    response = await s3.get_object(Bucket=self.bucket, Key=source_id)
                    content = await response["Body"].read()
                    return content.decode("utf-8")
            else:
                def get_content_sync():
                    response = self.client.get_object(Bucket=self.bucket, Key=source_id)
                    return response["Body"].read().decode("utf-8")

                return await asyncio.get_event_loop().run_in_executor(None, get_content_sync)
        except Exception as e:
            logger.error(f"Error getting S3 document content: {e}")
            return None

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        # S3 doesn't support native search, return empty
        # Actual search happens through vector store
        return []

    def _get_doc_type(self, key: str) -> str:
        """Determine document type from file extension."""
        lower_key = key.lower()
        if lower_key.endswith(".pdf"):
            return "pdf"
        elif lower_key.endswith(".md"):
            return "markdown"
        elif lower_key.endswith(".html") or lower_key.endswith(".htm"):
            return "html"
        elif lower_key.endswith(".docx"):
            return "docx"
        elif lower_key.endswith(".csv"):
            return "csv"
        elif lower_key.endswith(".json"):
            return "json"
        elif lower_key.endswith((".py", ".js", ".ts", ".java", ".go", ".rs")):
            return "code"
        else:
            return "text"


class ElasticsearchProvider(RAGProvider):
    """Elasticsearch document store provider"""

    def __init__(self, config: RAGProviderConfig):
        super().__init__(config)
        self.client = None
        self.index = None

    async def connect(self) -> bool:
        try:
            self.hosts = self.config.connection_config.get("hosts", [])
            self.index = self.config.connection_config.get("index")
            self.api_key = self.config.connection_config.get("api_key")

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"ApiKey {self.api_key}"

            self.http_client = httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
                verify=self.config.connection_config.get("verify_ssl", True),
            )
            self.base_url = self.hosts[0] if self.hosts else "http://localhost:9200"

            health = await self.health_check()
            return health.get("status") == "healthy"

        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            return False

    async def disconnect(self) -> None:
        if self.http_client:
            await self.http_client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        try:
            start = datetime.utcnow()
            response = await self.http_client.get(f"{self.base_url}/_cluster/health")
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "healthy" if data.get("status") in ["green", "yellow"] else "unhealthy",
                    "latency_ms": latency,
                    "cluster_status": data.get("status"),
                    "error": None,
                }
            return {"status": "unhealthy", "latency_ms": latency, "error": response.text}
        except Exception as e:
            return {"status": "unhealthy", "latency_ms": 0, "error": str(e)}

    async def list_documents(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Document]:
        query = {"match_all": {}}
        if prefix:
            query = {"prefix": {"_id": prefix}}

        response = await self.http_client.post(
            f"{self.base_url}/{self.index}/_search",
            json={
                "query": query,
                "size": limit,
                "from": offset,
            },
        )

        if response.status_code != 200:
            raise RAGProviderError(f"Search failed: {response.text}")

        data = response.json()
        documents = []

        for hit in data.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            documents.append(Document(
                id=hit["_id"],
                source_id=hit["_id"],
                content=source.get("content", ""),
                title=source.get("title"),
                doc_type=source.get("doc_type", "text"),
                metadata=source,
            ))

        return documents

    async def get_document(self, source_id: str) -> Optional[Document]:
        response = await self.http_client.get(
            f"{self.base_url}/{self.index}/_doc/{source_id}"
        )

        if response.status_code != 200:
            return None

        data = response.json()
        source = data.get("_source", {})

        return Document(
            id=data["_id"],
            source_id=data["_id"],
            content=source.get("content", ""),
            title=source.get("title"),
            doc_type=source.get("doc_type", "text"),
            metadata=source,
        )

    async def get_document_content(self, source_id: str) -> Optional[str]:
        doc = await self.get_document(source_id)
        return doc.content if doc else None

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        es_query = {
            "bool": {
                "must": [
                    {"multi_match": {"query": query, "fields": ["content", "title"]}}
                ]
            }
        }

        if filters:
            es_query["bool"]["filter"] = [
                {"term": {k: v}} for k, v in filters.items()
            ]

        response = await self.http_client.post(
            f"{self.base_url}/{self.index}/_search",
            json={
                "query": es_query,
                "size": top_k,
            },
        )

        if response.status_code != 200:
            raise RAGProviderError(f"Search failed: {response.text}")

        data = response.json()
        documents = []

        for hit in data.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            documents.append(Document(
                id=hit["_id"],
                source_id=hit["_id"],
                content=source.get("content", ""),
                title=source.get("title"),
                doc_type=source.get("doc_type", "text"),
                metadata={**source, "_score": hit.get("_score")},
            ))

        return documents


class NotionProvider(RAGProvider):
    """Notion document store provider"""

    def __init__(self, config: RAGProviderConfig):
        super().__init__(config)
        self.http_client = None

    async def connect(self) -> bool:
        try:
            self.api_key = self.config.connection_config.get("api_key")
            self.database_ids = self.config.connection_config.get("database_ids", [])
            self.page_ids = self.config.connection_config.get("page_ids", [])

            self.http_client = httpx.AsyncClient(
                base_url="https://api.notion.com/v1",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            health = await self.health_check()
            return health.get("status") == "healthy"

        except Exception as e:
            logger.error(f"Failed to connect to Notion: {e}")
            return False

    async def disconnect(self) -> None:
        if self.http_client:
            await self.http_client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        try:
            start = datetime.utcnow()
            response = await self.http_client.get("/users/me")
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            if response.status_code == 200:
                return {"status": "healthy", "latency_ms": latency, "error": None}
            return {"status": "unhealthy", "latency_ms": latency, "error": response.text}
        except Exception as e:
            return {"status": "unhealthy", "latency_ms": 0, "error": str(e)}

    async def list_documents(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Document]:
        documents = []

        # Query each database
        for db_id in self.database_ids:
            response = await self.http_client.post(
                f"/databases/{db_id}/query",
                json={"page_size": limit},
            )

            if response.status_code == 200:
                data = response.json()
                for result in data.get("results", []):
                    doc = self._parse_notion_page(result)
                    if doc:
                        documents.append(doc)

        # Also include specific pages
        for page_id in self.page_ids:
            response = await self.http_client.get(f"/pages/{page_id}")
            if response.status_code == 200:
                doc = self._parse_notion_page(response.json())
                if doc:
                    documents.append(doc)

        return documents[:limit]

    async def get_document(self, source_id: str) -> Optional[Document]:
        response = await self.http_client.get(f"/pages/{source_id}")
        if response.status_code != 200:
            return None
        return self._parse_notion_page(response.json())

    async def get_document_content(self, source_id: str) -> Optional[str]:
        # Get page blocks
        blocks_content = []
        response = await self.http_client.get(f"/blocks/{source_id}/children")

        if response.status_code != 200:
            return None

        data = response.json()
        for block in data.get("results", []):
            text = self._extract_block_text(block)
            if text:
                blocks_content.append(text)

        return "\n\n".join(blocks_content)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        response = await self.http_client.post(
            "/search",
            json={
                "query": query,
                "page_size": top_k,
            },
        )

        if response.status_code != 200:
            return []

        data = response.json()
        documents = []

        for result in data.get("results", []):
            doc = self._parse_notion_page(result)
            if doc:
                documents.append(doc)

        return documents

    def _parse_notion_page(self, page: Dict[str, Any]) -> Optional[Document]:
        """Parse a Notion page into a Document."""
        try:
            page_id = page.get("id", "")
            properties = page.get("properties", {})

            # Try to get title from various property types
            title = ""
            for prop_name, prop_value in properties.items():
                if prop_value.get("type") == "title":
                    title_items = prop_value.get("title", [])
                    title = "".join(t.get("plain_text", "") for t in title_items)
                    break

            return Document(
                id=page_id,
                source_id=page_id,
                source_path=page.get("url"),
                title=title or page_id,
                doc_type="notion",
                modified_at=datetime.fromisoformat(
                    page.get("last_edited_time", "").replace("Z", "+00:00")
                ) if page.get("last_edited_time") else None,
                metadata={
                    "object": page.get("object"),
                    "parent": page.get("parent"),
                },
            )
        except Exception as e:
            logger.error(f"Error parsing Notion page: {e}")
            return None

    def _extract_block_text(self, block: Dict[str, Any]) -> Optional[str]:
        """Extract text from a Notion block."""
        block_type = block.get("type")
        block_content = block.get(block_type, {})

        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
            rich_text = block_content.get("rich_text", [])
            return "".join(t.get("plain_text", "") for t in rich_text)
        elif block_type == "code":
            rich_text = block_content.get("rich_text", [])
            return "```\n" + "".join(t.get("plain_text", "") for t in rich_text) + "\n```"

        return None


# Text chunking utilities
class TextChunker:
    """Utility for chunking text into smaller pieces."""

    @staticmethod
    def chunk_recursive(
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
    ) -> List[str]:
        """Recursive character text splitter."""
        if separators is None:
            separators = ["\n\n", "\n", " ", ""]

        chunks = []
        current_sep = separators[0] if separators else ""

        if len(text) <= chunk_size:
            return [text]

        # Split by current separator
        splits = text.split(current_sep) if current_sep else list(text)

        current_chunk = ""
        for split in splits:
            test_chunk = current_chunk + (current_sep if current_chunk else "") + split

            if len(test_chunk) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    # Overlap
                    overlap_start = max(0, len(current_chunk) - chunk_overlap)
                    current_chunk = current_chunk[overlap_start:] + current_sep + split
                else:
                    # Single split is too large, recurse with next separator
                    if len(separators) > 1:
                        sub_chunks = TextChunker.chunk_recursive(
                            split, chunk_size, chunk_overlap, separators[1:]
                        )
                        chunks.extend(sub_chunks)
                    else:
                        # Can't split further, just add
                        chunks.append(split[:chunk_size])
                        remaining = split[chunk_size - chunk_overlap:]
                        if remaining:
                            chunks.extend(
                                TextChunker.chunk_recursive(
                                    remaining, chunk_size, chunk_overlap, separators
                                )
                            )
            else:
                current_chunk = test_chunk

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    @staticmethod
    def chunk_by_sentences(
        text: str,
        max_sentences: int = 5,
        min_chunk_size: int = 100,
    ) -> List[str]:
        """Split text by sentence boundaries."""
        import re

        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []

        for sentence in sentences:
            current_chunk.append(sentence)

            if len(current_chunk) >= max_sentences:
                chunk_text = " ".join(current_chunk)
                if len(chunk_text) >= min_chunk_size:
                    chunks.append(chunk_text)
                    current_chunk = []

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            if chunk_text:
                chunks.append(chunk_text)

        return chunks


class DemoProvider(RAGProvider):
    """
    Demo document store provider for testing.
    Generates sample documents in-memory - no external services needed.
    """

    # Sample content for demo documents
    SAMPLE_CONTENT = [
        ("Getting Started Guide", "Welcome to our platform! This guide will help you get started with the basic features. First, create an account and configure your settings. Then, explore the dashboard to see your metrics and manage your resources."),
        ("API Reference", "Our REST API supports JSON payloads. Authentication uses Bearer tokens. Rate limits are 1000 requests per minute. Use the /v1/resources endpoint to list resources, POST to create, PUT to update, and DELETE to remove."),
        ("Architecture Overview", "The system consists of three main components: the API Gateway, Processing Engine, and Data Store. The API Gateway handles routing and authentication. The Processing Engine manages business logic. The Data Store provides persistence."),
        ("Troubleshooting FAQ", "Common issues and solutions: 1) Connection timeout - check your network settings. 2) Authentication failed - verify your API key. 3) Rate limited - reduce request frequency. 4) Invalid response - check request format."),
        ("Best Practices", "Follow these best practices for optimal performance: Use connection pooling, implement retries with exponential backoff, cache frequently accessed data, and monitor your resource usage through the dashboard."),
        ("Security Guidelines", "Security is our top priority. All data is encrypted at rest and in transit. We support SSO integration, role-based access control, and audit logging. Enable MFA for enhanced account security."),
        ("Release Notes v2.0", "New features in version 2.0: Improved performance by 40%, new dashboard analytics, webhook integrations, batch processing support, and enhanced error messages."),
        ("Integration Guide", "Integrate with popular services: Slack for notifications, GitHub for CI/CD triggers, Jira for issue tracking, and Datadog for monitoring. OAuth2 is used for all integrations."),
        ("Data Model Reference", "Core entities: Users, Organizations, Projects, Resources, and Events. Users belong to Organizations. Organizations contain Projects. Projects manage Resources. Events track all changes."),
        ("Deployment Guide", "Deploy using Docker or Kubernetes. Minimum requirements: 2 CPU cores, 4GB RAM, 20GB storage. Recommended: 4 CPU cores, 8GB RAM, 100GB SSD. Use environment variables for configuration."),
    ]

    def __init__(self, config: RAGProviderConfig):
        super().__init__(config)
        self.num_documents = config.connection_config.get("num_documents", 10)
        self.document_prefix = config.connection_config.get("document_prefix", "demo-doc")
        self._documents: Dict[str, Document] = {}
        self._initialized = False

    async def connect(self) -> bool:
        """Initialize demo documents"""
        self._documents = {}
        for i in range(min(self.num_documents, len(self.SAMPLE_CONTENT))):
            title, content = self.SAMPLE_CONTENT[i]
            doc_id = f"{self.document_prefix}-{i+1}"
            self._documents[doc_id] = Document(
                id=doc_id,
                source_id=doc_id,
                source_path=f"demo://{doc_id}",
                content=content,
                title=title,
                doc_type="text",
                size_bytes=len(content),
                modified_at=datetime.utcnow(),
                metadata={"demo": True, "index": i},
            )
        self._initialized = True
        logger.info(f"Demo provider initialized with {len(self._documents)} documents")
        return True

    async def disconnect(self) -> None:
        self._documents = {}
        self._initialized = False

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "unhealthy",
            "latency_ms": 1.0,
            "error": None,
            "document_count": len(self._documents),
        }

    async def list_documents(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Document]:
        docs = list(self._documents.values())
        if prefix:
            docs = [d for d in docs if d.source_id.startswith(prefix)]
        return docs[offset:offset + limit]

    async def get_document(self, source_id: str) -> Optional[Document]:
        return self._documents.get(source_id)

    async def get_document_content(self, source_id: str) -> Optional[str]:
        doc = self._documents.get(source_id)
        return doc.content if doc else None

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Simple keyword search for demo purposes"""
        query_lower = query.lower()
        results = []
        for doc in self._documents.values():
            score = 0
            content_lower = doc.content.lower()
            title_lower = (doc.title or "").lower()

            # Simple scoring: count query term occurrences
            for term in query_lower.split():
                if term in title_lower:
                    score += 2
                if term in content_lower:
                    score += content_lower.count(term)

            if score > 0:
                results.append((score, doc))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in results[:top_k]]


# Provider factory
def create_rag_provider(config: RAGProviderConfig) -> RAGProvider:
    """Factory function to create the appropriate RAG provider."""
    providers = {
        "s3": S3Provider,
        "elasticsearch": ElasticsearchProvider,
        "notion": NotionProvider,
        "demo": DemoProvider,
    }

    provider_class = providers.get(config.provider_type)
    if not provider_class:
        raise RAGProviderError(f"Unsupported provider type: {config.provider_type}")

    return provider_class(config)

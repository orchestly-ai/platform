"""
RAG Connector Models - BYOD (Bring Your Own Data)

Supports connecting to customer's document stores:
- S3/GCS/Azure Blob storage
- Elasticsearch
- MongoDB
- PostgreSQL (full-text search)
- Notion, Confluence, Google Drive
- Custom HTTP endpoints

We store ONLY the connection configuration.
Documents remain in customer's infrastructure.
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


class RAGProviderType(Enum):
    """Supported document store providers"""
    # Cloud Storage
    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"

    # Databases
    ELASTICSEARCH = "elasticsearch"
    OPENSEARCH = "opensearch"
    MONGODB = "mongodb"
    POSTGRESQL = "postgresql"

    # SaaS/Productivity
    NOTION = "notion"
    CONFLUENCE = "confluence"
    GOOGLE_DRIVE = "google_drive"
    SHAREPOINT = "sharepoint"

    # Custom
    CUSTOM = "custom"


class DocumentType(Enum):
    """Types of documents"""
    PDF = "pdf"
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"
    DOCX = "docx"
    CSV = "csv"
    JSON = "json"
    CODE = "code"


class ChunkingStrategy(Enum):
    """Document chunking strategies"""
    FIXED_SIZE = "fixed_size"           # Fixed character count
    SENTENCE = "sentence"               # Sentence boundaries
    PARAGRAPH = "paragraph"             # Paragraph boundaries
    SEMANTIC = "semantic"               # Semantic similarity
    RECURSIVE = "recursive"             # Recursive character splitting
    CODE = "code"                       # Code-aware splitting


class RAGConnectorConfigModel(Base):
    """
    RAG connector configuration per organization.

    Stores connection details for customer's document stores.
    We never store their documents - just how to access them.
    """
    __tablename__ = "rag_connector_configs"

    # Primary key
    config_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Provider details
    provider_type = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Connection configuration (encrypted at rest)
    connection_config = Column(JSON, nullable=False)

    # Chunking configuration
    chunking_strategy = Column(String(50), nullable=False, default="recursive")
    chunk_size = Column(Integer, nullable=False, default=1000)
    chunk_overlap = Column(Integer, nullable=False, default=200)

    # Vector store for embeddings (references memory provider)
    memory_provider_id = Column(UniversalUUID(), nullable=True)

    # Embedding configuration (if not using memory provider)
    embedding_provider = Column(String(50), nullable=True)
    embedding_model = Column(String(100), nullable=True)

    # Sync configuration
    sync_enabled = Column(Boolean, nullable=False, default=False)
    sync_interval_hours = Column(Integer, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(50), nullable=True)
    last_sync_documents = Column(Integer, nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    health_status = Column(String(50), nullable=True)
    last_health_check = Column(DateTime, nullable=True)

    # Usage stats
    total_documents = Column(Integer, nullable=False, default=0)
    total_chunks = Column(Integer, nullable=False, default=0)
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
        Index('idx_rag_connector_org', 'organization_id'),
        Index('idx_rag_connector_type', 'provider_type'),
        Index('idx_rag_connector_active', 'is_active'),
        Index('idx_rag_connector_default', 'organization_id', 'is_default'),
    )

    def __repr__(self):
        return f"<RAGConnectorConfig(id={self.config_id}, provider={self.provider_type}, name={self.name})>"


class RAGDocumentIndexModel(Base):
    """
    Index of documents from connected data sources.

    Tracks which documents have been indexed, when, and their chunk count.
    Actual content is not stored - only metadata for tracking.
    """
    __tablename__ = "rag_document_index"

    # Primary key
    document_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Organization and connector
    organization_id = Column(String(255), nullable=False, index=True)
    connector_id = Column(UniversalUUID(), nullable=False, index=True)

    # Document identification (from source)
    source_id = Column(String(500), nullable=False)  # ID in the source system
    source_path = Column(String(1000), nullable=True)  # Path/URL in source
    source_type = Column(String(50), nullable=False)  # pdf, markdown, etc.

    # Document metadata
    title = Column(String(500), nullable=True)
    content_hash = Column(String(64), nullable=True)  # SHA256 of content
    size_bytes = Column(Integer, nullable=True)

    # Indexing info
    chunk_count = Column(Integer, nullable=False, default=0)
    indexed_at = Column(DateTime, nullable=True)
    index_status = Column(String(50), nullable=False, default="pending")
    index_error = Column(Text, nullable=True)

    # Version tracking
    source_modified_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    needs_reindex = Column(Boolean, nullable=False, default=False)

    # Metadata from source
    source_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_doc_index_org', 'organization_id'),
        Index('idx_doc_index_connector', 'connector_id'),
        Index('idx_doc_index_source', 'connector_id', 'source_id'),
        Index('idx_doc_index_status', 'index_status'),
        Index('idx_doc_index_reindex', 'needs_reindex'),
    )

    def __repr__(self):
        return f"<RAGDocumentIndex(id={self.document_id}, source={self.source_id})>"


class RAGQueryHistoryModel(Base):
    """
    History of RAG queries for analytics and debugging.
    """
    __tablename__ = "rag_query_history"

    # Primary key
    query_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Organization and connector
    organization_id = Column(String(255), nullable=False, index=True)
    connector_id = Column(UniversalUUID(), nullable=True)

    # Query details
    query_text = Column(Text, nullable=False)
    query_type = Column(String(50), nullable=False, default="similarity")  # similarity, keyword, hybrid

    # Results
    results_count = Column(Integer, nullable=False, default=0)
    top_score = Column(Float, nullable=True)
    avg_score = Column(Float, nullable=True)

    # Performance
    latency_ms = Column(Float, nullable=True)

    # Context
    workflow_execution_id = Column(UniversalUUID(), nullable=True)
    agent_id = Column(String(255), nullable=True)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_rag_query_org', 'organization_id'),
        Index('idx_rag_query_connector', 'connector_id'),
        Index('idx_rag_query_time', 'created_at'),
    )


# Provider configuration schemas (for validation)
RAG_PROVIDER_CONFIG_SCHEMAS = {
    "s3": {
        "required": ["bucket", "region"],
        "optional": ["access_key", "secret_key", "prefix", "endpoint_url", "use_iam_role"],
        "example": {
            "bucket": "my-documents",
            "region": "us-east-1",
            "prefix": "knowledge-base/",
        }
    },
    "gcs": {
        "required": ["bucket"],
        "optional": ["credentials_json", "prefix", "project_id"],
        "example": {
            "bucket": "my-documents",
            "prefix": "knowledge-base/",
        }
    },
    "azure_blob": {
        "required": ["container", "connection_string"],
        "optional": ["prefix"],
        "example": {
            "container": "documents",
            "connection_string": "DefaultEndpointsProtocol=https;...",
        }
    },
    "elasticsearch": {
        "required": ["hosts", "index"],
        "optional": ["api_key", "username", "password", "cloud_id", "ca_certs"],
        "example": {
            "hosts": ["https://localhost:9200"],
            "index": "documents",
            "api_key": "your-api-key",
        }
    },
    "opensearch": {
        "required": ["hosts", "index"],
        "optional": ["username", "password", "aws_region", "use_ssl"],
        "example": {
            "hosts": ["https://search-domain.us-east-1.es.amazonaws.com"],
            "index": "documents",
        }
    },
    "mongodb": {
        "required": ["connection_string", "database", "collection"],
        "optional": ["text_field", "metadata_fields"],
        "example": {
            "connection_string": "mongodb+srv://user:pass@cluster.mongodb.net",
            "database": "knowledge",
            "collection": "documents",
        }
    },
    "postgresql": {
        "required": ["connection_string", "table"],
        "optional": ["text_column", "metadata_columns", "schema"],
        "example": {
            "connection_string": "postgresql://user:pass@host:5432/db",
            "table": "documents",
            "text_column": "content",
        }
    },
    "notion": {
        "required": ["api_key"],
        "optional": ["database_ids", "page_ids", "filter"],
        "example": {
            "api_key": "secret_...",
            "database_ids": ["database-id-1"],
        }
    },
    "confluence": {
        "required": ["url", "username", "api_token"],
        "optional": ["space_keys", "page_ids", "cql_query"],
        "example": {
            "url": "https://your-domain.atlassian.net/wiki",
            "username": "your-email@example.com",
            "api_token": "your-api-token",
            "space_keys": ["TEAM", "DOCS"],
        }
    },
    "google_drive": {
        "required": ["credentials_json"],
        "optional": ["folder_ids", "shared_drive_ids", "query"],
        "example": {
            "credentials_json": "{...service account json...}",
            "folder_ids": ["folder-id-1"],
        }
    },
    "sharepoint": {
        "required": ["site_url", "client_id", "client_secret", "tenant_id"],
        "optional": ["library_name", "folder_path"],
        "example": {
            "site_url": "https://yourorg.sharepoint.com/sites/team",
            "client_id": "app-client-id",
            "client_secret": "app-secret",
            "tenant_id": "tenant-id",
        }
    },
    "custom": {
        "required": ["base_url"],
        "optional": ["api_key", "headers", "list_endpoint", "get_endpoint", "search_endpoint"],
        "example": {
            "base_url": "https://your-api.com",
            "api_key": "your-api-key",
            "list_endpoint": "/documents",
            "search_endpoint": "/search",
        }
    },
    "demo": {
        "required": [],
        "optional": ["num_documents", "document_prefix"],
        "example": {
            "num_documents": 10,
            "document_prefix": "demo-doc",
        },
        "description": "Demo provider with sample documents for testing (no external services needed)"
    },
}


# Chunking strategy configurations
CHUNKING_CONFIGS = {
    "fixed_size": {
        "description": "Split by fixed character count",
        "params": ["chunk_size", "chunk_overlap"],
    },
    "sentence": {
        "description": "Split at sentence boundaries",
        "params": ["max_sentences", "min_chunk_size"],
    },
    "paragraph": {
        "description": "Split at paragraph boundaries",
        "params": ["max_paragraphs", "min_chunk_size"],
    },
    "semantic": {
        "description": "Split by semantic similarity",
        "params": ["similarity_threshold", "max_chunk_size"],
    },
    "recursive": {
        "description": "Recursive character text splitter",
        "params": ["chunk_size", "chunk_overlap", "separators"],
    },
    "code": {
        "description": "Language-aware code splitting",
        "params": ["language", "chunk_size", "chunk_overlap"],
    },
}

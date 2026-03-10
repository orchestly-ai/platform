"""Shared utilities and models for Agent Orchestration Platform."""

__version__ = "0.1.0"

# Database session - provide compatibility aliases
try:
    from backend.database.session import Base, AsyncSessionLocal, get_db
    # Alias for demos that expect SessionLocal
    SessionLocal = AsyncSessionLocal
except ImportError:
    pass

# LLM Service - provide compatibility alias
try:
    from backend.shared.llm_service import LLMRoutingService
    # Alias for demos that expect LLMService
    LLMService = LLMRoutingService
except ImportError:
    pass

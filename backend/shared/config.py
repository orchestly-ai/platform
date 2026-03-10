"""Configuration management for Agent Orchestration Platform."""

import os
import secrets
import warnings
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

# Get absolute path to .env file (config.py is in backend/shared/, .env is in agent-orchestration/)
_ENV_FILE_PATH = (Path(__file__).parent.parent.parent / ".env").resolve()

# Debug: Print the path to help troubleshoot
import logging
_logger = logging.getLogger(__name__)
_logger.info(f"Looking for .env at: {_ENV_FILE_PATH} (exists: {_ENV_FILE_PATH.exists()})")


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # ========================================================================
    # Application
    # ========================================================================
    APP_NAME: str = "Agent Orchestration Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    ENVIRONMENT: str = Field(default="development", description="dev/staging/production")

    # ========================================================================
    # API Server
    # ========================================================================
    API_HOST: str = Field(default="0.0.0.0", description="API server host")
    API_PORT: int = Field(default=8000, description="API server port")
    API_WORKERS: int = Field(default=4, description="Number of worker processes")

    # ========================================================================
    # Database
    # ========================================================================
    USE_SQLITE: bool = Field(default=False, description="Use SQLite instead of PostgreSQL")
    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL host")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port")
    POSTGRES_DB: str = Field(default="agent_orchestrator", description="Database name")
    POSTGRES_USER: str = Field(default="postgres", description="Database user")
    POSTGRES_PASSWORD: str = Field(default="postgres", description="Database password")

    @property
    def DATABASE_URL(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ========================================================================
    # Redis
    # ========================================================================
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password")

    @property
    def REDIS_URL(self) -> str:
        """Construct Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ========================================================================
    # Authentication
    # ========================================================================
    API_KEY_HEADER: str = Field(default="X-API-Key", description="API key header name")
    API_KEY_LENGTH: int = Field(default=32, description="Generated API key length")
    JWT_SECRET_KEY: str = Field(
        default="",
        description="JWT signing secret (min 32 chars). Auto-generated if empty."
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440, description="JWT token expiration (24 hours)")
    JWT_EXPIRATION_HOURS: int = Field(default=24, description="JWT token expiration (deprecated, use JWT_ACCESS_TOKEN_EXPIRE_MINUTES)")

    # ========================================================================
    # LLM Providers
    # ========================================================================
    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    OPENAI_ORG_ID: Optional[str] = Field(default=None, description="OpenAI organization ID")
    OPENAI_DEFAULT_MODEL: str = Field(default="gpt-4", description="Default OpenAI model")

    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API key")
    ANTHROPIC_DEFAULT_MODEL: str = Field(default="claude-3-5-sonnet-20241022", description="Default Claude model")

    # Groq (fast inference)
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API key")

    # Google (Gemini)
    GOOGLE_API_KEY: Optional[str] = Field(default=None, description="Google API key")

    # DeepSeek
    DEEPSEEK_API_KEY: Optional[str] = Field(default=None, description="DeepSeek API key")

    # Azure OpenAI
    AZURE_OPENAI_API_KEY: Optional[str] = Field(default=None, description="Azure OpenAI API key")
    AZURE_OPENAI_ENDPOINT: Optional[str] = Field(default=None, description="Azure OpenAI endpoint")
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-02-15-preview", description="API version")

    # Ollama (local)
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", description="Ollama API URL")

    # ========================================================================
    # Cost Limits (Defaults)
    # ========================================================================
    DEFAULT_AGENT_DAILY_COST_LIMIT: float = Field(default=100.0, description="Default daily cost limit USD")
    DEFAULT_AGENT_MONTHLY_COST_LIMIT: float = Field(default=3000.0, description="Default monthly cost limit USD")
    SYSTEM_DAILY_COST_LIMIT: float = Field(default=10000.0, description="System-wide daily limit USD")
    SYSTEM_MONTHLY_COST_LIMIT: float = Field(default=300000.0, description="System-wide monthly limit USD")

    # ========================================================================
    # Task Configuration
    # ========================================================================
    DEFAULT_TASK_TIMEOUT_SECONDS: int = Field(default=300, description="Default task timeout")
    MAX_TASK_TIMEOUT_SECONDS: int = Field(default=3600, description="Maximum task timeout")
    DEFAULT_MAX_RETRIES: int = Field(default=3, description="Default task retry count")
    MAX_CONCURRENT_TASKS_PER_AGENT: int = Field(default=5, description="Max concurrent tasks per agent")

    # ========================================================================
    # Queue Configuration
    # ========================================================================
    TASK_QUEUE_NAME: str = Field(default="agent_tasks", description="Task queue name")
    RESULT_QUEUE_NAME: str = Field(default="task_results", description="Result queue name")
    QUEUE_TTL_SECONDS: int = Field(default=86400, description="Queue message TTL (24 hours)")

    # ========================================================================
    # Observability
    # ========================================================================
    ENABLE_METRICS: bool = Field(default=True, description="Enable Prometheus metrics")
    METRICS_PORT: int = Field(default=9090, description="Prometheus metrics port")
    ENABLE_TRACING: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    JAEGER_ENDPOINT: Optional[str] = Field(default=None, description="Jaeger collector endpoint")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format: json or text")
    LOG_FILE: Optional[str] = Field(default=None, description="Log file path")

    # ========================================================================
    # Rate Limiting
    # ========================================================================
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=100, description="Requests per minute")
    RATE_LIMIT_REQUESTS_PER_HOUR: int = Field(default=5000, description="Requests per hour")

    # ========================================================================
    # CORS
    # ========================================================================
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001", "http://localhost:3040"],
        description="Allowed CORS origins"
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, description="Allow credentials")

    # ========================================================================
    # Feature Flags
    # ========================================================================
    ENABLE_VISUAL_WORKFLOW_DESIGNER: bool = Field(default=False, description="Enable workflow designer")
    ENABLE_ML_ROUTING: bool = Field(default=False, description="Enable ML-based routing")
    ENABLE_CONFLICT_DETECTION: bool = Field(default=True, description="Enable agent conflict detection")
    ENABLE_EXTENDED_ROUTERS: bool = Field(default=False, description="Enable extended API routers (marketplace, integrations)")

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        """Ensure JWT_SECRET_KEY is set. Auto-generate for dev, reject in production."""
        insecure_defaults = {"", "your-secret-key-change-in-production-min-32-chars",
                             "your-secret-key-change-this-in-production"}
        if self.JWT_SECRET_KEY in insecure_defaults:
            if self.ENVIRONMENT == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be explicitly set in production. "
                    "Generate one with: python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
            # Auto-generate for development/staging and warn
            self.JWT_SECRET_KEY = secrets.token_urlsafe(48)
            warnings.warn(
                "JWT_SECRET_KEY not set — using auto-generated ephemeral secret. "
                "JWTs will be invalidated on restart. Set JWT_SECRET_KEY in .env for persistence.",
                stacklevel=2,
            )
        elif len(self.JWT_SECRET_KEY) < 32:
            warnings.warn(
                f"JWT_SECRET_KEY is only {len(self.JWT_SECRET_KEY)} chars (min 32 recommended).",
                stacklevel=2,
            )
        return self

    class Config:
        """Pydantic config."""
        env_file = str(_ENV_FILE_PATH)
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings

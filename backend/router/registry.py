"""
Model Registry

Manages available LLM models with their costs, capabilities, and metadata.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import RouterModelModel


class ModelInfo:
    """Information about an available LLM model."""

    def __init__(
        self,
        id: str,
        provider: str,
        model_name: str,
        display_name: Optional[str] = None,
        cost_per_1k_input_tokens: Optional[float] = None,
        cost_per_1k_output_tokens: Optional[float] = None,
        max_tokens: Optional[int] = None,
        supports_vision: bool = False,
        supports_tools: bool = False,
        quality_score: float = 0.8,
        is_enabled: bool = True,
    ):
        self.id = id
        self.provider = provider
        self.model_name = model_name
        self.display_name = display_name or model_name
        self.cost_per_1k_input_tokens = cost_per_1k_input_tokens
        self.cost_per_1k_output_tokens = cost_per_1k_output_tokens
        self.max_tokens = max_tokens
        self.supports_vision = supports_vision
        self.supports_tools = supports_tools
        self.quality_score = quality_score
        self.is_enabled = is_enabled

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "provider": self.provider,
            "model_name": self.model_name,
            "display_name": self.display_name,
            "cost_per_1k_input_tokens": self.cost_per_1k_input_tokens,
            "cost_per_1k_output_tokens": self.cost_per_1k_output_tokens,
            "max_tokens": self.max_tokens,
            "supports_vision": self.supports_vision,
            "supports_tools": self.supports_tools,
            "quality_score": self.quality_score,
            "is_enabled": self.is_enabled,
        }


class ModelRegistry:
    """
    Registry for tracking available LLM models.

    Manages model definitions, costs, and capabilities.
    """

    def __init__(self, db: AsyncSession):
        """Initialize model registry."""
        self.db = db

    async def register_model(
        self,
        organization_id: str,
        provider: str,
        model_name: str,
        display_name: Optional[str] = None,
        cost_per_1k_input_tokens: Optional[float] = None,
        cost_per_1k_output_tokens: Optional[float] = None,
        max_tokens: Optional[int] = None,
        supports_vision: bool = False,
        supports_tools: bool = False,
        quality_score: float = 0.8,
    ) -> ModelInfo:
        """Register a new LLM model."""
        model_id = str(uuid4())

        model = RouterModelModel(
            id=model_id,
            organization_id=organization_id,
            provider=provider,
            model_name=model_name,
            display_name=display_name or model_name,
            cost_per_1k_input_tokens=cost_per_1k_input_tokens,
            cost_per_1k_output_tokens=cost_per_1k_output_tokens,
            max_tokens=max_tokens,
            supports_vision=supports_vision,
            supports_tools=supports_tools,
            quality_score=quality_score,
            is_enabled=True,
        )

        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)

        return self._model_to_info(model)

    async def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get model by ID."""
        result = await self.db.execute(
            select(RouterModelModel).where(RouterModelModel.id == model_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_info(model)

    async def list_models(
        self,
        organization_id: str,
        provider: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[ModelInfo]:
        """List available models."""
        stmt = select(RouterModelModel).where(
            RouterModelModel.organization_id == organization_id
        )

        if provider:
            stmt = stmt.where(RouterModelModel.provider == provider)

        if enabled_only:
            stmt = stmt.where(RouterModelModel.is_enabled == True)

        result = await self.db.execute(stmt)
        models = result.scalars().all()

        return [self._model_to_info(m) for m in models]

    async def update_model(
        self,
        model_id: str,
        **kwargs
    ) -> Optional[ModelInfo]:
        """Update model configuration."""
        result = await self.db.execute(
            select(RouterModelModel).where(RouterModelModel.id == model_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Update allowed fields
        allowed_fields = {
            'display_name', 'cost_per_1k_input_tokens', 'cost_per_1k_output_tokens',
            'max_tokens', 'supports_vision', 'supports_tools', 'quality_score', 'is_enabled'
        }

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(model, key, value)

        model.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(model)

        return self._model_to_info(model)

    async def enable_model(self, model_id: str) -> bool:
        """Enable a model."""
        return await self.update_model(model_id, is_enabled=True) is not None

    async def disable_model(self, model_id: str) -> bool:
        """Disable a model."""
        return await self.update_model(model_id, is_enabled=False) is not None

    async def delete_model(self, model_id: str) -> bool:
        """Delete a model."""
        result = await self.db.execute(
            select(RouterModelModel).where(RouterModelModel.id == model_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return False

        await self.db.delete(model)
        await self.db.flush()
        return True

    def _model_to_info(self, model: RouterModelModel) -> ModelInfo:
        """Convert database model to ModelInfo."""
        return ModelInfo(
            id=model.id,
            provider=model.provider,
            model_name=model.model_name,
            display_name=model.display_name,
            cost_per_1k_input_tokens=model.cost_per_1k_input_tokens,
            cost_per_1k_output_tokens=model.cost_per_1k_output_tokens,
            max_tokens=model.max_tokens,
            supports_vision=model.supports_vision,
            supports_tools=model.supports_tools,
            quality_score=model.quality_score,
            is_enabled=model.is_enabled,
        )

    async def seed_default_models(self, organization_id: str):
        """Seed default popular models."""
        default_models = [
            # OpenAI models
            {
                "provider": "openai",
                "model_name": "gpt-4o",
                "display_name": "GPT-4o",
                "cost_per_1k_input_tokens": 0.0025,
                "cost_per_1k_output_tokens": 0.01,
                "max_tokens": 128000,
                "supports_vision": True,
                "supports_tools": True,
                "quality_score": 0.95,
            },
            {
                "provider": "openai",
                "model_name": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "cost_per_1k_input_tokens": 0.00015,
                "cost_per_1k_output_tokens": 0.0006,
                "max_tokens": 128000,
                "supports_vision": True,
                "supports_tools": True,
                "quality_score": 0.85,
            },
            {
                "provider": "openai",
                "model_name": "gpt-3.5-turbo",
                "display_name": "GPT-3.5 Turbo",
                "cost_per_1k_input_tokens": 0.0005,
                "cost_per_1k_output_tokens": 0.0015,
                "max_tokens": 16385,
                "supports_vision": False,
                "supports_tools": True,
                "quality_score": 0.75,
            },
            # Anthropic models
            {
                "provider": "anthropic",
                "model_name": "claude-3-opus-20240229",
                "display_name": "Claude 3 Opus",
                "cost_per_1k_input_tokens": 0.015,
                "cost_per_1k_output_tokens": 0.075,
                "max_tokens": 200000,
                "supports_vision": True,
                "supports_tools": True,
                "quality_score": 0.98,
            },
            {
                "provider": "anthropic",
                "model_name": "claude-3-sonnet-20240229",
                "display_name": "Claude 3 Sonnet",
                "cost_per_1k_input_tokens": 0.003,
                "cost_per_1k_output_tokens": 0.015,
                "max_tokens": 200000,
                "supports_vision": True,
                "supports_tools": True,
                "quality_score": 0.92,
            },
            {
                "provider": "anthropic",
                "model_name": "claude-3-haiku-20240307",
                "display_name": "Claude 3 Haiku",
                "cost_per_1k_input_tokens": 0.00025,
                "cost_per_1k_output_tokens": 0.00125,
                "max_tokens": 200000,
                "supports_vision": True,
                "supports_tools": True,
                "quality_score": 0.82,
            },
            # Google models
            {
                "provider": "google",
                "model_name": "gemini-pro",
                "display_name": "Gemini Pro",
                "cost_per_1k_input_tokens": 0.000125,
                "cost_per_1k_output_tokens": 0.000375,
                "max_tokens": 32768,
                "supports_vision": False,
                "supports_tools": True,
                "quality_score": 0.88,
            },
        ]

        for model_config in default_models:
            # Check if model already exists
            stmt = select(RouterModelModel).where(
                RouterModelModel.organization_id == organization_id,
                RouterModelModel.provider == model_config["provider"],
                RouterModelModel.model_name == model_config["model_name"],
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                await self.register_model(organization_id=organization_id, **model_config)


def get_model_registry(db: AsyncSession) -> ModelRegistry:
    """Get model registry instance."""
    return ModelRegistry(db)

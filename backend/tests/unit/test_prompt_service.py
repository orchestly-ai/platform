"""
Unit Tests for Prompt Service

Tests for prompt template management, versioning, and rendering.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from backend.shared.prompt_service import PromptService


class TestPromptServiceHelpers:
    """Tests for static helper methods."""

    def test_generate_slug_basic(self):
        """Test basic slug generation."""
        assert PromptService._generate_slug("Hello World") == "hello-world"

    def test_generate_slug_special_chars(self):
        """Test slug generation with special characters."""
        assert PromptService._generate_slug("Hello! World?") == "hello-world"

    def test_generate_slug_multiple_spaces(self):
        """Test slug generation with multiple spaces."""
        assert PromptService._generate_slug("Hello   World") == "hello-world"

    def test_generate_slug_leading_trailing(self):
        """Test slug generation with leading/trailing special chars."""
        assert PromptService._generate_slug("--Hello World--") == "hello-world"

    def test_generate_slug_numbers(self):
        """Test slug generation with numbers."""
        assert PromptService._generate_slug("Version 2.0 Release") == "version-2-0-release"

    def test_extract_variables_single(self):
        """Test extracting single variable."""
        content = "Hello {{name}}!"
        assert PromptService._extract_variables(content) == ["name"]

    def test_extract_variables_multiple(self):
        """Test extracting multiple variables."""
        content = "Hello {{name}}, your order {{order_id}} is ready."
        variables = PromptService._extract_variables(content)
        assert set(variables) == {"name", "order_id"}

    def test_extract_variables_duplicates(self):
        """Test that duplicate variables are deduplicated."""
        content = "{{name}} said hello to {{name}}"
        variables = PromptService._extract_variables(content)
        assert variables == ["name"]

    def test_extract_variables_none(self):
        """Test content with no variables."""
        content = "Hello world, no variables here!"
        assert PromptService._extract_variables(content) == []

    def test_extract_variables_nested_braces(self):
        """Test that invalid nested braces are ignored."""
        content = "Hello {{{name}}} world"
        # Should still extract 'name' from the valid pattern
        variables = PromptService._extract_variables(content)
        assert "name" in variables

    def test_render_prompt_basic(self):
        """Test basic prompt rendering."""
        content = "Hello {{name}}!"
        variables = {"name": "World"}
        result = PromptService._render_prompt(content, variables)
        assert result == "Hello World!"

    def test_render_prompt_multiple_vars(self):
        """Test rendering with multiple variables."""
        content = "{{greeting}} {{name}}, your order {{order_id}} is ready."
        variables = {"greeting": "Hello", "name": "John", "order_id": "12345"}
        result = PromptService._render_prompt(content, variables)
        assert result == "Hello John, your order 12345 is ready."

    def test_render_prompt_missing_variable(self):
        """Test that missing variables raise ValueError."""
        content = "Hello {{name}}, your order {{order_id}} is ready."
        variables = {"name": "John"}  # Missing order_id
        with pytest.raises(ValueError) as exc_info:
            PromptService._render_prompt(content, variables)
        assert "order_id" in str(exc_info.value)

    def test_render_prompt_extra_variables(self):
        """Test that extra variables are ignored."""
        content = "Hello {{name}}!"
        variables = {"name": "World", "extra": "ignored"}
        result = PromptService._render_prompt(content, variables)
        assert result == "Hello World!"

    def test_render_prompt_numeric_value(self):
        """Test rendering with numeric values."""
        content = "Your score is {{score}} out of {{total}}."
        variables = {"score": 85, "total": 100}
        result = PromptService._render_prompt(content, variables)
        assert result == "Your score is 85 out of 100."

    def test_render_prompt_empty_string(self):
        """Test rendering with empty string value."""
        content = "Hello {{name}}!"
        variables = {"name": ""}
        result = PromptService._render_prompt(content, variables)
        assert result == "Hello !"


class TestPromptServiceAsync:
    """Tests for async database methods."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_template(self, mock_db):
        """Test template creation."""
        org_id = uuid4()

        # Mock the execute to return empty (no existing template)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute.return_value = mock_result

        template = await PromptService.create_template(
            db=mock_db,
            organization_id=org_id,
            name="Test Template",
            description="A test template",
            category="testing"
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_template_by_slug(self, mock_db):
        """Test getting template by organization and slug."""
        organization_id = uuid4()
        slug = "test-template"

        mock_template = MagicMock()
        mock_template.slug = slug
        mock_template.name = "Test Template"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_template)
        mock_db.execute.return_value = mock_result

        result = await PromptService.get_template(
            db=mock_db,
            organization_id=organization_id,
            slug=slug
        )

        assert result is not None
        assert result.slug == slug

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, mock_db):
        """Test getting non-existent template."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute.return_value = mock_result

        result = await PromptService.get_template(
            db=mock_db,
            organization_id=uuid4(),
            slug="nonexistent"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_render_prompt_with_version(self, mock_db):
        """Test rendering prompt with specific version."""
        organization_id = uuid4()
        slug = "greeting-template"
        template_id = uuid4()

        # Mock template
        mock_template = MagicMock()
        mock_template.template_id = template_id

        # Mock version with actual string content
        mock_version = MagicMock()
        mock_version.content = "Hello {{name}}, welcome to {{company}}!"
        mock_version.is_published = True

        call_count = [0]
        async def execute_side_effect(stmt):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: get template
                result.scalar_one_or_none = MagicMock(return_value=mock_template)
            else:
                # Subsequent calls: get version
                result.scalar_one_or_none = MagicMock(return_value=mock_version)
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        # render_prompt returns a dict with rendered content
        result = await PromptService.render_prompt(
            db=mock_db,
            organization_id=organization_id,
            slug=slug,
            variables={"name": "John", "company": "Acme"},
            version="1.0.0"
        )

        # Verify the method was called
        assert mock_db.execute.called


class TestPromptVersioning:
    """Tests for version management."""

    def test_version_format(self):
        """Test semantic version format."""
        # Valid versions
        valid_versions = ["1.0.0", "2.1.0", "10.20.30"]
        for v in valid_versions:
            parts = v.split(".")
            assert len(parts) == 3
            assert all(p.isdigit() for p in parts)

    def test_version_comparison(self):
        """Test version string comparison."""
        # Lexicographic comparison works for same-length versions
        assert "1.0.1" > "1.0.0"
        assert "2.0.0" > "1.9.9"
        assert "1.1.0" > "1.0.9"


class TestPromptUsageTracking:
    """Tests for usage analytics."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_track_usage_creates_record(self, mock_db):
        """Test that usage tracking creates a stats record."""
        version_id = uuid4()

        # Mock no existing stats
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute.return_value = mock_result

        # track_usage signature: (db, version_id, latency_ms, tokens, success)
        await PromptService.track_usage(
            db=mock_db,
            version_id=version_id,
            latency_ms=500.0,
            tokens=100,
            success=True
        )

        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_track_usage_updates_existing(self, mock_db):
        """Test that usage tracking can handle existing stats."""
        version_id = uuid4()

        # Mock existing stats (with real integer values that can be incremented)
        mock_stats = MagicMock()
        mock_stats.total_uses = 10
        mock_stats.total_tokens = 1000
        mock_stats.successful_uses = 9
        mock_stats.failed_uses = 1
        mock_stats.total_latency_ms = 4500.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_stats)
        mock_db.execute.return_value = mock_result

        # track_usage signature: (db, version_id, latency_ms, tokens, success)
        await PromptService.track_usage(
            db=mock_db,
            version_id=version_id,
            latency_ms=500.0,
            tokens=100,
            success=True
        )

        # Verify database operations were performed
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

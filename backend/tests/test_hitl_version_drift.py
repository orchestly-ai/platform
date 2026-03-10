"""
HITL Version Drift Service Tests

Tests for ROADMAP.md Section: Agent Version Checking for HITL Resume

Test Coverage:
- Version drift detection (none, patch, minor, major)
- Breaking vs non-breaking change handling
- Hot-reload for non-breaking changes
- Block resume for breaking changes
- Config and prompt hash change detection
- Changelog tracking
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

from backend.shared.hitl_version_service import (
    HITLVersionService,
    DriftType,
    ResumeAction,
    VersionInfo,
    VersionCheckResult,
    SuspendedExecution,
    ResumeResult,
    ChangelogEntry,
    get_hitl_version_service,
    reset_hitl_version_service,
)


@pytest.fixture
def version_service():
    """Create a fresh HITLVersionService instance for testing."""
    reset_hitl_version_service()
    return HITLVersionService(db=None)


@pytest.fixture
def execution_id():
    """Create a sample execution ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Create a sample agent ID."""
    return "agent-customer-service-v1"


# =============================================================================
# Version Parsing Tests
# =============================================================================

def test_parse_version_standard():
    """Should parse standard semver version."""
    major, minor, patch = VersionInfo.parse_version("1.2.3")
    assert (major, minor, patch) == (1, 2, 3)


def test_parse_version_with_v_prefix():
    """Should parse version with 'v' prefix."""
    major, minor, patch = VersionInfo.parse_version("v2.1.0")
    assert (major, minor, patch) == (2, 1, 0)


def test_parse_version_with_prerelease():
    """Should parse version with prerelease tag."""
    major, minor, patch = VersionInfo.parse_version("1.0.0-beta.1")
    assert (major, minor, patch) == (1, 0, 0)


def test_parse_version_incomplete():
    """Should handle incomplete versions."""
    assert VersionInfo.parse_version("1") == (1, 0, 0)
    assert VersionInfo.parse_version("1.2") == (1, 2, 0)


def test_parse_version_invalid():
    """Should handle invalid versions gracefully."""
    assert VersionInfo.parse_version("invalid") == (0, 0, 0)
    assert VersionInfo.parse_version("") == (0, 0, 0)


# =============================================================================
# Suspension Recording Tests
# =============================================================================

@pytest.mark.asyncio
async def test_record_suspension(version_service, execution_id, agent_id):
    """Should record suspension with version info."""
    suspended = await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
        agent_config_hash="config-hash-123",
        agent_prompt_hash="prompt-hash-456",
        context={"task": "customer_inquiry"},
    )

    assert suspended.execution_id == execution_id
    assert suspended.agent_id == agent_id
    assert suspended.agent_version == "1.0.0"
    assert suspended.agent_config_hash == "config-hash-123"
    assert suspended.agent_prompt_hash == "prompt-hash-456"
    assert suspended.resume_token is not None
    assert suspended.context["task"] == "customer_inquiry"


@pytest.mark.asyncio
async def test_record_suspension_creates_resume_token(version_service, execution_id, agent_id):
    """Each suspension should get a unique resume token."""
    suspended1 = await version_service.record_suspension(
        execution_id=uuid4(),
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    suspended2 = await version_service.record_suspension(
        execution_id=uuid4(),
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    assert suspended1.resume_token != suspended2.resume_token


# =============================================================================
# Version Check Tests - No Drift
# =============================================================================

@pytest.mark.asyncio
async def test_version_check_no_drift(version_service, execution_id, agent_id):
    """Should detect no drift when version unchanged."""
    # Record suspension
    await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    # Register same version as current
    await version_service.register_agent_version(
        agent_id=agent_id,
        version="1.0.0",
    )

    # Check version
    result = await version_service.check_version_before_resume(execution_id)

    assert result.needs_reload is False
    assert result.drift_type == DriftType.NONE
    assert result.action == ResumeAction.PROCEED
    assert result.is_breaking_change is False


# =============================================================================
# Version Check Tests - Patch/Minor (Hot-Reload)
# =============================================================================

@pytest.mark.asyncio
async def test_version_check_patch_drift(version_service, execution_id, agent_id):
    """Patch version change should trigger hot-reload."""
    await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="1.0.1",  # Patch bump
    )

    result = await version_service.check_version_before_resume(execution_id)

    assert result.needs_reload is True
    assert result.drift_type == DriftType.PATCH
    assert result.action == ResumeAction.HOT_RELOAD
    assert result.is_breaking_change is False
    assert result.original_version == "1.0.0"
    assert result.current_version == "1.0.1"


@pytest.mark.asyncio
async def test_version_check_minor_drift(version_service, execution_id, agent_id):
    """Minor version change should trigger hot-reload."""
    await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="1.1.0",  # Minor bump
    )

    result = await version_service.check_version_before_resume(execution_id)

    assert result.needs_reload is True
    assert result.drift_type == DriftType.MINOR
    assert result.action == ResumeAction.HOT_RELOAD
    assert result.is_breaking_change is False


# =============================================================================
# Version Check Tests - Major (Block)
# =============================================================================

@pytest.mark.asyncio
async def test_version_check_major_drift_blocks(version_service, execution_id, agent_id):
    """Major version change should block resume."""
    await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="2.0.0",  # Major bump
    )

    result = await version_service.check_version_before_resume(execution_id)

    assert result.needs_reload is True
    assert result.drift_type == DriftType.MAJOR
    assert result.action == ResumeAction.BLOCK
    assert result.is_breaking_change is True


@pytest.mark.asyncio
async def test_version_check_breaking_changelog_blocks(version_service, execution_id, agent_id):
    """Breaking changelog entry should block resume even with minor bump."""
    await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="1.1.0",  # Minor bump, but...
    )

    # Add breaking changelog entry
    await version_service.add_changelog_entry(
        agent_id=agent_id,
        version="1.1.0",
        changes=["Changed response format"],
        is_breaking=True,
        breaking_reason="Response JSON structure changed",
    )

    result = await version_service.check_version_before_resume(execution_id)

    assert result.is_breaking_change is True
    assert result.action == ResumeAction.BLOCK
    assert len(result.changelog) == 1
    assert result.changelog[0]["is_breaking"] is True


# =============================================================================
# Config/Prompt Hash Tests
# =============================================================================

@pytest.mark.asyncio
async def test_config_hash_change_triggers_reload(version_service, execution_id, agent_id):
    """Config hash change with same version should trigger hot-reload."""
    await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
        agent_config_hash="config-hash-old",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="1.0.0",  # Same version
        config_hash="config-hash-new",  # Different config
    )

    result = await version_service.check_version_before_resume(execution_id)

    assert result.needs_reload is True
    assert result.drift_type == DriftType.CONFIG_CHANGE
    assert result.action == ResumeAction.HOT_RELOAD


@pytest.mark.asyncio
async def test_prompt_hash_change_blocks(version_service, execution_id, agent_id):
    """Prompt hash change should block resume (breaking change)."""
    await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
        agent_prompt_hash="prompt-hash-old",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="1.0.0",
        prompt_hash="prompt-hash-new",  # Different prompt
    )

    result = await version_service.check_version_before_resume(execution_id)

    assert result.needs_reload is True
    assert result.drift_type == DriftType.PROMPT_CHANGE
    assert result.action == ResumeAction.BLOCK
    assert result.is_breaking_change is True


# =============================================================================
# Resume Execution Tests
# =============================================================================

@pytest.mark.asyncio
async def test_resume_approved_same_version(version_service, agent_id):
    """Resume should succeed when approved with same version."""
    execution_id = uuid4()
    suspended = await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="1.0.0",
    )

    result = await version_service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )

    assert result.success is True
    assert result.status == "resumed"
    assert result.hot_reload_applied is False


@pytest.mark.asyncio
async def test_resume_with_hot_reload(version_service, agent_id):
    """Resume should apply hot-reload for non-breaking changes."""
    execution_id = uuid4()
    suspended = await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="1.0.1",  # Patch bump
    )

    result = await version_service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )

    assert result.success is True
    assert result.status == "hot_reloaded"
    assert result.hot_reload_applied is True
    assert result.version_check.drift_type == DriftType.PATCH


@pytest.mark.asyncio
async def test_resume_blocked_for_breaking_change(version_service, agent_id):
    """Resume should be blocked for breaking changes."""
    execution_id = uuid4()
    suspended = await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="2.0.0",  # Major bump
    )

    result = await version_service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )

    assert result.success is False
    assert result.status == "blocked"
    assert result.version_check.is_breaking_change is True


@pytest.mark.asyncio
async def test_resume_force_overrides_block(version_service, agent_id):
    """Force resume should override breaking change block."""
    execution_id = uuid4()
    suspended = await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="2.0.0",  # Major bump - would normally block
    )

    result = await version_service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="admin@company.com",
        force_resume=True,  # Force override
    )

    assert result.success is True
    assert result.status == "hot_reloaded"


@pytest.mark.asyncio
async def test_resume_rejected_no_version_check(version_service, agent_id):
    """Rejection should not check version."""
    execution_id = uuid4()
    suspended = await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    # Don't register current version - normally would warn
    # But rejection should skip version check

    result = await version_service.resume_execution(
        resume_token=suspended.resume_token,
        approved=False,
        responded_by="reviewer@company.com",
    )

    assert result.success is True
    assert result.status == "rejected"
    assert result.version_check is None


@pytest.mark.asyncio
async def test_resume_invalid_token(version_service):
    """Resume with invalid token should fail."""
    result = await version_service.resume_execution(
        resume_token=uuid4(),  # Invalid token
        approved=True,
        responded_by="reviewer@company.com",
    )

    assert result.success is False
    assert result.status == "error"
    assert "execution" in result.message.lower() and "found" in result.message.lower()


# =============================================================================
# Changelog Tests
# =============================================================================

@pytest.mark.asyncio
async def test_add_changelog_entry(version_service, agent_id):
    """Should add changelog entries for versions."""
    entry = await version_service.add_changelog_entry(
        agent_id=agent_id,
        version="1.1.0",
        changes=["Added new feature", "Fixed bug"],
        is_breaking=False,
    )

    assert entry.version == "1.1.0"
    assert len(entry.changes) == 2
    assert entry.is_breaking is False


@pytest.mark.asyncio
async def test_changelog_included_in_version_check(version_service, execution_id, agent_id):
    """Version check should include changelog entries."""
    await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await version_service.register_agent_version(
        agent_id=agent_id,
        version="1.2.0",
    )

    # Add multiple changelog entries
    await version_service.add_changelog_entry(
        agent_id=agent_id,
        version="1.1.0",
        changes=["Feature A"],
    )
    await version_service.add_changelog_entry(
        agent_id=agent_id,
        version="1.2.0",
        changes=["Feature B"],
    )

    result = await version_service.check_version_before_resume(execution_id)

    assert len(result.changelog) == 2


# =============================================================================
# Suspended Executions Management Tests
# =============================================================================

@pytest.mark.asyncio
async def test_get_suspended_executions(version_service, agent_id):
    """Should list all suspended executions."""
    await version_service.record_suspension(
        execution_id=uuid4(),
        agent_id=agent_id,
        agent_version="1.0.0",
    )
    await version_service.record_suspension(
        execution_id=uuid4(),
        agent_id="other-agent",
        agent_version="2.0.0",
    )

    all_suspended = version_service.get_suspended_executions()
    assert len(all_suspended) == 2

    agent_suspended = version_service.get_suspended_executions(agent_id=agent_id)
    assert len(agent_suspended) == 1
    assert agent_suspended[0].agent_id == agent_id


@pytest.mark.asyncio
async def test_clear_suspension(version_service, agent_id):
    """Should clear suspension record."""
    execution_id = uuid4()
    await version_service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    assert len(version_service.get_suspended_executions()) == 1

    result = version_service.clear_suspension(execution_id)

    assert result is True
    assert len(version_service.get_suspended_executions()) == 0


@pytest.mark.asyncio
async def test_clear_nonexistent_suspension(version_service):
    """Clearing nonexistent suspension should return False."""
    result = version_service.clear_suspension(uuid4())
    assert result is False


# =============================================================================
# Serialization Tests
# =============================================================================

def test_version_info_to_dict():
    """VersionInfo should serialize to dict."""
    info = VersionInfo(
        version="1.0.0",
        deployment_tag="prod-123",
        config_hash="config-hash",
        prompt_hash="prompt-hash",
        deployed_at=datetime(2025, 1, 1, 12, 0, 0),
    )

    d = info.to_dict()

    assert d["version"] == "1.0.0"
    assert d["deployment_tag"] == "prod-123"
    assert "2025-01-01" in d["deployed_at"]


def test_version_check_result_to_dict():
    """VersionCheckResult should serialize to dict."""
    result = VersionCheckResult(
        needs_reload=True,
        original_version="1.0.0",
        current_version="1.1.0",
        is_breaking_change=False,
        drift_type=DriftType.MINOR,
        action=ResumeAction.HOT_RELOAD,
        message="Test message",
    )

    d = result.to_dict()

    assert d["needs_reload"] is True
    assert d["drift_type"] == "minor"
    assert d["action"] == "hot_reload"


def test_resume_result_to_dict():
    """ResumeResult should serialize to dict."""
    result = ResumeResult(
        success=True,
        status="resumed",
        execution_id=uuid4(),
        message="Resumed successfully",
    )

    d = result.to_dict()

    assert d["success"] is True
    assert d["status"] == "resumed"


# =============================================================================
# Singleton Tests
# =============================================================================

def test_get_hitl_version_service_singleton():
    """get_hitl_version_service should return singleton."""
    reset_hitl_version_service()

    service1 = get_hitl_version_service()
    service2 = get_hitl_version_service()

    assert service1 is service2

    reset_hitl_version_service()


def test_reset_hitl_version_service():
    """reset_hitl_version_service should clear singleton."""
    service1 = get_hitl_version_service()
    reset_hitl_version_service()
    service2 = get_hitl_version_service()

    assert service1 is not service2

    reset_hitl_version_service()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

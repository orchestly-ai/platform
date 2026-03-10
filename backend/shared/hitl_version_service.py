"""
HITL Version Drift Service

Implements ROADMAP.md Section: Agent Version Checking for HITL Resume

Features:
- Track agent version at HITL suspension time
- Detect version changes when resuming
- Block resume for breaking changes
- Hot-reload agents for non-breaking changes
- Version changelog tracking

Design Decisions:
- Semantic versioning for agent versions
- Breaking changes = major version bump
- Non-breaking = minor/patch bumps
- Hot-reload preserves execution context
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class DriftType(Enum):
    """Type of version drift detected."""
    NONE = "none"                    # Same version
    PATCH = "patch"                  # Bug fix (hot-reloadable)
    MINOR = "minor"                  # New feature (hot-reloadable)
    MAJOR = "major"                  # Breaking change (blocks resume)
    CONFIG_CHANGE = "config_change"  # Configuration changed
    PROMPT_CHANGE = "prompt_change"  # System prompt changed (major)


class ResumeAction(Enum):
    """Action to take when resuming HITL."""
    PROCEED = "proceed"               # Continue with original version
    HOT_RELOAD = "hot_reload"         # Reload agent with new version
    BLOCK = "block"                   # Block resume, require re-execution
    WARN = "warn"                     # Proceed with warning


@dataclass
class VersionInfo:
    """Agent version information."""
    version: str
    deployment_tag: Optional[str] = None
    config_hash: Optional[str] = None
    prompt_hash: Optional[str] = None
    deployed_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "deployment_tag": self.deployment_tag,
            "config_hash": self.config_hash,
            "prompt_hash": self.prompt_hash,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
        }

    @staticmethod
    def parse_version(version: str) -> Tuple[int, int, int]:
        """Parse semantic version string into components."""
        try:
            parts = version.lstrip("v").split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2].split("-")[0]) if len(parts) > 2 else 0
            return (major, minor, patch)
        except (ValueError, IndexError):
            return (0, 0, 0)


@dataclass
class VersionCheckResult:
    """Result of version drift check."""
    needs_reload: bool
    original_version: Optional[str] = None
    current_version: Optional[str] = None
    is_breaking_change: bool = False
    drift_type: Optional[DriftType] = None
    action: ResumeAction = ResumeAction.PROCEED
    message: Optional[str] = None
    changelog: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "needs_reload": self.needs_reload,
            "original_version": self.original_version,
            "current_version": self.current_version,
            "is_breaking_change": self.is_breaking_change,
            "drift_type": self.drift_type.value if self.drift_type else None,
            "action": self.action.value,
            "message": self.message,
            "changelog": self.changelog,
        }


@dataclass
class SuspendedExecution:
    """Information about a suspended HITL execution."""
    execution_id: UUID
    agent_id: str
    agent_version: str
    agent_config_hash: Optional[str] = None
    agent_prompt_hash: Optional[str] = None
    suspended_at: datetime = field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = field(default_factory=dict)
    resume_token: Optional[UUID] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "execution_id": str(self.execution_id),
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "agent_config_hash": self.agent_config_hash,
            "agent_prompt_hash": self.agent_prompt_hash,
            "suspended_at": self.suspended_at.isoformat(),
            "resume_token": str(self.resume_token) if self.resume_token else None,
        }


@dataclass
class ResumeResult:
    """Result of attempting to resume HITL execution."""
    success: bool
    status: str  # 'resumed', 'hot_reloaded', 'blocked', 'error'
    execution_id: Optional[UUID] = None
    message: Optional[str] = None
    version_check: Optional[VersionCheckResult] = None
    hot_reload_applied: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "status": self.status,
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "message": self.message,
            "version_check": self.version_check.to_dict() if self.version_check else None,
            "hot_reload_applied": self.hot_reload_applied,
        }


@dataclass
class ChangelogEntry:
    """Entry in the version changelog."""
    version: str
    is_breaking: bool
    changes: List[str]
    breaking_reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "is_breaking": self.is_breaking,
            "changes": self.changes,
            "breaking_reason": self.breaking_reason,
            "created_at": self.created_at.isoformat(),
        }


class HITLVersionService:
    """
    Service for handling agent version drift during HITL resume.

    When an execution is suspended for human approval, the agent version
    is captured. When the human responds (potentially hours or days later),
    we check if the agent has been updated and handle accordingly:

    - Same version: Proceed normally
    - Patch/Minor update: Hot-reload the new version
    - Major/Breaking update: Block resume, require re-execution
    """

    def __init__(self, db=None):
        """
        Initialize version service.

        Args:
            db: Database session for persistence
        """
        self.db = db
        # In-memory storage for demo/testing
        self._suspended_executions: Dict[UUID, SuspendedExecution] = {}
        self._agent_versions: Dict[str, VersionInfo] = {}
        self._version_changelog: Dict[str, List[ChangelogEntry]] = {}

    async def record_suspension(
        self,
        execution_id: UUID,
        agent_id: str,
        agent_version: str,
        agent_config_hash: Optional[str] = None,
        agent_prompt_hash: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> SuspendedExecution:
        """
        Record execution suspension for HITL with version info.

        Args:
            execution_id: Execution being suspended
            agent_id: Agent that's suspended
            agent_version: Current agent version
            agent_config_hash: Hash of agent configuration
            agent_prompt_hash: Hash of system prompt
            context: Execution context to preserve

        Returns:
            SuspendedExecution record
        """
        from uuid import uuid4

        suspended = SuspendedExecution(
            execution_id=execution_id,
            agent_id=agent_id,
            agent_version=agent_version,
            agent_config_hash=agent_config_hash,
            agent_prompt_hash=agent_prompt_hash,
            suspended_at=datetime.utcnow(),
            context=context or {},
            resume_token=uuid4(),
        )

        self._suspended_executions[execution_id] = suspended

        if self.db:
            # In production, persist to database
            pass

        logger.info(
            f"Recorded suspension for execution {execution_id}, "
            f"agent {agent_id} v{agent_version}"
        )

        return suspended

    async def check_version_before_resume(
        self,
        execution_id: UUID,
    ) -> VersionCheckResult:
        """
        Check for version drift before resuming HITL execution.

        Args:
            execution_id: Execution to check

        Returns:
            VersionCheckResult with action to take
        """
        # Get suspended execution
        suspended = self._suspended_executions.get(execution_id)
        if not suspended:
            return VersionCheckResult(
                needs_reload=False,
                action=ResumeAction.PROCEED,
                message="Execution not found in suspension records",
            )

        # Get current agent version
        current_version = await self._get_current_agent_version(suspended.agent_id)

        if not current_version:
            # No version info, proceed with caution
            return VersionCheckResult(
                needs_reload=False,
                original_version=suspended.agent_version,
                current_version=None,
                action=ResumeAction.WARN,
                message="Cannot verify agent version, proceeding with original",
            )

        # Check if version changed
        original = suspended.agent_version
        current = current_version.version

        if original == current:
            # Check for config/prompt changes even with same version
            if (suspended.agent_config_hash and
                current_version.config_hash and
                suspended.agent_config_hash != current_version.config_hash):
                return VersionCheckResult(
                    needs_reload=True,
                    original_version=original,
                    current_version=current,
                    is_breaking_change=False,
                    drift_type=DriftType.CONFIG_CHANGE,
                    action=ResumeAction.HOT_RELOAD,
                    message="Agent configuration changed, hot-reloading",
                )

            if (suspended.agent_prompt_hash and
                current_version.prompt_hash and
                suspended.agent_prompt_hash != current_version.prompt_hash):
                return VersionCheckResult(
                    needs_reload=True,
                    original_version=original,
                    current_version=current,
                    is_breaking_change=True,
                    drift_type=DriftType.PROMPT_CHANGE,
                    action=ResumeAction.BLOCK,
                    message="System prompt changed, requires re-execution",
                )

            return VersionCheckResult(
                needs_reload=False,
                original_version=original,
                current_version=current,
                drift_type=DriftType.NONE,
                action=ResumeAction.PROCEED,
                message="Agent version unchanged",
            )

        # Version changed - determine if breaking
        drift_type = self._determine_drift_type(original, current)
        is_breaking = await self._is_breaking_change(
            suspended.agent_id, original, current
        )
        changelog = await self._get_changelog_between_versions(
            suspended.agent_id, original, current
        )

        if is_breaking or drift_type == DriftType.MAJOR:
            return VersionCheckResult(
                needs_reload=True,
                original_version=original,
                current_version=current,
                is_breaking_change=True,
                drift_type=drift_type,
                action=ResumeAction.BLOCK,
                message=f"Agent updated from v{original} to v{current} (breaking change)",
                changelog=[c.to_dict() for c in changelog],
            )

        # Non-breaking change - hot-reload
        return VersionCheckResult(
            needs_reload=True,
            original_version=original,
            current_version=current,
            is_breaking_change=False,
            drift_type=drift_type,
            action=ResumeAction.HOT_RELOAD,
            message=f"Agent updated from v{original} to v{current} (hot-reloadable)",
            changelog=[c.to_dict() for c in changelog],
        )

    async def resume_execution(
        self,
        resume_token: UUID,
        approved: bool,
        responded_by: str,
        force_resume: bool = False,
    ) -> ResumeResult:
        """
        Resume a HITL-suspended execution with version validation.

        Args:
            resume_token: Token from original suspension
            approved: Whether the human approved
            responded_by: User who responded
            force_resume: Force resume even with breaking changes

        Returns:
            ResumeResult with status
        """
        # Find execution by resume token
        execution = None
        for exec_id, suspended in self._suspended_executions.items():
            if suspended.resume_token == resume_token:
                execution = suspended
                break

        if not execution:
            return ResumeResult(
                success=False,
                status="error",
                message=f"No execution found for resume token {resume_token}",
            )

        if not approved:
            # Rejection - no version check needed
            del self._suspended_executions[execution.execution_id]
            return ResumeResult(
                success=True,
                status="rejected",
                execution_id=execution.execution_id,
                message="HITL request rejected by user",
            )

        # Check version drift
        version_check = await self.check_version_before_resume(
            execution.execution_id
        )

        if version_check.action == ResumeAction.BLOCK and not force_resume:
            return ResumeResult(
                success=False,
                status="blocked",
                execution_id=execution.execution_id,
                message=version_check.message,
                version_check=version_check,
            )

        # Handle hot-reload (also applies when force_resume bypasses BLOCK with version change)
        hot_reload_applied = False
        if version_check.action == ResumeAction.HOT_RELOAD or (
            force_resume and version_check.needs_reload
        ):
            await self._hot_reload_agent(execution, version_check)
            hot_reload_applied = True

        # Clean up suspension record
        del self._suspended_executions[execution.execution_id]

        status = "hot_reloaded" if hot_reload_applied else "resumed"
        return ResumeResult(
            success=True,
            status=status,
            execution_id=execution.execution_id,
            message=f"Execution {status} by {responded_by}",
            version_check=version_check,
            hot_reload_applied=hot_reload_applied,
        )

    def _determine_drift_type(self, original: str, current: str) -> DriftType:
        """Determine type of version drift using semver."""
        orig_parts = VersionInfo.parse_version(original)
        curr_parts = VersionInfo.parse_version(current)

        if curr_parts[0] != orig_parts[0]:
            return DriftType.MAJOR
        elif curr_parts[1] != orig_parts[1]:
            return DriftType.MINOR
        elif curr_parts[2] != orig_parts[2]:
            return DriftType.PATCH
        return DriftType.NONE

    async def _get_current_agent_version(
        self,
        agent_id: str,
    ) -> Optional[VersionInfo]:
        """Get current version for an agent."""
        if agent_id in self._agent_versions:
            return self._agent_versions[agent_id]

        if self.db:
            # In production, query database
            pass

        return None

    async def _is_breaking_change(
        self,
        agent_id: str,
        from_version: str,
        to_version: str,
    ) -> bool:
        """Check if version change is breaking based on changelog."""
        changelog = await self._get_changelog_between_versions(
            agent_id, from_version, to_version
        )

        # Any breaking entry means breaking change
        return any(entry.is_breaking for entry in changelog)

    async def _get_changelog_between_versions(
        self,
        agent_id: str,
        from_version: str,
        to_version: str,
    ) -> List[ChangelogEntry]:
        """Get changelog entries between two versions."""
        if agent_id not in self._version_changelog:
            return []

        entries = []
        from_parts = VersionInfo.parse_version(from_version)
        to_parts = VersionInfo.parse_version(to_version)

        for entry in self._version_changelog[agent_id]:
            entry_parts = VersionInfo.parse_version(entry.version)
            if from_parts < entry_parts <= to_parts:
                entries.append(entry)

        return entries

    async def _hot_reload_agent(
        self,
        execution: SuspendedExecution,
        version_check: VersionCheckResult,
    ) -> None:
        """
        Hot-reload an agent with the new version.

        This preserves execution context while updating the agent.
        """
        logger.info(
            f"Hot-reloading agent {execution.agent_id} from "
            f"v{version_check.original_version} to v{version_check.current_version}"
        )

        # In production, this would:
        # 1. Load the new agent version
        # 2. Transfer execution context
        # 3. Update database records
        # 4. Log the hot-reload for audit

        # For demo, just log
        pass

    # =========================================================================
    # Version Management Methods
    # =========================================================================

    async def register_agent_version(
        self,
        agent_id: str,
        version: str,
        deployment_tag: Optional[str] = None,
        config_hash: Optional[str] = None,
        prompt_hash: Optional[str] = None,
    ) -> VersionInfo:
        """Register a new agent version."""
        version_info = VersionInfo(
            version=version,
            deployment_tag=deployment_tag,
            config_hash=config_hash,
            prompt_hash=prompt_hash,
            deployed_at=datetime.utcnow(),
        )

        self._agent_versions[agent_id] = version_info
        return version_info

    async def add_changelog_entry(
        self,
        agent_id: str,
        version: str,
        changes: List[str],
        is_breaking: bool = False,
        breaking_reason: Optional[str] = None,
    ) -> ChangelogEntry:
        """Add a changelog entry for an agent version."""
        entry = ChangelogEntry(
            version=version,
            is_breaking=is_breaking,
            changes=changes,
            breaking_reason=breaking_reason,
        )

        if agent_id not in self._version_changelog:
            self._version_changelog[agent_id] = []

        self._version_changelog[agent_id].append(entry)
        return entry

    def get_suspended_executions(
        self,
        agent_id: Optional[str] = None,
    ) -> List[SuspendedExecution]:
        """Get all suspended executions, optionally filtered by agent."""
        executions = list(self._suspended_executions.values())
        if agent_id:
            executions = [e for e in executions if e.agent_id == agent_id]
        return executions

    def clear_suspension(self, execution_id: UUID) -> bool:
        """Clear a suspension record."""
        if execution_id in self._suspended_executions:
            del self._suspended_executions[execution_id]
            return True
        return False


# Singleton instance
_hitl_version_service: Optional[HITLVersionService] = None


def get_hitl_version_service(db=None) -> HITLVersionService:
    """Get or create the global HITLVersionService instance."""
    global _hitl_version_service
    if _hitl_version_service is None:
        _hitl_version_service = HITLVersionService(db=db)
    return _hitl_version_service


def reset_hitl_version_service():
    """Reset the global HITLVersionService instance (useful for testing)."""
    global _hitl_version_service
    _hitl_version_service = None

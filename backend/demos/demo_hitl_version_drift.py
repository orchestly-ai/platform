#!/usr/bin/env python3
"""
Demo: HITL Version Drift Handling

Shows the agent version checking for HITL resume from ROADMAP.md:
1. Recording suspension with version info
2. Same version - normal resume
3. Patch/Minor update - hot-reload resume
4. Major/Breaking update - blocked resume
5. Config/Prompt change detection
6. Force resume for breaking changes

Reference: ROADMAP.md Section "Agent Version Checking for HITL Resume"

Key Design Decisions:
- Semantic versioning determines drift type
- Major version = breaking change (blocks resume)
- Minor/Patch = non-breaking (hot-reloadable)
- Prompt changes always block (considered breaking)
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Add parent directories to path
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
)


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(description: str, result, indent=2):
    """Print a result with formatting."""
    prefix = " " * indent
    if hasattr(result, 'to_dict'):
        print(f"{prefix}{description}:")
        for key, value in result.to_dict().items():
            print(f"{prefix}  {key}: {value}")
    else:
        print(f"{prefix}{description}: {result}")


async def demo_basic_flow():
    """Demo 1: Basic HITL suspension and resume with version tracking."""
    print_header("Demo 1: Basic Version Tracking")
    print("\nWhen an agent is suspended for HITL, we capture its version.\n")

    service = HITLVersionService()
    agent_id = "customer-service-agent"
    execution_id = uuid4()

    # Register current agent version
    print("1. Registering agent version...")
    await service.register_agent_version(
        agent_id=agent_id,
        version="1.0.0",
        config_hash="config-abc123",
        prompt_hash="prompt-xyz789",
    )
    print(f"   Agent: {agent_id}")
    print(f"   Version: 1.0.0")

    # Suspend execution for HITL
    print("\n2. Suspending execution for human approval...")
    suspended = await service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
        agent_config_hash="config-abc123",
        agent_prompt_hash="prompt-xyz789",
        context={"customer_id": "C-12345", "inquiry_type": "refund"},
    )
    print(f"   Execution ID: {execution_id}")
    print(f"   Resume Token: {suspended.resume_token}")
    print(f"   Captured Version: {suspended.agent_version}")

    # Human approves (same version)
    print("\n3. Human approves request (same version)...")
    result = await service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )
    print_result("Resume Result", result)

    print("\n[OK] Basic version tracking works correctly!")


async def demo_hot_reload():
    """Demo 2: Non-breaking change triggers hot-reload."""
    print_header("Demo 2: Hot-Reload for Non-Breaking Changes")
    print("\nPatch and minor version bumps are hot-reloadable.\n")

    service = HITLVersionService()
    agent_id = "sales-agent"

    # Scenario 1: Patch bump (1.0.0 -> 1.0.1)
    print("Scenario A: Patch version bump (1.0.0 -> 1.0.1)")
    print("-" * 50)

    execution_id = uuid4()
    suspended = await service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    # Agent gets patched during HITL wait
    await service.register_agent_version(
        agent_id=agent_id,
        version="1.0.1",  # Patch bump
    )
    await service.add_changelog_entry(
        agent_id=agent_id,
        version="1.0.1",
        changes=["Fixed typo in response", "Improved error handling"],
    )

    print(f"  Original version: 1.0.0")
    print(f"  Current version:  1.0.1")

    result = await service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )
    print(f"  Resume status: {result.status}")
    print(f"  Hot-reload applied: {result.hot_reload_applied}")
    print(f"  Drift type: {result.version_check.drift_type.value}")

    # Scenario 2: Minor bump (1.0.0 -> 1.1.0)
    print("\nScenario B: Minor version bump (1.0.0 -> 1.1.0)")
    print("-" * 50)

    # Reset for new scenario
    service._agent_versions.clear()
    service._version_changelog.clear()

    execution_id = uuid4()
    suspended = await service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await service.register_agent_version(
        agent_id=agent_id,
        version="1.1.0",  # Minor bump
    )
    await service.add_changelog_entry(
        agent_id=agent_id,
        version="1.1.0",
        changes=["Added new greeting variations", "Enhanced product recommendations"],
    )

    print(f"  Original version: 1.0.0")
    print(f"  Current version:  1.1.0")

    result = await service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )
    print(f"  Resume status: {result.status}")
    print(f"  Hot-reload applied: {result.hot_reload_applied}")
    print(f"  Drift type: {result.version_check.drift_type.value}")

    print("\n[OK] Hot-reload works for non-breaking changes!")


async def demo_breaking_change():
    """Demo 3: Breaking change blocks resume."""
    print_header("Demo 3: Breaking Changes Block Resume")
    print("\nMajor version changes and breaking changelogs block resume.\n")

    service = HITLVersionService()
    agent_id = "order-processor"

    # Scenario 1: Major version bump
    print("Scenario A: Major version bump (1.0.0 -> 2.0.0)")
    print("-" * 50)

    execution_id = uuid4()
    suspended = await service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    # Agent gets major update
    await service.register_agent_version(
        agent_id=agent_id,
        version="2.0.0",
    )
    await service.add_changelog_entry(
        agent_id=agent_id,
        version="2.0.0",
        changes=["Complete API redesign", "New response format"],
        is_breaking=True,
        breaking_reason="Response JSON structure completely changed",
    )

    print(f"  Original version: 1.0.0")
    print(f"  Current version:  2.0.0")

    result = await service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )
    print(f"  Resume success: {result.success}")
    print(f"  Status: {result.status}")
    print(f"  Message: {result.message}")
    print(f"  Changelog entries: {len(result.version_check.changelog)}")

    # Scenario 2: Breaking changelog entry
    print("\nScenario B: Breaking changelog with minor bump")
    print("-" * 50)

    service._agent_versions.clear()
    service._version_changelog.clear()

    execution_id = uuid4()
    suspended = await service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    await service.register_agent_version(
        agent_id=agent_id,
        version="1.1.0",  # Minor bump BUT...
    )
    await service.add_changelog_entry(
        agent_id=agent_id,
        version="1.1.0",
        changes=["Changed tool parameter format"],
        is_breaking=True,  # Marked as breaking despite minor bump
        breaking_reason="Tool call format changed",
    )

    print(f"  Original version: 1.0.0")
    print(f"  Current version:  1.1.0")
    print(f"  (Has breaking changelog entry)")

    result = await service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )
    print(f"  Resume success: {result.success}")
    print(f"  Status: {result.status}")
    print(f"  Breaking change detected: {result.version_check.is_breaking_change}")

    print("\n[OK] Breaking changes correctly block resume!")


async def demo_config_prompt_changes():
    """Demo 4: Config and prompt hash change detection."""
    print_header("Demo 4: Config & Prompt Change Detection")
    print("\nEven with same version, config/prompt changes are detected.\n")

    service = HITLVersionService()
    agent_id = "support-agent"

    # Scenario 1: Config change (hot-reloadable)
    print("Scenario A: Configuration changed (same version)")
    print("-" * 50)

    execution_id = uuid4()
    suspended = await service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
        agent_config_hash="config-old",
    )

    await service.register_agent_version(
        agent_id=agent_id,
        version="1.0.0",  # Same version
        config_hash="config-new",  # Different config
    )

    print(f"  Version: 1.0.0 (unchanged)")
    print(f"  Config hash: config-old -> config-new")

    check = await service.check_version_before_resume(execution_id)
    print(f"  Drift type: {check.drift_type.value}")
    print(f"  Action: {check.action.value}")
    print(f"  Needs reload: {check.needs_reload}")

    # Resume (hot-reload will apply)
    result = await service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )
    print(f"  Resume status: {result.status}")

    # Scenario 2: Prompt change (blocks - breaking)
    print("\nScenario B: System prompt changed (same version)")
    print("-" * 50)

    service._agent_versions.clear()

    execution_id = uuid4()
    suspended = await service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
        agent_prompt_hash="prompt-old",
    )

    await service.register_agent_version(
        agent_id=agent_id,
        version="1.0.0",
        prompt_hash="prompt-new",  # Different prompt
    )

    print(f"  Version: 1.0.0 (unchanged)")
    print(f"  Prompt hash: prompt-old -> prompt-new")

    check = await service.check_version_before_resume(execution_id)
    print(f"  Drift type: {check.drift_type.value}")
    print(f"  Action: {check.action.value}")
    print(f"  Breaking: {check.is_breaking_change}")

    result = await service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
    )
    print(f"  Resume success: {result.success}")
    print(f"  Status: {result.status}")

    print("\n[OK] Config/prompt changes are properly detected!")


async def demo_force_resume():
    """Demo 5: Force resume for breaking changes."""
    print_header("Demo 5: Force Resume Override")
    print("\nAdmins can force resume even with breaking changes.\n")

    service = HITLVersionService()
    agent_id = "critical-agent"

    execution_id = uuid4()
    suspended = await service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    # Major version change (normally blocks)
    await service.register_agent_version(
        agent_id=agent_id,
        version="2.0.0",
    )

    print("1. Normal resume attempt (should be blocked)...")
    result = await service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="reviewer@company.com",
        force_resume=False,
    )
    print(f"   Success: {result.success}")
    print(f"   Status: {result.status}")

    # Need to re-suspend since it was cleared from cache
    suspended = await service.record_suspension(
        execution_id=execution_id,
        agent_id=agent_id,
        agent_version="1.0.0",
    )

    print("\n2. Force resume by admin (should succeed)...")
    result = await service.resume_execution(
        resume_token=suspended.resume_token,
        approved=True,
        responded_by="admin@company.com",
        force_resume=True,  # Admin override
    )
    print(f"   Success: {result.success}")
    print(f"   Status: {result.status}")
    print(f"   Hot-reload applied: {result.hot_reload_applied}")

    print("\n[OK] Force resume allows admins to override blocks!")


async def demo_use_cases():
    """Demo 6: Common scenarios and recommendations."""
    print_header("Demo 6: Version Drift Decision Matrix")
    print("\nFrom ROADMAP.md - How version changes affect resume:\n")

    print("┌──────────────────────────┬────────────────┬───────────────┐")
    print("│ Change Type              │ Drift Type     │ Action        │")
    print("├──────────────────────────┼────────────────┼───────────────┤")
    print("│ No change                │ NONE           │ PROCEED       │")
    print("│ Bug fix (x.x.PATCH)      │ PATCH          │ HOT_RELOAD    │")
    print("│ New feature (x.MINOR.x)  │ MINOR          │ HOT_RELOAD    │")
    print("│ Breaking (MAJOR.x.x)     │ MAJOR          │ BLOCK         │")
    print("│ Config changed           │ CONFIG_CHANGE  │ HOT_RELOAD    │")
    print("│ Prompt changed           │ PROMPT_CHANGE  │ BLOCK         │")
    print("│ Breaking changelog       │ (varies)       │ BLOCK         │")
    print("└──────────────────────────┴────────────────┴───────────────┘")

    print("\nVersion Checking Process:")
    print("  1. Record agent version at HITL suspension")
    print("  2. When human responds, check current version")
    print("  3. Compare versions using semver")
    print("  4. Check changelog for breaking changes")
    print("  5. Check config/prompt hashes")
    print("  6. Apply appropriate action")

    print("\n" + "-" * 60)
    print("Version drift handling ensures consistent agent behavior!")
    print("-" * 60)


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("  HITL VERSION DRIFT DEMO")
    print("  Agent Version Checking for Resume")
    print("=" * 60)
    print("\nReference: ROADMAP.md Section 'Agent Version Checking for HITL Resume'")

    try:
        await demo_basic_flow()
        await demo_hot_reload()
        await demo_breaking_change()
        await demo_config_prompt_changes()
        await demo_force_resume()
        await demo_use_cases()

        print("\n" + "=" * 60)
        print("  ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nKey Takeaways:")
        print("  1. Agent version is captured at HITL suspension")
        print("  2. Version drift is checked before resume")
        print("  3. Non-breaking changes (patch/minor) hot-reload")
        print("  4. Breaking changes (major/prompt) block resume")
        print("  5. Admins can force resume if needed")
        print("  6. Changelog entries can mark any version as breaking")
        print()

    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

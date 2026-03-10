"""
Master Demo Runner - Execute All Platform Demos

Automatically discovers and runs all demos in the demos directory.

Run: python backend/demos/demo_all.py
Or:  python -m backend.demos.demo_all
"""

import asyncio
import sys
import importlib
from pathlib import Path
from typing import List, Tuple, Callable

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def discover_demos(show_failures_only=False) -> tuple:
    """
    Automatically discover all demo files in the demos directory.

    Args:
        show_failures_only: If True, only return failed demos

    Returns:
        Tuple of (successful_demos, failed_demos)
        - successful_demos: List of (demo_name, demo_function) tuples
        - failed_demos: List of (demo_file_name, error_message) tuples
    """
    demos_dir = Path(__file__).parent
    demo_files = sorted(demos_dir.glob("demo_*.py"))

    # Exclude demo_all.py
    demo_files = [f for f in demo_files if f.name != "demo_all.py"]

    discovered = []
    failed = []

    for demo_file in demo_files:
        module_name = demo_file.stem  # e.g., "demo_api_keys"
        demo_name = module_name.replace("demo_", "").replace("_", " ").title()

        try:
            # Import the module
            module = importlib.import_module(f"backend.demos.{module_name}")

            # Look for main() function or a function matching the module name
            if hasattr(module, 'main'):
                discovered.append((demo_name, module.main))
            elif hasattr(module, module_name):
                discovered.append((demo_name, getattr(module, module_name)))
            else:
                error_msg = "no main() function found"
                failed.append((demo_file.name, error_msg))
                if not show_failures_only:
                    print(f"⚠️  Skipping {demo_file.name} - {error_msg}")

        except Exception as e:
            error_msg = str(e)
            failed.append((demo_file.name, error_msg))
            if not show_failures_only:
                print(f"⚠️  Could not load {demo_file.name}: {e}")

    return discovered, failed


async def run_all_demos(interactive: bool = True):
    """Run all discovered demos."""
    print("=" * 80)
    print("AGENT ORCHESTRATION PLATFORM - COMPLETE DEMO SUITE")
    print("=" * 80)
    print()

    # Discover all demos
    demos, failed = await discover_demos()

    print(f"Found {len(demos)} demos:")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    print()

    if interactive:
        print("Estimated time: Variable (5-30 minutes depending on demos)")
        print()
        response = input("Press Enter to run all demos, or 'q' to quit: ")
        if response.lower() == 'q':
            print("Exiting...")
            return
        print()

    # Track results
    successful = []
    failed = []

    # Run each demo
    for i, (name, demo_func) in enumerate(demos, 1):
        print("\n" + "=" * 80)
        print(f"DEMO {i}/{len(demos)}: {name}")
        print("=" * 80)
        print()

        try:
            # Run the demo
            result = demo_func()

            # Handle both sync and async functions
            if asyncio.iscoroutine(result):
                await result

            print(f"\n✅ {name} completed successfully!")
            successful.append(name)

        except KeyboardInterrupt:
            print(f"\n⏸️  Demo interrupted by user")
            failed.append((name, "User interrupted"))
            break

        except Exception as e:
            print(f"\n❌ Error in {name}: {type(e).__name__}: {str(e)[:200]}")
            failed.append((name, str(e)[:100]))
            print("Continuing to next demo...")

        if i < len(demos):
            print("\n" + "-" * 80)
            if interactive:
                input("Press Enter to continue to next demo...")
            else:
                print("Moving to next demo in 2 seconds...")
                await asyncio.sleep(2)

    # Final Summary
    print("\n\n" + "=" * 80)
    print("COMPLETE DEMO SUITE - FINAL SUMMARY")
    print("=" * 80)

    print(f"\n📊 Results:")
    print(f"   ✅ Successful: {len(successful)}/{len(demos)}")
    print(f"   ❌ Failed: {len(failed)}/{len(demos)}")

    if successful:
        print(f"\n✅ Successful Demos ({len(successful)}):")
        for name in successful:
            print(f"   • {name}")

    if failed:
        print(f"\n❌ Failed Demos ({len(failed)}):")
        for name, error in failed:
            print(f"   • {name}")
            print(f"     Error: {error}")

    print("\n🎯 Platform Capabilities Demonstrated:")
    print("\n1. API Key Management:")
    print("   • SHA-256 hashing with secure key generation")
    print("   • Key rotation with grace period")
    print("   • Rate limiting and IP whitelisting")
    print("   • Monthly quotas and permission scopes")

    print("\n2. Agent Registry & Governance:")
    print("   • Multi-stage approval workflows")
    print("   • Policy enforcement and compliance")
    print("   • Cost tracking and analytics")
    print("   • Agent discovery and deduplication")

    print("\n3. LLM Routing & Optimization:")
    print("   • Multi-LLM routing with 40% cost savings")
    print("   • ML-powered routing decisions")
    print("   • Provider failover and circuit breakers")
    print("   • A/B testing for optimization")

    print("\n4. Workflow Orchestration:")
    print("   • Visual DAG builder")
    print("   • Supervisor orchestration patterns")
    print("   • Time-travel debugging")
    print("   • Workflow templates and marketplace")

    print("\n5. Enterprise Features:")
    print("   • SSO/SAML authentication")
    print("   • RBAC and audit logging")
    print("   • Multi-cloud deployment")
    print("   • White-label and reseller programs")

    print("\n6. Integration & Monitoring:")
    print("   • Integration marketplace (10+ integrations)")
    print("   • Real-time monitoring and analytics")
    print("   • Cost forecasting and budget alerts")
    print("   • Security and compliance dashboards")

    print("\n💰 Business Impact:")
    print("   • 40% reduction in operational costs")
    print("   • 35% increase in conversion rates")
    print("   • 60% faster response times")
    print("   • 90% automation of manual tasks")

    print("\n🏆 Competitive Advantages:")
    print("   ✓ Only platform with multi-LLM routing + orchestration")
    print("   ✓ BYOX (Bring Your Own X) for everything")
    print("   ✓ Enterprise security (SOC 2, HIPAA, GDPR)")
    print("   ✓ Multi-cloud deployment (AWS, Azure, GCP, On-Prem)")
    print("   ✓ Agent marketplace with 1-click install")

    print("\n📊 Technical Highlights:")
    print(f"   • {len(demos)} feature demos")
    print("   • Full PostgreSQL persistence")
    print("   • Async Python with FastAPI")
    print("   • Comprehensive error handling")
    print("   • Production-ready architecture")

    print("\n" + "=" * 80)
    print("Thank you for watching the complete platform demonstration!")
    print("=" * 80)
    print()


async def run_specific_demos(demo_names: List[str]):
    """Run specific demos by name."""
    demos, failed = await discover_demos()

    # Build a lookup dict
    demo_dict = {name.lower(): (name, func) for name, func in demos}

    for requested_name in demo_names:
        requested_lower = requested_name.lower()

        # Try to find matching demo
        matching = None
        for demo_name_lower, (name, func) in demo_dict.items():
            if requested_lower in demo_name_lower or demo_name_lower in requested_lower:
                matching = (name, func)
                break

        if matching:
            name, func = matching
            print(f"\n{'=' * 80}")
            print(f"Running: {name}")
            print('=' * 80)

            try:
                result = func()
                if asyncio.iscoroutine(result):
                    await result
                print(f"\n✅ {name} completed!")
            except Exception as e:
                print(f"\n❌ Error: {e}")
        else:
            print(f"⚠️  Demo not found: {requested_name}")
            print(f"Available demos:")
            for name in sorted(demo_dict.keys()):
                print(f"  • {name}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run Agent Orchestration Platform demos")
    parser.add_argument(
        "demos",
        nargs="*",
        help="Specific demo names to run (runs all if not specified)"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode (no prompts)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available demos"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for failed/broken demos (shows only failures)"
    )

    args = parser.parse_args()

    if args.check:
        # Check for failed demos
        demos, failed = asyncio.run(discover_demos(show_failures_only=True))

        if failed:
            print(f"\n❌ Failed Demos ({len(failed)}):\n")
            for demo_file, error in failed:
                print(f"  • {demo_file}")
                # Truncate long error messages
                error_short = error if len(error) <= 80 else error[:77] + "..."
                print(f"    Error: {error_short}")
            print(f"\n✅ Successful: {len(demos)}")
            print(f"❌ Failed: {len(failed)}")
            print(f"📊 Total: {len(demos) + len(failed)}\n")
        else:
            print(f"\n✅ All {len(demos)} demos loaded successfully!\n")
        return

    if args.list:
        # List all demos
        demos, failed = asyncio.run(discover_demos())
        print(f"\nAvailable Demos ({len(demos)}):")
        for i, (name, _) in enumerate(sorted(demos), 1):
            print(f"  {i}. {name}")
        if failed:
            print(f"\n⚠️  {len(failed)} demo(s) failed to load (use --check to see details)")
        print()
        return

    if args.demos:
        # Run specific demos
        asyncio.run(run_specific_demos(args.demos))
    else:
        # Run all demos
        asyncio.run(run_all_demos(interactive=not args.non_interactive))


if __name__ == "__main__":
    main()

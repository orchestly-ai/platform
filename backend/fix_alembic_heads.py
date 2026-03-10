#!/usr/bin/env python3
"""
Fix Alembic migration head conflicts

This script:
1. Lists all migration heads
2. Creates a merge migration to resolve conflicts
3. Validates the migration chain
"""

import subprocess
import sys
from datetime import datetime

def run_command(cmd_list):
    """Run a command (as list) and return output. No shell=True for safety."""
    result = subprocess.run(cmd_list, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def main():
    print("🔍 Checking Alembic migration status...\n")

    # Check current heads
    stdout, stderr, code = run_command(["alembic", "heads"])

    if code != 0:
        print(f"❌ Error checking heads: {stderr}")
        return 1

    heads = [line.split()[0] for line in stdout.split('\n') if line.strip() and '->' not in line]

    print(f"📋 Found {len(heads)} head(s):")
    for head in heads:
        print(f"   - {head}")

    if len(heads) <= 1:
        print("\n✅ No merge needed, only one head exists")

        # Try to upgrade
        print("\n⬆️  Running alembic upgrade head...")
        stdout, stderr, code = run_command(["alembic", "upgrade", "head"])

        if code == 0:
            print("✅ Database upgraded successfully!")
            return 0
        else:
            print(f"❌ Upgrade failed: {stderr}")
            return 1

    # Multiple heads - create merge migration
    print(f"\n⚠️  Multiple heads detected. Creating merge migration...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    merge_msg = f"merge_migration_heads_{timestamp}"

    stdout, stderr, code = run_command(["alembic", "merge", "-m", merge_msg, "heads"])

    if code != 0:
        print(f"❌ Failed to create merge migration: {stderr}")
        return 1

    print(f"✅ Merge migration created!")
    print(f"\n{stdout}")

    # Now upgrade
    print("\n⬆️  Running alembic upgrade head...")
    stdout, stderr, code = run_command(["alembic", "upgrade", "head"])

    if code == 0:
        print("\n✅ Database upgraded successfully!")
        print("\n📝 Summary:")
        print(f"   - Merged {len(heads)} migration heads")
        print("   - Database schema is now up to date")
        return 0
    else:
        print(f"\n❌ Upgrade failed: {stderr}")
        print("\n💡 You may need to manually review the migrations")
        return 1

if __name__ == "__main__":
    sys.exit(main())

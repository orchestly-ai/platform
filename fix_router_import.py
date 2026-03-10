#!/usr/bin/env python3
"""
Fix missing Session import in backend/router/monitor.py

This script adds the missing import:
    from sqlalchemy.orm import Session

The import is needed for the type hint in:
    def get_health_monitor(db: Optional[Session] = None) -> HealthMonitor:
"""

import os
import sys
from pathlib import Path

def fix_monitor_import():
    monitor_file = Path("backend/router/monitor.py")

    print(f"🔧 Fixing Session import in {monitor_file}")

    # Check if file exists
    if not monitor_file.exists():
        print(f"❌ Error: {monitor_file} not found!")
        print("This file should exist in your local repository.")
        print("\nPossible reasons:")
        print("1. You haven't pulled the latest changes")
        print("2. The file was created in a previous session but not committed")
        print("3. You're running this from the wrong directory")
        return 1

    # Read the file
    with open(monitor_file, 'r') as f:
        lines = f.readlines()

    # Check if import already exists
    for line in lines:
        if 'from sqlalchemy.orm import Session' in line:
            print("✅ Session import already exists!")
            return 0

    # Create backup
    backup_file = monitor_file.with_suffix('.py.backup')
    with open(backup_file, 'w') as f:
        f.writelines(lines)
    print(f"📦 Created backup: {backup_file}")

    # Find where to insert the import
    # Look for the first import from typing or sqlalchemy
    insert_index = 0
    for i, line in enumerate(lines):
        if line.startswith('from typing import') or line.startswith('from sqlalchemy'):
            insert_index = i + 1
            break
        elif line.startswith('from ') or line.startswith('import '):
            insert_index = i + 1

    # Insert the import
    new_import = 'from sqlalchemy.orm import Session\n'
    lines.insert(insert_index, new_import)

    # Write back
    with open(monitor_file, 'w') as f:
        f.writelines(lines)

    print(f"✅ Added 'from sqlalchemy.orm import Session' at line {insert_index + 1}")
    print()
    print("🎉 Fix applied successfully!")
    print()
    print("Next steps:")
    print("1. Verify the fix: grep -n 'from sqlalchemy.orm import Session' backend/router/monitor.py")
    print("2. Test the API: ./run_api_postgres.sh")
    print("3. Commit the fix: git add backend/router/monitor.py && git commit -m 'Fix missing Session import in router monitor'")
    print()
    print(f"If you need to restore the backup: cp {backup_file} {monitor_file}")

    return 0

if __name__ == '__main__':
    sys.exit(fix_monitor_import())

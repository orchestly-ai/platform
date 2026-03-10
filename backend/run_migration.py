#!/usr/bin/env python3
"""
Run Alembic migrations with correct Python path setup

This script properly configures the Python path and runs Alembic migrations.

Usage:
    python run_migration.py
"""

import sys
from pathlib import Path

# Add parent directory to Python path so 'backend' can be imported
backend_dir = Path(__file__).parent
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

print(f"✅ Added to Python path: {parent_dir}")
print(f"📁 Working directory: {backend_dir}")

# Now import and run alembic
from alembic import command
from alembic.config import Config

# Create Alembic config
config = Config(str(backend_dir / "alembic.ini"))

print("🔄 Running database migrations...")
print()

try:
    # Run upgrade to head
    command.upgrade(config, "head")
    print()
    print("✅ Successfully upgraded database to latest version!")

except Exception as e:
    print()
    print(f"❌ Migration failed: {e}")
    print()
    print("💡 Troubleshooting tips:")
    print("   1. Make sure your database is running")
    print("   2. Check DATABASE_URL environment variable or .env file")
    print("   3. Verify database connection settings in backend/shared/config.py")
    sys.exit(1)

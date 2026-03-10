#!/usr/bin/env python3
"""
Run migrations up to routing_strategies only
"""
import sys
from pathlib import Path

# Set up Python path BEFORE any backend imports
backend_dir = Path(__file__).parent
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

print(f"✅ Added to Python path: {parent_dir}")
print(f"📁 Working directory: {backend_dir}")
print()

# Now we can import alembic
import os
os.chdir(str(backend_dir))

# Use subprocess to avoid import conflicts with local alembic directory
import subprocess

print("🔄 Running database migrations up to 20260104_0001 (routing_strategies)...")
result = subprocess.run(
    [sys.executable, "-c", """
import sys
from pathlib import Path

# Add parent to path
backend_dir = Path.cwd()
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

# Now import and run alembic
from alembic.config import Config
from alembic import command

config = Config('alembic.ini')
command.upgrade(config, '20260104_0001')
"""],
    cwd=str(backend_dir)
)

if result.returncode == 0:
    print()
    print("✅ Migrations completed successfully up to routing_strategies!")
else:
    print()
    print(f"❌ Migration failed with exit code {result.returncode}")
    sys.exit(result.returncode)

#!/usr/bin/env python3
"""
Run migrations for SQLite database
"""
import sys
import os
from pathlib import Path

# Set up Python path BEFORE any backend imports
backend_dir = Path(__file__).parent
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

# Enable SQLite mode
os.environ['USE_SQLITE'] = 'true'

print(f"✅ Added to Python path: {parent_dir}")
print(f"📁 Working directory: {backend_dir}")
print(f"🗄️  Database mode: SQLite (test_workflow.db)")
print()

# Now we can import alembic
os.chdir(str(backend_dir))

# Use subprocess to avoid import conflicts
import subprocess

print("🔄 Running database migrations for SQLite up to routing_strategies...")
result = subprocess.run(
    [sys.executable, "-c", """
import sys
import os
from pathlib import Path

# Add parent to path
backend_dir = Path.cwd()
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

# Enable SQLite mode
os.environ['USE_SQLITE'] = 'true'

# Now import and run alembic
from alembic.config import Config
from alembic import command

config = Config('alembic.ini')
# Run migrations up to routing_strategies (20260104_0001)
command.upgrade(config, '20260104_0001')
"""],
    cwd=str(backend_dir),
    env={**os.environ, 'USE_SQLITE': 'true'}
)

if result.returncode == 0:
    print()
    print("✅ SQLite migrations completed successfully!")
else:
    print()
    print(f"❌ Migration failed with exit code {result.returncode}")
    sys.exit(result.returncode)

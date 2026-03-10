#!/usr/bin/env python3
"""
Simple migration runner using subprocess to avoid import conflicts
"""
import subprocess
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
parent_dir = backend_dir.parent

# Set PYTHONPATH for the subprocess
import os
env = os.environ.copy()
env['PYTHONPATH'] = str(parent_dir)

print("🔄 Running database migrations...")
print(f"📁 Backend directory: {backend_dir}")
print(f"📁 PYTHONPATH: {parent_dir}")
print()

# Run alembic upgrade using Python subprocess
result = subprocess.run(
    [sys.executable, "-m", "alembic.config", "upgrade", "head"],
    cwd=str(backend_dir),
    env=env,
    capture_output=False
)

if result.returncode == 0:
    print()
    print("✅ Migrations completed successfully!")
else:
    print()
    print(f"❌ Migration failed with exit code {result.returncode}")
    sys.exit(result.returncode)

#!/usr/bin/env python3
"""
Run PostgreSQL migrations on Mac
"""
import sys
import os
from pathlib import Path

# Set up Python path
backend_dir = Path(__file__).parent
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

# Use PostgreSQL mode
os.environ['USE_SQLITE'] = 'false'

# Load .env file for database credentials
env_file = backend_dir / '.env'
if env_file.exists():
    print(f"Loading database config from {env_file}")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
                if key == 'POSTGRES_USER':
                    print(f"  Using PostgreSQL user: {value}")

print(f"✅ Added to Python path: {parent_dir}")
print(f"📁 Working directory: {backend_dir}")
print()

# Change to backend directory
os.chdir(str(backend_dir))

# Run migrations
import subprocess

print("🔄 Running PostgreSQL migrations up to routing_strategies (20260104_0001)...")
print()

result = subprocess.run(
    [sys.executable, "-c", """
import sys
import os
from pathlib import Path

# Add parent to path
backend_dir = Path.cwd()
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

# Import and run alembic
from alembic.config import Config
from alembic import command

config = Config('alembic.ini')
# Run migrations up to routing_strategies
command.upgrade(config, '20260104_0001')
"""],
    cwd=str(backend_dir)
)

if result.returncode == 0:
    print()
    print("✅ PostgreSQL migrations completed successfully!")
    print()
    print("Verifying routing_strategies table...")

    # Verify the table exists
    import asyncio
    async def verify():
        from sqlalchemy import text
        from backend.database.session import engine

        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM routing_strategies"))
            count = result.scalar()
            print(f"   routing_strategies table exists with {count} rows")

    try:
        asyncio.run(verify())
    except Exception as e:
        print(f"   Verification check (optional): {e}")
else:
    print()
    print(f"❌ Migration failed with exit code {result.returncode}")
    sys.exit(result.returncode)

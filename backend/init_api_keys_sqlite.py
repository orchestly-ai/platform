"""
Initialize API Keys table in SQLite for testing
"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

# Use SQLite mode
os.environ['USE_SQLITE'] = 'true'

from sqlalchemy import text
from backend.database.session import engine, Base
from backend.database.models import APIKeyModel
from backend.shared.rbac_models import OrganizationModel


async def init_tables():
    """Initialize database tables."""
    print("🔧 Initializing SQLite database for API keys...")

    # Create all tables
    async with engine.begin() as conn:
        # Drop existing tables to start fresh
        await conn.run_sync(Base.metadata.drop_all)

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

        # Insert default organization if it doesn't exist
        await conn.execute(text("""
            INSERT OR IGNORE INTO organizations (organization_id, name, slug, plan, max_users, max_agents, enabled_features, is_active, created_at, updated_at)
            VALUES ('default-org', 'Default Organization', 'default-org', 'enterprise', 100, 100, '[]', 1, datetime('now'), datetime('now'))
        """))

        await conn.commit()

    print("✅ Database initialized successfully!")
    print("\nTables created:")
    print("  • organizations")
    print("  • api_keys")
    print("  • team_members")
    print("  • ... and other platform tables")


if __name__ == "__main__":
    asyncio.run(init_tables())

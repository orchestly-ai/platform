#!/usr/bin/env python3
"""Fix the alembic version in the database."""
import asyncio
import sys
sys.path.insert(0, '..')

from database.session import AsyncSessionLocal
from sqlalchemy import text


async def fix_alembic_version():
    """Update the alembic version to the last known good revision."""
    async with AsyncSessionLocal() as db:
        try:
            # Check current version
            result = await db.execute(text('SELECT version_num FROM alembic_version'))
            current_versions = result.fetchall()
            print('Current version(s) in DB:', [v[0] for v in current_versions])

            # Delete all versions
            await db.execute(text("DELETE FROM alembic_version"))

            # Insert the last known good revision (RAG BYOD migration)
            await db.execute(text("INSERT INTO alembic_version (version_num) VALUES ('c3d4e5f6a7b8')"))

            await db.commit()
            print('✓ Updated to revision: c3d4e5f6a7b8 (RAG BYOD migration)')
            print('\nNow run: alembic upgrade head')

        except Exception as e:
            print(f'Error: {e}')
            await db.rollback()
            raise


if __name__ == '__main__':
    asyncio.run(fix_alembic_version())

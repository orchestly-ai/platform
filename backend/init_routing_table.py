#!/usr/bin/env python3
"""
Initialize routing_strategies table

Simple script to create the routing_strategies table if it doesn't exist.
Run this if the table is missing and you can't run Alembic migrations.

Usage:
    python init_routing_table.py
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir.parent))

# Check database type
database_url = os.getenv('DATABASE_URL', '')
is_sqlite = 'sqlite' in database_url.lower() or os.getenv('USE_SQLITE', '').lower() in ('true', '1', 'yes')

if is_sqlite:
    print("🔍 Detected SQLite database")
    from sqlalchemy import create_engine, text, inspect

    # Find the SQLite database file
    db_files = list(backend_dir.parent.glob('*.db'))
    if not db_files:
        print("❌ No SQLite database file found")
        print("   Looking for: *.db files")
        sys.exit(1)

    db_path = db_files[0]
    print(f"📁 Using database: {db_path}")

    engine = create_engine(f"sqlite:///{db_path}", echo=True)

    # Check if table exists
    inspector = inspect(engine)
    if 'routing_strategies' in inspector.get_table_names():
        print("✅ Table 'routing_strategies' already exists")
        sys.exit(0)

    # Create table
    print("🔨 Creating routing_strategies table...")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE routing_strategies (
                id VARCHAR(100) PRIMARY KEY,
                organization_id VARCHAR(100) NOT NULL,
                strategy VARCHAR(50) NOT NULL,
                config TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.execute(text("""
            CREATE INDEX idx_routing_strategy_org ON routing_strategies(organization_id)
        """))

    print("✅ Successfully created routing_strategies table!")
    print("✅ Created index on organization_id")

else:
    print("🔍 Detected PostgreSQL database")
    print("⚠️  For PostgreSQL, please run Alembic migrations:")
    print("    cd backend && alembic upgrade head")
    print("    OR")
    print("    cd backend && python -m alembic upgrade head")
    sys.exit(1)

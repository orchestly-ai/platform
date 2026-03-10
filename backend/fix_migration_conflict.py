#!/usr/bin/env python3
"""
Fix migration conflicts by cleaning up duplicate enum types

This script handles the 'type already exists' error when running migrations.

Usage:
    python fix_migration_conflict.py
"""

import sys
from pathlib import Path

# Add parent directory to Python path
backend_dir = Path(__file__).parent
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

print("🔧 Fixing migration conflicts...")
print()

from sqlalchemy import create_engine, text
from backend.shared.config import get_settings

settings = get_settings()

# Construct database URL without async
database_url = (
    f"postgresql://{settings.POSTGRES_USER}:"
    f"{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:"
    f"{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

engine = create_engine(database_url, echo=False)

print("1️⃣ Checking for conflicting enum types...")

with engine.connect() as conn:
    # Check if the problematic types exist
    result = conn.execute(text("""
        SELECT typname FROM pg_type
        WHERE typname IN ('routingstrategy', 'modelprovider', 'optimizationgoal', 'predictionconfidence')
        ORDER BY typname;
    """))
    existing_types = [row[0] for row in result]

    if existing_types:
        print(f"   ⚠️  Found existing types: {', '.join(existing_types)}")
        print()
        print("2️⃣ Checking if these types are in use...")

        # Check if any tables use these types
        result = conn.execute(text("""
            SELECT DISTINCT t.typname, c.relname as table_name
            FROM pg_type t
            JOIN pg_attribute a ON a.atttypid = t.oid
            JOIN pg_class c ON a.attrelid = c.oid
            WHERE t.typname IN ('routingstrategy', 'modelprovider', 'optimizationgoal', 'predictionconfidence')
            AND c.relkind = 'r'
            ORDER BY t.typname, c.relname;
        """))

        usage = list(result)

        if usage:
            print("   ⚠️  These types are in use by tables:")
            for type_name, table_name in usage:
                print(f"      - {type_name} used by {table_name}")
            print()
            print("3️⃣ Options:")
            print("   A) Drop all related tables and types (clean start)")
            print("   B) Mark migrations as already applied (skip them)")
            print()

            choice = input("   Choose option (A/B) or press Enter to cancel: ").strip().upper()

            if choice == "A":
                print()
                print("   ⚠️  This will DROP the following tables:")
                for type_name, table_name in usage:
                    print(f"      - {table_name}")
                print()
                confirm = input("   Are you SURE? Type 'yes' to confirm: ").strip().lower()

                if confirm == "yes":
                    print()
                    print("   🗑️  Dropping tables...")

                    with engine.begin() as trans_conn:
                        # Get unique table names
                        tables_to_drop = sorted(set(table_name for _, table_name in usage))

                        for table_name in tables_to_drop:
                            try:
                                trans_conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE;"))
                                print(f"      ✅ Dropped {table_name}")
                            except Exception as e:
                                print(f"      ⚠️  Could not drop {table_name}: {e}")

                        # Drop the types
                        for type_name in existing_types:
                            try:
                                trans_conn.execute(text(f"DROP TYPE IF EXISTS {type_name} CASCADE;"))
                                print(f"      ✅ Dropped type {type_name}")
                            except Exception as e:
                                print(f"      ⚠️  Could not drop type {type_name}: {e}")

                    print()
                    print("   ✅ Cleanup complete!")
                    print()
                    print("   📝 Now run migrations:")
                    print("      python run_migration.py")
                else:
                    print("   ❌ Cancelled")
                    sys.exit(1)

            elif choice == "B":
                print()
                print("   ℹ️  To skip these migrations, we'll mark them as applied.")
                print("   This is safe if the tables already exist with correct structure.")
                print()

                with engine.begin() as trans_conn:
                    # Mark the problematic migration as applied
                    trans_conn.execute(text("""
                        INSERT INTO alembic_version (version_num)
                        VALUES ('20251219_0900')
                        ON CONFLICT (version_num) DO NOTHING;
                    """))
                    print("   ✅ Marked migration 20251219_0900 as applied")

                print()
                print("   📝 Now run migrations to apply remaining migrations:")
                print("      python run_migration.py")
            else:
                print("   ❌ Cancelled")
                sys.exit(1)
        else:
            print("   ✅ Types exist but are not in use")
            print()
            print("   Dropping unused types...")

            with engine.begin() as trans_conn:
                for type_name in existing_types:
                    try:
                        trans_conn.execute(text(f"DROP TYPE IF EXISTS {type_name} CASCADE;"))
                        print(f"   ✅ Dropped {type_name}")
                    except Exception as e:
                        print(f"   ⚠️  Error dropping {type_name}: {e}")

            print()
            print("   📝 Now run migrations:")
            print("      python run_migration.py")
    else:
        print("   ✅ No conflicting types found")
        print()
        print("   You can proceed with migrations:")
        print("      python run_migration.py")

print()
print("✅ Done!")

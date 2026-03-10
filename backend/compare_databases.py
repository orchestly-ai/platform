#!/usr/bin/env python3
"""
Compare SQLite and PostgreSQL databases
"""
import sqlite3
import psycopg2

print("=" * 80)
print("DATABASE COMPARISON: SQLite vs PostgreSQL")
print("=" * 80)

# SQLite
import os
sqlite_path = os.path.join(os.path.dirname(__file__), 'test_workflow.db')
sqlite_conn = sqlite3.connect(sqlite_path)
sqlite_cursor = sqlite_conn.cursor()
sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'alembic_version' ORDER BY name")
sqlite_tables = [row[0] for row in sqlite_cursor.fetchall()]

# Get SQLite migration version
sqlite_cursor.execute("SELECT version_num FROM alembic_version")
sqlite_version = sqlite_cursor.fetchone()
sqlite_version = sqlite_version[0] if sqlite_version else 'None'

sqlite_conn.close()

# PostgreSQL
pg_conn = psycopg2.connect(
    host='localhost',
    port=5432,
    user='postgres',
    password='',
    database='agent_orchestrator'
)
pg_cursor = pg_conn.cursor()
pg_cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name != 'alembic_version'
    ORDER BY table_name
""")
pg_tables = [row[0] for row in pg_cursor.fetchall()]

# Get PostgreSQL migration version
pg_cursor.execute("SELECT version_num FROM alembic_version")
pg_version = pg_cursor.fetchone()
pg_version = pg_version[0] if pg_version else 'None'

pg_conn.close()

# Print comparison
print()
print(f"SQLite Database (test_workflow.db)")
print(f"  Migration version: {sqlite_version}")
print(f"  Total tables: {len(sqlite_tables)}")
print()

print(f"PostgreSQL Database (agent_orchestrator)")
print(f"  Migration version: {pg_version}")
print(f"  Total tables: {len(pg_tables)}")
print()

# Tables only in SQLite
sqlite_only = set(sqlite_tables) - set(pg_tables)
if sqlite_only:
    print(f"❌ Tables ONLY in SQLite ({len(sqlite_only)}):")
    for table in sorted(sqlite_only):
        print(f"   - {table}")
    print()

# Tables only in PostgreSQL
pg_only = set(pg_tables) - set(sqlite_tables)
if pg_only:
    print(f"✅ Tables ONLY in PostgreSQL ({len(pg_only)}):")
    for table in sorted(pg_only):
        print(f"   - {table}")
    print()

# Common tables
common = set(sqlite_tables) & set(pg_tables)
print(f"📊 Common tables ({len(common)}):")
for table in sorted(common):
    print(f"   - {table}")
print()

# Important tables check
important_tables = [
    'routing_strategies',
    'ab_experiments',
    'ab_variants',
    'llm_models',
    'llm_providers',
    'agents',
    'workflows',
    'tasks'
]

print("🔍 Critical Feature Tables:")
print("-" * 80)
for table in important_tables:
    in_sqlite = "✓" if table in sqlite_tables else "✗"
    in_pg = "✓" if table in pg_tables else "✗"
    print(f"   {table:30s}  SQLite: {in_sqlite}   PostgreSQL: {in_pg}")

print()
print("=" * 80)

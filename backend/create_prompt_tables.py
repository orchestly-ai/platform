#!/usr/bin/env python3
"""
Create Prompt Registry tables in SQLite database
"""
import sqlite3
import sys
from pathlib import Path

# Database path
db_path = Path(__file__).parent / "test_workflow.db"

print(f"📁 Database: {db_path}")

# Connect to database
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Create prompt_templates table
print("Creating prompt_templates table...")
cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_templates (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    category TEXT,
    default_version_id TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
)
""")

# Create indexes for prompt_templates
cursor.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_template_org_slug
ON prompt_templates(organization_id, slug)
""")
cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_prompt_template_category
ON prompt_templates(category)
""")
cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_prompt_template_active
ON prompt_templates(is_active)
""")

# Create prompt_versions table
print("Creating prompt_versions table...")
cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_versions (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    variables TEXT DEFAULT '[]',
    model_hint TEXT,
    extra_metadata TEXT DEFAULT '{}',
    is_published INTEGER DEFAULT 0,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    FOREIGN KEY (template_id) REFERENCES prompt_templates(id) ON DELETE CASCADE
)
""")

# Create indexes for prompt_versions
cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_prompt_version_template_id
ON prompt_versions(template_id)
""")
cursor.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_version_template_version
ON prompt_versions(template_id, version)
""")
cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_prompt_version_published
ON prompt_versions(is_published)
""")

# Create prompt_usage_stats table
print("Creating prompt_usage_stats table...")
cursor.execute("""
CREATE TABLE IF NOT EXISTS prompt_usage_stats (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    date DATE NOT NULL,
    invocations INTEGER DEFAULT 0,
    avg_latency_ms REAL,
    avg_tokens INTEGER,
    success_rate REAL,
    FOREIGN KEY (version_id) REFERENCES prompt_versions(id) ON DELETE CASCADE
)
""")

# Create indexes for prompt_usage_stats
cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_prompt_usage_version_id
ON prompt_usage_stats(version_id)
""")
cursor.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_usage_version_date
ON prompt_usage_stats(version_id, date)
""")

# Commit changes
conn.commit()
conn.close()

print("✅ All Prompt Registry tables created successfully!")

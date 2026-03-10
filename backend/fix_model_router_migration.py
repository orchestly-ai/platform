#!/usr/bin/env python3
"""
Fix model router migration revision IDs

This script fixes the conflicting migration by:
1. Changing down_revision from filename format to actual revision ID
2. Changing revision ID to avoid conflicts
"""

import os

# Path to the problematic file
file_path = 'alembic/versions/20260114_0001_add_model_router.py'

if not os.path.exists(file_path):
    print(f"❌ File not found: {file_path}")
    print("This script should be run from the backend directory")
    exit(1)

# Read the file
with open(file_path, 'r') as f:
    content = f.read()

# Check if already fixed
if "'c3d4e5f6a7b8'" in content and "'e5f6a7b8c9d0'" in content:
    print("✅ Migration already fixed!")
    exit(0)

# Fix the down_revision (from filename format to actual revision ID)
content = content.replace(
    "down_revision = '20260113_0002'",
    "down_revision = 'c3d4e5f6a7b8'"
)

# Fix the revision ID to avoid conflict with prompt_registry
content = content.replace(
    "revision = '20260114_0001'",
    "revision = 'e5f6a7b8c9d0'"
)

# Write back
with open(file_path, 'w') as f:
    f.write(content)

print("✅ Fixed model_router migration!")
print("\nChanges made:")
print("  1. down_revision: '20260113_0002' → 'c3d4e5f6a7b8'")
print("     (Changed from filename format to actual revision ID)")
print("  2. revision: '20260114_0001' → 'e5f6a7b8c9d0'")
print("     (Changed to avoid conflict with prompt_registry)")
print("\nYou can now run: alembic upgrade head")

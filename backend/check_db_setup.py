#!/usr/bin/env python3
"""
Database Setup Checker and Fixer

Helps diagnose and fix database connection issues.

Usage:
    python check_db_setup.py
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd_list, check=False):
    """Run a command (as list) and return output. No shell=True for safety."""
    try:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode == 0, result.stdout, result.stderr
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd_list[0]}"
    except Exception as e:
        return False, "", str(e)

print("🔍 Checking PostgreSQL setup...\n")

# Check if PostgreSQL is running
print("1️⃣ Checking if PostgreSQL is running...")
success, stdout, stderr = run_command(["pg_isready"])
if success:
    print("   ✅ PostgreSQL is running")
else:
    print("   ❌ PostgreSQL is not running")
    print(f"   Output: {stderr}")
    print("\n   💡 Try starting PostgreSQL:")
    print("      brew services start postgresql")
    print("      OR")
    print("      brew services start postgresql@14")
    sys.exit(1)

# Check current user
print("\n2️⃣ Checking your system username...")
success, stdout, stderr = run_command(["whoami"])
username = stdout.strip() if success else "unknown"
print(f"   ℹ️  Your username: {username}")

# Check if we can connect with current user
print("\n3️⃣ Testing database connection with your username...")
success, stdout, stderr = run_command(["psql", "-U", username, "-d", "postgres", "-c", "SELECT 1;"])
if success:
    print(f"   ✅ Can connect as user '{username}'")
    db_user = username
else:
    print(f"   ⚠️  Cannot connect as user '{username}'")
    print(f"   Trying 'postgres' user...")
    success, stdout, stderr = run_command(["psql", "-U", "postgres", "-d", "postgres", "-c", "SELECT 1;"])
    if success:
        print("   ✅ Can connect as user 'postgres'")
        db_user = "postgres"
    else:
        print("   ❌ Cannot connect with any common username")
        print("\n   💡 Try one of these:")
        print(f"      1. Create a postgres superuser:")
        print(f"         createuser -s postgres")
        print(f"      2. Or use your current user:")
        print(f"         createuser -s {username}")
        sys.exit(1)

# Check if database exists
print(f"\n4️⃣ Checking if 'agent_orchestrator' database exists...")
success, stdout, stderr = run_command(["psql", "-U", db_user, "-lqt"])
db_exists = "agent_orchestrator" in stdout if success else False
if db_exists:
    print("   ✅ Database 'agent_orchestrator' exists")
else:
    print("   ⚠️  Database 'agent_orchestrator' does not exist")
    print("\n   Creating database...")
    success, stdout, stderr = run_command(["createdb", "-U", db_user, "agent_orchestrator"])
    if success:
        print("   ✅ Created database 'agent_orchestrator'")
    else:
        print(f"   ❌ Failed to create database: {stderr}")
        sys.exit(1)

# Generate correct configuration
print("\n5️⃣ Recommended configuration:")
print(f"   Database user: {db_user}")
print(f"   Database name: agent_orchestrator")
print(f"   Database host: localhost")
print(f"   Database port: 5432")

# Check .env file
env_file = Path(__file__).parent / ".env"
print(f"\n6️⃣ Checking .env file...")
if env_file.exists():
    print(f"   ✅ Found .env file at: {env_file}")
    with open(env_file) as f:
        content = f.read()
        if "POSTGRES_USER" in content:
            print("   ⚠️  POSTGRES_USER is already set in .env")
            print("   Please verify it's set to:")
            print(f"   POSTGRES_USER={db_user}")
            print(f"   POSTGRES_DB=agent_orchestrator")
        else:
            print("   Adding PostgreSQL configuration to .env...")
            with open(env_file, 'a') as f:
                f.write(f"\n# PostgreSQL Configuration\n")
                f.write(f"POSTGRES_USER={db_user}\n")
                f.write(f"POSTGRES_PASSWORD=\n")  # Empty password for local dev
                f.write(f"POSTGRES_HOST=localhost\n")
                f.write(f"POSTGRES_PORT=5432\n")
                f.write(f"POSTGRES_DB=agent_orchestrator\n")
            print("   ✅ Added PostgreSQL config to .env")
else:
    print(f"   ℹ️  No .env file found")
    print(f"   Creating .env file...")
    with open(env_file, 'w') as f:
        f.write(f"# PostgreSQL Configuration\n")
        f.write(f"POSTGRES_USER={db_user}\n")
        f.write(f"POSTGRES_PASSWORD=\n")  # Empty password for local dev
        f.write(f"POSTGRES_HOST=localhost\n")
        f.write(f"POSTGRES_PORT=5432\n")
        f.write(f"POSTGRES_DB=agent_orchestrator\n")
    print(f"   ✅ Created .env file with PostgreSQL config")

print("\n✅ Database setup complete!")
print("\n📝 Next steps:")
print("   1. Run migrations:")
print("      python run_migration.py")
print("   2. Start the backend server:")
print("      python main.py")
print("      OR")
print("      uvicorn main:app --reload")

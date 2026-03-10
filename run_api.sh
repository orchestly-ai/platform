#!/bin/bash
# API Server Runner Script
# Sets proper PYTHONPATH and runs the API server
#
# This script now loads configuration from .env file.
# Use USE_SQLITE=false in .env to use PostgreSQL instead of SQLite.

set -e

# Determine the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set PYTHONPATH to this directory so 'backend' module can be imported
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Load .env file if it exists (respects USE_SQLITE setting!)
# Only load simple key=value pairs, skip complex values like JSON arrays
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "Loading configuration from .env..."
    # Only export database-related and simple config variables
    eval $(grep -E '^(POSTGRES_|USE_SQLITE|DEBUG|ENVIRONMENT|REDIS_|API_HOST|API_PORT)' "$SCRIPT_DIR/.env" | grep -v '^#')
fi

# Default to SQLite only if USE_SQLITE is not set in .env
# IMPORTANT: If you want to use PostgreSQL, set USE_SQLITE=false in .env
export USE_SQLITE=${USE_SQLITE:-true}

# Set database connection (used when USE_SQLITE=false)
export POSTGRES_USER=${POSTGRES_USER:-$USER}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-""}
export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
export POSTGRES_PORT=${POSTGRES_PORT:-5432}
export POSTGRES_DB=${POSTGRES_DB:-"agent_orchestration"}

# Default to V1 API (most features enabled)
API_VERSION=${1:-v1}

echo "Starting Agent Orchestration Platform API..."
echo "  Directory: $SCRIPT_DIR"
if [ "$USE_SQLITE" = "true" ] || [ "$USE_SQLITE" = "True" ]; then
    echo "  Database: SQLite (local file)"
    echo "  Note: Credentials stored in SQLite will not persist across database resets"
else
    echo "  Database: PostgreSQL ($POSTGRES_USER@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB)"
fi
echo ""

if [ "$API_VERSION" = "v1" ]; then
    echo "Running API V1 (main.py)..."
    python -m backend.api.main
elif [ "$API_VERSION" = "v2" ]; then
    echo "Running API V2 (main_v2.py) with core modules..."
    python -m backend.api.main_v2
else
    echo "Usage: ./run_api.sh [v1|v2]"
    echo ""
    echo "  v1 - Original API (simple auth)"
    echo "  v2 - V2 API with core module integration (default)"
    exit 1
fi

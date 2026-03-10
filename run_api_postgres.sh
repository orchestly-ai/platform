#!/bin/bash
# API Server Runner Script with PostgreSQL
# Sets proper PYTHONPATH and runs the API server with PostgreSQL

set -e

# Determine the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment if it exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/venv/bin/activate"
elif [ -d "$SCRIPT_DIR/../venv" ]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/../venv/bin/activate"
fi

# Set PYTHONPATH to this directory so 'backend' module can be imported
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Use PostgreSQL instead of SQLite
export USE_SQLITE=false

# Enable extended routers (HITL, AB Testing, Cost, Audit)
export ENABLE_EXTENDED_ROUTERS=true

# Load .env file if it exists (for PostgreSQL credentials)
# Only load simple key=value pairs, skip complex values like JSON arrays
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "Loading database configuration from .env..."
    # Only export POSTGRES_* and USE_SQLITE variables to avoid JSON parsing issues
    eval $(grep -E '^(POSTGRES_|USE_SQLITE|DEBUG|ENVIRONMENT)' "$SCRIPT_DIR/.env" | grep -v '^#')
elif [ -f "$SCRIPT_DIR/backend/.env" ]; then
    echo "Loading database configuration from backend/.env..."
    eval $(grep -E '^(POSTGRES_|USE_SQLITE|DEBUG|ENVIRONMENT)' "$SCRIPT_DIR/backend/.env" | grep -v '^#')
fi

# Set database connection defaults (only if not already set by .env)
export POSTGRES_USER=${POSTGRES_USER:-$USER}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-""}
export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
export POSTGRES_PORT=${POSTGRES_PORT:-5432}
export POSTGRES_DB=${POSTGRES_DB:-agent_orchestration}

# Default to V1 API (most features enabled)
API_VERSION=${1:-v1}

echo "Starting Agent Orchestration Platform API..."
echo "  Directory: $SCRIPT_DIR"
echo "  Database: PostgreSQL ($POSTGRES_USER@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB)"
echo ""

if [ "$API_VERSION" = "v1" ]; then
    echo "Running API V1 (main.py)..."
    python -m backend.api.main
elif [ "$API_VERSION" = "v2" ]; then
    echo "Running API V2 (main_v2.py) with core modules..."
    python -m backend.api.main_v2
else
    echo "Usage: ./run_api_postgres.sh [v1|v2]"
    echo ""
    echo "  v1 - Original API (simple auth)"
    echo "  v2 - V2 API with core module integration (default)"
    exit 1
fi

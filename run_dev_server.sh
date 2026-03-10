#!/bin/bash
# Simple Development Server Startup Script
# Use this instead of running uvicorn directly to ensure correct PYTHONPATH

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to script directory
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d "backend/venv" ]; then
    echo "Activating virtual environment..."
    source "backend/venv/bin/activate"
elif [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source "venv/bin/activate"
fi

# Set PYTHONPATH to include this directory so 'backend' can be imported
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Use SQLite by default for easy development (no PostgreSQL required)
export USE_SQLITE=${USE_SQLITE:-true}

# Enable extended routers
export ENABLE_EXTENDED_ROUTERS=${ENABLE_EXTENDED_ROUTERS:-true}

echo "========================================"
echo "Starting Agent Orchestration Platform"
echo "========================================"
echo "  Directory: $SCRIPT_DIR"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  Database: ${USE_SQLITE:-true} (USE_SQLITE)"
echo "  API URL: http://localhost:8000"
echo "  Dashboard: http://localhost:3000 (run 'cd dashboard && npm run dev' in another terminal)"
echo "========================================"
echo ""

# Run uvicorn with reload for development
python -m uvicorn backend.api.main:app --reload --port 8000 --host 0.0.0.0

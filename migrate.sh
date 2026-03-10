#!/bin/bash
# Migration wrapper script - run from agent-orchestration directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔄 Running database migrations..."
echo "📁 Working directory: $(pwd)"
echo ""

# Set PYTHONPATH to include the agent-orchestration directory
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Run alembic from the backend directory
cd backend
alembic upgrade head

echo ""
echo "✅ Migrations complete!"

#!/bin/bash
# Run database migrations
# Usage: ./run_migrations.sh

cd "$(dirname "$0")"
export PYTHONPATH=.

echo "Running database migrations..."
alembic -c backend/alembic.ini upgrade head

echo "✅ Migrations complete!"

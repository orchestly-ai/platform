#!/bin/bash
# Demo Runner Script
# Sets proper PYTHONPATH and runs any demo script

# Set PYTHONPATH to parent directory so 'backend' module can be imported
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Set database connection
export POSTGRES_USER=${POSTGRES_USER:-$USER}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-""}
export POSTGRES_DB=${POSTGRES_DB:-"agent_orchestration"}

if [ -z "$1" ]; then
    echo "Usage: ./run_demo.sh <demo_script.py>"
    echo ""
    echo "Examples:"
    echo "  ./run_demo.sh backend/demo_integration_marketplace.py"
    echo "  ./run_demo.sh backend/demos/demo_customer_service.py"
    echo ""
    echo "Available demos in backend/:"
    ls backend/demo_*.py 2>/dev/null | sed 's/^/  /'
    echo ""
    echo "Available demos in backend/demos/:"
    ls backend/demos/demo_*.py 2>/dev/null | sed 's/^/  /'
    exit 1
fi

echo "Running demo: $1"
echo "PYTHONPATH=$PYTHONPATH"
echo ""

python "$1"

#!/bin/bash

# Script to test all demos

echo "================================"
echo "Testing All Backend Demos"
echo "================================"

PYTHONPATH=.

demos=(
    "backend/demo_cost_forecasting.py"
    "backend/demo_integration_marketplace.py"
    "backend/demo_multicloud.py"
    "backend/demo_realtime.py"
    "backend/demo_security.py"
    "backend/demo_sso_authentication.py"
    "backend/demo_supervisor_orchestration.py"
    "backend/demo_timetravel_debugging.py"
    "backend/demo_visual_dag_builder.py"
)

passed=0
failed=0

for demo in "${demos[@]}"; do
    echo ""
    echo "===== Testing: $demo ====="

    # Run with timeout and capture first 30 lines
    python "$demo" 2>&1 | head -30

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "✓ PASSED: $demo"
        ((passed++))
    else
        echo "✗ FAILED: $demo"
        ((failed++))
    fi
done

echo ""
echo "================================"
echo "Summary: $passed passed, $failed failed"
echo "================================"

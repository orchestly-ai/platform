#!/bin/bash
#
# Unified Test Runner for Agent Orchestration Platform
#
# This script runs all tests (backend + frontend) in one go.
# Use this before committing to ensure all tests pass.
#
# Usage:
#   ./scripts/run-tests.sh           # Run all tests
#   ./scripts/run-tests.sh backend   # Run only backend tests
#   ./scripts/run-tests.sh frontend  # Run only frontend tests
#   ./scripts/run-tests.sh --quick   # Run quick tests only (skip slow integration tests)
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Test result tracking
BACKEND_RESULT=0
FRONTEND_RESULT=0
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Agent Orchestration Platform - Test Runner${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Parse arguments
RUN_BACKEND=true
RUN_FRONTEND=true
QUICK_MODE=false

for arg in "$@"; do
    case $arg in
        backend)
            RUN_FRONTEND=false
            ;;
        frontend)
            RUN_BACKEND=false
            ;;
        --quick)
            QUICK_MODE=true
            ;;
        --help|-h)
            echo "Usage: $0 [backend|frontend] [--quick]"
            echo ""
            echo "Options:"
            echo "  backend   Run only backend Python tests"
            echo "  frontend  Run only frontend TypeScript tests"
            echo "  --quick   Skip slow integration/load tests"
            exit 0
            ;;
    esac
done

# ============================================================================
# Backend Tests (Python/pytest)
# ============================================================================
run_backend_tests() {
    echo -e "${YELLOW}━━━ Backend Tests (Python) ━━━${NC}"
    echo ""

    cd "$PROJECT_ROOT/backend"

    # Check if pytest is available
    if ! command -v pytest &> /dev/null; then
        echo -e "${RED}pytest not found. Install with: pip install pytest pytest-asyncio${NC}"
        return 1
    fi

    # Build pytest arguments
    PYTEST_ARGS="-v --tb=short"

    if [ "$QUICK_MODE" = true ]; then
        # Skip slow tests (integration, load tests)
        PYTEST_ARGS="$PYTEST_ARGS --ignore=tests/integration --ignore=tests/load"
    fi

    # Run tests
    echo "Running: pytest $PYTEST_ARGS tests/"
    echo ""

    if pytest $PYTEST_ARGS tests/; then
        echo -e "${GREEN}✓ Backend tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Backend tests failed${NC}"
        return 1
    fi
}

# ============================================================================
# Frontend Tests (TypeScript/Vitest)
# ============================================================================
run_frontend_tests() {
    echo ""
    echo -e "${YELLOW}━━━ Frontend Tests (TypeScript) ━━━${NC}"
    echo ""

    cd "$PROJECT_ROOT/dashboard"

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        npm install
    fi

    # Check if vitest is available
    if ! npm list vitest &> /dev/null 2>&1; then
        echo "Installing test dependencies..."
        npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
    fi

    # Run tests
    echo "Running: npm test"
    echo ""

    if npm test; then
        echo -e "${GREEN}✓ Frontend tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Frontend tests failed${NC}"
        return 1
    fi
}

# ============================================================================
# Type Checking
# ============================================================================
run_type_check() {
    echo ""
    echo -e "${YELLOW}━━━ Type Checking ━━━${NC}"
    echo ""

    cd "$PROJECT_ROOT/dashboard"

    echo "Running: npx tsc --noEmit"
    echo ""

    if npx tsc --noEmit; then
        echo -e "${GREEN}✓ Type check passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Type check failed${NC}"
        return 1
    fi
}

# ============================================================================
# Linting
# ============================================================================
run_lint() {
    echo ""
    echo -e "${YELLOW}━━━ Linting ━━━${NC}"
    echo ""

    cd "$PROJECT_ROOT/dashboard"

    echo "Running: npm run lint"
    echo ""

    # Run lint but don't fail on warnings
    if npm run lint 2>/dev/null || true; then
        echo -e "${GREEN}✓ Lint check completed${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Lint warnings found${NC}"
        return 0  # Don't fail on lint warnings
    fi
}

# ============================================================================
# Main Execution
# ============================================================================
echo "Test Configuration:"
echo "  Backend:  $([ "$RUN_BACKEND" = true ] && echo "✓" || echo "○")"
echo "  Frontend: $([ "$RUN_FRONTEND" = true ] && echo "✓" || echo "○")"
echo "  Quick:    $([ "$QUICK_MODE" = true ] && echo "✓" || echo "○")"
echo ""

START_TIME=$(date +%s)

# Run backend tests
if [ "$RUN_BACKEND" = true ]; then
    if run_backend_tests; then
        BACKEND_RESULT=0
    else
        BACKEND_RESULT=1
    fi
fi

# Run frontend tests
if [ "$RUN_FRONTEND" = true ]; then
    if run_frontend_tests; then
        FRONTEND_RESULT=0
    else
        FRONTEND_RESULT=1
    fi

    # Also run type check for frontend
    run_type_check
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$RUN_BACKEND" = true ]; then
    if [ $BACKEND_RESULT -eq 0 ]; then
        echo -e "  Backend:  ${GREEN}PASSED${NC}"
    else
        echo -e "  Backend:  ${RED}FAILED${NC}"
    fi
fi

if [ "$RUN_FRONTEND" = true ]; then
    if [ $FRONTEND_RESULT -eq 0 ]; then
        echo -e "  Frontend: ${GREEN}PASSED${NC}"
    else
        echo -e "  Frontend: ${RED}FAILED${NC}"
    fi
fi

echo ""
echo "  Duration: ${ELAPSED}s"
echo ""

# Exit with appropriate code
if [ $BACKEND_RESULT -ne 0 ] || [ $FRONTEND_RESULT -ne 0 ]; then
    echo -e "${RED}━━━ TESTS FAILED ━━━${NC}"
    exit 1
else
    echo -e "${GREEN}━━━ ALL TESTS PASSED ━━━${NC}"
    exit 0
fi

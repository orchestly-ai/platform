#!/bin/bash
#
# Setup Git Hooks for Agent Orchestration Platform
#
# This script installs git hooks that run tests before commits.
# Run this once after cloning the repository.
#
# Usage:
#   ./scripts/setup-git-hooks.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Find the git root (might be different from project root in monorepo)
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")

if [ -z "$GIT_ROOT" ]; then
    echo "Error: Not in a git repository"
    exit 1
fi

HOOKS_DIR="$GIT_ROOT/.git/hooks"

echo "Setting up git hooks..."
echo "  Git root: $GIT_ROOT"
echo "  Hooks dir: $HOOKS_DIR"
echo ""

# Create pre-commit hook
cat > "$HOOKS_DIR/pre-commit" << 'HOOK_EOF'
#!/bin/bash
#
# Pre-commit hook for Agent Orchestration Platform
# Runs quick tests before allowing commits
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Running pre-commit checks...${NC}"
echo ""

# Find the agent-orchestration directory
SCRIPT_PATH="$(git rev-parse --show-toplevel)"

if [ -d "$SCRIPT_PATH" ]; then
    # Check if test script exists
    if [ -f "$SCRIPT_PATH/scripts/run-tests.sh" ]; then
        echo "Running quick tests..."

        # Run quick tests (skip slow integration tests)
        if "$SCRIPT_PATH/scripts/run-tests.sh" --quick; then
            echo ""
            echo -e "${GREEN}✓ Pre-commit checks passed${NC}"
            exit 0
        else
            echo ""
            echo -e "${RED}✗ Pre-commit checks failed${NC}"
            echo ""
            echo "Commit aborted. Fix the issues above and try again."
            echo "To skip checks (not recommended): git commit --no-verify"
            exit 1
        fi
    else
        echo -e "${YELLOW}Warning: Test script not found, skipping tests${NC}"
        exit 0
    fi
else
    echo "Warning: agent-orchestration directory not found, skipping tests"
    exit 0
fi
HOOK_EOF

chmod +x "$HOOKS_DIR/pre-commit"

echo -e "✓ Pre-commit hook installed"
echo ""
echo "The pre-commit hook will run quick tests before each commit."
echo "To skip (not recommended): git commit --no-verify"
echo ""
echo "Done!"

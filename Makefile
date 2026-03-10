# Agent Orchestration Platform - Makefile
#
# Quick commands for development and testing
#
# Usage:
#   make test           - Run all tests AND demos (full verification)
#   make test-quick     - Run quick tests only (fast feedback)
#   make test-backend   - Run backend tests only
#   make test-frontend  - Run frontend tests only
#   make tests-only     - Run all tests without demos
#   make demos          - Run demo scripts only
#   make list           - List all tests and demos
#   make lint           - Run linting
#   make setup-hooks    - Install git pre-commit hooks
#   make help           - Show this help message

.PHONY: test test-quick test-backend test-frontend tests-only demos list lint setup-hooks help dev-backend dev-frontend install

# Default target
.DEFAULT_GOAL := help

# ============================================================================
# Testing
# ============================================================================

test: ## Run all tests AND demos (full verification before commit)
	@./scripts/run-all.sh

test-quick: ## Run quick tests only (fast feedback, minimal tests)
	@./scripts/run-all.sh --quick

test-backend: ## Run backend tests only
	@./scripts/run-all.sh --backend

test-frontend: ## Run frontend tests only
	@./scripts/run-all.sh --frontend

tests-only: ## Run all tests without demos
	@./scripts/run-all.sh --tests-only

test-watch: ## Run frontend tests in watch mode
	@cd dashboard && npm run test:watch

test-coverage: ## Run tests with coverage report
	@cd dashboard && npm run test:coverage
	@cd backend && pytest --cov=. --cov-report=html tests/

# ============================================================================
# Demos
# ============================================================================

demos: ## Run demo scripts to verify features work
	@./scripts/run-all.sh --demos

list: ## List all available tests and demos
	@./scripts/run-all.sh --list

# ============================================================================
# Linting & Type Checking
# ============================================================================

lint: ## Run linting
	@echo "Running frontend lint..."
	@cd dashboard && npm run lint || true
	@echo ""
	@echo "Running backend lint..."
	@cd backend && python -m flake8 . --max-line-length=120 --exclude=__pycache__,venv,.git 2>/dev/null || echo "flake8 not installed, skipping"

typecheck: ## Run TypeScript type checking
	@cd dashboard && npx tsc --noEmit

# ============================================================================
# Development
# ============================================================================

dev-backend: ## Start backend development server
	@cd backend && python -m uvicorn main:app --reload --port 8000

dev-frontend: ## Start frontend development server
	@cd dashboard && npm run dev

install: ## Install all dependencies
	@echo "Installing backend dependencies..."
	@cd backend && pip install -r requirements.txt 2>/dev/null || echo "No requirements.txt found"
	@echo ""
	@echo "Installing frontend dependencies..."
	@cd dashboard && npm install

# ============================================================================
# Git Hooks
# ============================================================================

setup-hooks: ## Install git pre-commit hooks
	@./scripts/setup-git-hooks.sh

# ============================================================================
# Help
# ============================================================================

help: ## Show this help message
	@echo ""
	@echo "Agent Orchestration Platform - Available Commands"
	@echo "================================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make test          # Run ALL tests + demos (recommended before commit)"
	@echo "  make test-quick    # Quick tests for fast feedback"
	@echo "  make tests-only    # Run tests without demos"
	@echo "  make list          # See all available tests and demos"
	@echo "  make setup-hooks   # Install pre-commit hooks (run once)"
	@echo ""

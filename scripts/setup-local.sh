#!/bin/bash
# ============================================================================
# Agent Orchestration Platform - Local Development Setup
# ============================================================================
#
# This script sets up the local development environment including:
# - PostgreSQL 16 and Redis 7 using Docker
# - Python virtual environment with dependencies
# - Database migrations
# - Initial configuration
#
# Usage: ./scripts/setup-local.sh
#
# Prerequisites:
# - Docker and Docker Compose installed
# - Python 3.11+
# - Node.js 18+ (for dashboard)
#
# ============================================================================

set -e  # Exit on any error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# Check Prerequisites
# ============================================================================

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker Desktop."
        echo "  macOS: brew install --cask docker"
        echo "  Linux: https://docs.docker.com/engine/install/"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker Desktop."
        exit 1
    fi

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed."
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log_info "Python version: $PYTHON_VERSION"

    # Check Node.js (optional, for dashboard)
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        log_info "Node.js version: $NODE_VERSION"
    else
        log_warn "Node.js not found. Required for dashboard development."
    fi

    log_success "Prerequisites check passed"
}

# ============================================================================
# Start Docker Services
# ============================================================================

start_docker_services() {
    log_info "Starting PostgreSQL and Redis with Docker..."

    cd "$ROOT_DIR"

    # Check if containers already exist
    if docker ps -a --format '{{.Names}}' | grep -q "^agentorch-postgres$"; then
        log_info "Containers already exist, starting them..."
        docker compose up -d postgres redis
    else
        log_info "Creating and starting containers..."
        docker compose up -d postgres redis
    fi

    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker exec agentorch-postgres pg_isready -U postgres &> /dev/null; then
            log_success "PostgreSQL is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "PostgreSQL did not become ready in time"
            exit 1
        fi
        sleep 1
    done

    # Wait for Redis to be ready
    log_info "Waiting for Redis to be ready..."
    for i in {1..30}; do
        if docker exec agentorch-redis redis-cli ping &> /dev/null; then
            log_success "Redis is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "Redis did not become ready in time"
            exit 1
        fi
        sleep 1
    done

    # Create database if it doesn't exist
    log_info "Ensuring database exists..."
    docker exec agentorch-postgres psql -U postgres -c "SELECT 1 FROM pg_database WHERE datname = 'agent_orchestrator'" | grep -q 1 || \
        docker exec agentorch-postgres psql -U postgres -c "CREATE DATABASE agent_orchestrator"

    log_success "Docker services are running"
}

# ============================================================================
# Setup Python Environment
# ============================================================================

setup_python_env() {
    log_info "Setting up Python virtual environment..."

    cd "$ROOT_DIR/backend"

    # Create venv if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_info "Virtual environment created"
    fi

    # Activate venv
    source venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip > /dev/null

    # Install dependencies
    log_info "Installing Python dependencies..."
    pip install -r requirements.txt

    log_success "Python environment ready"
}

# ============================================================================
# Setup Environment Variables
# ============================================================================

setup_env_file() {
    log_info "Setting up environment variables..."

    cd "$ROOT_DIR"

    if [ ! -f ".env" ]; then
        log_info "Creating .env file from .env.example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
        else
            # Create default .env
            cat > .env << 'EOF'
# ============================================================================
# Agent Orchestration Platform - Environment Configuration
# ============================================================================

# Application
ENVIRONMENT=development
DEBUG=true

# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agent_orchestrator
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# ============================================================================
# LLM Provider API Keys
# ============================================================================

# OpenAI (replace with your key)
OPENAI_API_KEY=
OPENAI_ORG_ID=
OPENAI_DEFAULT_MODEL=gpt-4o-mini

# Anthropic (replace with your key)
ANTHROPIC_API_KEY=
ANTHROPIC_DEFAULT_MODEL=claude-3-5-sonnet-20241022

# Azure OpenAI (Optional)
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Ollama (Local LLMs - Optional)
OLLAMA_BASE_URL=http://localhost:11434

# ============================================================================
# Cost Limits
# ============================================================================

# Default limits per agent (USD)
DEFAULT_AGENT_DAILY_COST_LIMIT=100.0
DEFAULT_AGENT_MONTHLY_COST_LIMIT=3000.0

# System-wide limits (USD)
SYSTEM_DAILY_COST_LIMIT=10000.0
SYSTEM_MONTHLY_COST_LIMIT=300000.0

# ============================================================================
# Task Configuration
# ============================================================================

DEFAULT_TASK_TIMEOUT_SECONDS=300
MAX_TASK_TIMEOUT_SECONDS=3600
DEFAULT_MAX_RETRIES=3
MAX_CONCURRENT_TASKS_PER_AGENT=5

# ============================================================================
# Authentication & Security
# ============================================================================

API_KEY_HEADER=X-API-Key
API_KEY_LENGTH=32
JWT_SECRET_KEY=dev-secret-key-for-agentorch-platform-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# ============================================================================
# Observability
# ============================================================================

# Metrics
ENABLE_METRICS=true
METRICS_PORT=9090

# Tracing (Optional)
ENABLE_TRACING=false
JAEGER_ENDPOINT=

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=

# ============================================================================
# Rate Limiting
# ============================================================================

RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=100
RATE_LIMIT_REQUESTS_PER_HOUR=5000

# ============================================================================
# CORS
# ============================================================================

CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost:5173"]
CORS_ALLOW_CREDENTIALS=true

# ============================================================================
# Feature Flags
# ============================================================================

ENABLE_VISUAL_WORKFLOW_DESIGNER=true
ENABLE_ML_ROUTING=false
ENABLE_CONFLICT_DETECTION=true
EOF
        fi
        log_success ".env file created"
    else
        log_info ".env file already exists"
    fi
}

# ============================================================================
# Run Database Migrations
# ============================================================================

run_migrations() {
    log_info "Running database migrations..."

    cd "$ROOT_DIR/backend"
    source venv/bin/activate

    # Run alembic migrations
    PYTHONPATH="$ROOT_DIR" alembic upgrade head

    log_success "Database migrations completed"
}

# ============================================================================
# Setup Dashboard
# ============================================================================

setup_dashboard() {
    log_info "Setting up dashboard..."

    cd "$ROOT_DIR/dashboard"

    if [ -f "package.json" ]; then
        if [ ! -d "node_modules" ]; then
            log_info "Installing dashboard dependencies..."
            npm install
        else
            log_info "Dashboard dependencies already installed"
        fi
        log_success "Dashboard ready"
    else
        log_warn "Dashboard package.json not found, skipping"
    fi
}

# ============================================================================
# Print Summary
# ============================================================================

print_summary() {
    echo ""
    echo "============================================================================"
    echo -e "${GREEN}Setup Complete!${NC}"
    echo "============================================================================"
    echo ""
    echo "To start the backend API:"
    echo "  cd backend && source venv/bin/activate"
    echo "  python -m backend.api.main"
    echo "  # API will be available at http://localhost:8000"
    echo ""
    echo "To start the dashboard:"
    echo "  cd dashboard && npm run dev"
    echo "  # Dashboard will be available at http://localhost:5173"
    echo ""
    echo "To view API documentation:"
    echo "  http://localhost:8000/docs"
    echo ""
    echo "To check service status:"
    echo "  docker compose ps"
    echo ""
    echo "To stop services:"
    echo "  docker compose down"
    echo ""
    echo "============================================================================"
    echo ""
    echo -e "${YELLOW}Important:${NC} Add your LLM API keys to .env file:"
    echo "  OPENAI_API_KEY=sk-..."
    echo "  ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    echo ""
    echo "============================================================================"
    echo "Agent Orchestration Platform - Local Development Setup"
    echo "============================================================================"
    echo ""

    check_prerequisites
    start_docker_services
    setup_env_file
    setup_python_env
    run_migrations
    setup_dashboard
    print_summary
}

# Run main
main

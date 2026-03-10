# Docker Compose Deployment

Deploy the Agent Orchestration Platform using Docker Compose for development and small-scale production deployments.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4 GB RAM minimum
- 20 GB disk space

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/orchestly-ai/platform.git
cd platform
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### 3. Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs
```

## Docker Compose Configuration

### docker-compose.yml

```yaml
version: '3.8'

services:
  # =============================================================================
  # API Server
  # =============================================================================
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/agent_orchestrator
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
      - DEBUG=${DEBUG:-false}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    networks:
      - agent-network

  # =============================================================================
  # Background Workers
  # =============================================================================
  worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A backend.worker worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/agent_orchestrator
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
    depends_on:
      - api
      - redis
    restart: unless-stopped
    networks:
      - agent-network

  # =============================================================================
  # Scheduler
  # =============================================================================
  scheduler:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A backend.worker beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/agent_orchestrator
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - worker
    restart: unless-stopped
    networks:
      - agent-network

  # =============================================================================
  # PostgreSQL Database
  # =============================================================================
  db:
    image: postgres:14-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=agent_orchestrator
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - agent-network

  # =============================================================================
  # Redis Cache & Queue
  # =============================================================================
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - agent-network

  # =============================================================================
  # Dashboard (React Frontend)
  # =============================================================================
  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    depends_on:
      - api
    restart: unless-stopped
    networks:
      - agent-network

  # =============================================================================
  # Nginx Reverse Proxy (Production)
  # =============================================================================
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
      - dashboard
    restart: unless-stopped
    networks:
      - agent-network
    profiles:
      - production

volumes:
  postgres_data:
  redis_data:

networks:
  agent-network:
    driver: bridge
```

## Environment Configuration

### .env.example

```bash
# =============================================================================
# Application Settings
# =============================================================================
DEBUG=false
SECRET_KEY=your-secret-key-here-change-in-production
ENVIRONMENT=development

# =============================================================================
# Database
# =============================================================================
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/agent_orchestrator

# =============================================================================
# Redis
# =============================================================================
REDIS_URL=redis://redis:6379/0

# =============================================================================
# API Settings
# =============================================================================
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# =============================================================================
# LLM Providers
# =============================================================================
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...

# =============================================================================
# Integrations (Optional)
# =============================================================================
SLACK_BOT_TOKEN=xoxb-...
GITHUB_TOKEN=ghp_...
SALESFORCE_CLIENT_ID=...
SALESFORCE_CLIENT_SECRET=...

# =============================================================================
# Monitoring (Optional)
# =============================================================================
SENTRY_DSN=https://...@sentry.io/...
```

## Dockerfile

```dockerfile
# =============================================================================
# Build Stage
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# =============================================================================
# Production Stage
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Commands

### Basic Operations

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a specific service
docker-compose restart api

# View logs
docker-compose logs -f api

# Scale workers
docker-compose up -d --scale worker=3
```

### Database Operations

```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Create new migration
docker-compose exec api alembic revision -m "Add new table"

# Access database shell
docker-compose exec db psql -U postgres agent_orchestrator

# Backup database
docker-compose exec db pg_dump -U postgres agent_orchestrator > backup.sql

# Restore database
docker-compose exec -T db psql -U postgres agent_orchestrator < backup.sql
```

### Debugging

```bash
# Access API shell
docker-compose exec api python

# Run tests
docker-compose exec api pytest

# Check container resources
docker stats
```

## Production Configuration

### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  api:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 1G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  worker:
    deploy:
      replicas: 5
      resources:
        limits:
          cpus: '1'
          memory: 2G

  db:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
    command: postgres -c max_connections=200 -c shared_buffers=2GB

  redis:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
```

### Run Production

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Nginx Configuration

### nginx/nginx.conf

```nginx
upstream api {
    server api:8000;
}

upstream dashboard {
    server dashboard:3000;
}

server {
    listen 80;
    server_name agent-orchestrator.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name agent-orchestrator.example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # API
    location /api/ {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Dashboard
    location / {
        proxy_pass http://dashboard;
        proxy_set_header Host $host;
    }
}
```

## Monitoring Stack

### docker-compose.monitoring.yml

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - agent-network

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    networks:
      - agent-network

volumes:
  prometheus_data:
  grafana_data:
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Check container status
docker-compose ps

# Inspect container
docker inspect agent-orchestration-api-1
```

### Database Connection Issues

```bash
# Check database is running
docker-compose exec db pg_isready

# Check connection from API
docker-compose exec api python -c "from backend.database.session import engine; print(engine.url)"
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Increase limits in docker-compose.yml
# Or add swap space
```

### Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Kill process or change port in docker-compose.yml
```

---

**Next Steps:**
- [Kubernetes Deployment](./kubernetes.md) for high availability
- [AWS Deployment](./aws.md) for cloud-native setup

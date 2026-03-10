# Development Guide - Agent Orchestration Platform

> **For developers (human or AI) continuing work on this project**

This document provides everything you need to understand what's been built and what to build next.

## 🗺️ Project Status Overview

### ✅ **Phase 1: COMPLETE - Foundation (Nov 2024)**

**What's Built:**
- Project structure and folder organization
- Core data models (Pydantic)
- LLM Gateway service with cost tracking
- Docker Compose for local development
- Comprehensive architecture documentation

**Files:**
```
backend/
├── shared/
│   ├── models.py          ✅ Complete - All Pydantic models
│   ├── config.py          ✅ Complete - Settings management
│   └── __init__.py        ✅ Complete
├── gateway/
│   ├── llm_proxy.py       ✅ Complete - LLM Gateway with OpenAI/Anthropic
│   └── __init__.py        ✅ Complete
├── requirements.txt       ✅ Complete
└── [orchestrator/]        ❌ TODO - Not built yet
    [observer/]            ❌ TODO - Not built yet
    [api/]                 ❌ TODO - Not built yet
```

### ✅ **Phase 2: COMPLETE - SDK & Demo (Nov 2024)**

**What's Built:**
- Complete Python SDK with decorators
- Agent registration and task polling
- LLM client integration
- Customer Support demo with 2 working agents

**Files:**
```
sdk/python/agent_orchestrator/
├── __init__.py           ✅ Complete
├── client.py             ✅ Complete - AgentClient
├── decorators.py         ✅ Complete - @register_agent, @task
├── llm.py                ✅ Complete - LLMClient
└── setup.py              ✅ Complete - PyPI packaging

examples/customer-support/
├── README.md             ✅ Complete
├── agents/
│   ├── triage_agent.py   ✅ Complete - Classifies tickets
│   ├── faq_agent.py      ✅ Complete - Auto-resolves FAQs
│   └── [technical_agent.py]  ❌ TODO - Not built yet
│       [billing_agent.py]    ❌ TODO - Not built yet
├── submit_tickets.py     ✅ Complete - Test data
└── requirements.txt      ✅ Complete
```

### ✅ **Phase 3: COMPLETE - Backend Services (Nov 2024)**

**What's Built:**
- ✅ Orchestrator Service (registry, router, queue)
- ✅ FastAPI REST API (all core endpoints)

**Files:**
```
backend/
├── orchestrator/
│   ├── __init__.py         ✅ Complete
│   ├── registry.py         ✅ Complete - Agent management
│   ├── router.py           ✅ Complete - Task routing
│   └── queue.py            ✅ Complete - Redis task queue
├── api/
│   ├── __init__.py         ✅ Complete
│   └── main.py             ✅ Complete - FastAPI app with all endpoints
```

### ✅ **Phase 4: COMPLETE - Observer Service (Nov 2024)**

**What's Built:**
- ✅ Metrics Collector (time-series data, aggregation)
- ✅ Alert Manager (alert detection, lifecycle, notifications)
- ✅ Observer API endpoints (metrics, alerts, time-series)
- ✅ Automatic metrics recording on task completion

**Files:**
```
backend/
├── observer/
│   ├── __init__.py            ✅ Complete
│   ├── metrics_collector.py   ✅ Complete - Metrics aggregation and analytics
│   └── alert_manager.py       ✅ Complete - Alert management and notifications
└── api/
    └── main.py                 ✅ Updated - Added 10 new observer endpoints
```

**Key Features:**
- Real-time metric collection and caching
- Per-capability performance analytics (latency P95/P99, cost, success rate)
- Per-agent performance tracking
- Time-series data storage (in-memory for MVP)
- Automatic alert detection (high queue depth, error rate, cost burn, agent health)
- Alert deduplication and cooldown
- Alert lifecycle management (active → acknowledged → resolved)
- Pluggable notification handlers (console, Slack, email)

**API Endpoints Added:**
```
GET  /api/v1/metrics/system                - Comprehensive system metrics
GET  /api/v1/metrics/capabilities/{name}   - Capability-specific metrics
GET  /api/v1/metrics/agents/{id}           - Agent performance metrics
GET  /api/v1/metrics/timeseries            - Time-series data
GET  /api/v1/alerts                        - Active alerts
GET  /api/v1/alerts/history                - Alert history
GET  /api/v1/alerts/stats                  - Alert statistics
POST /api/v1/alerts/{id}/acknowledge       - Acknowledge alert
POST /api/v1/alerts/{id}/resolve           - Resolve alert
```

### ✅ **Phase 5: COMPLETE - Database Persistence (Nov 2024)**

**What's Built:**
- ✅ SQLAlchemy ORM models (6 tables)
- ✅ Database repositories (data access layer)
- ✅ Alembic migration system
- ✅ Migration CLI tool
- ✅ Comprehensive database documentation

**Files:**
```
backend/
├── database/
│   ├── __init__.py          ✅ Complete
│   ├── session.py           ✅ Complete - Async session management
│   ├── models.py            ✅ Complete - 6 ORM models (350 lines)
│   ├── repositories.py      ✅ Complete - AgentRepo, TaskRepo (500 lines)
│   └── README.md            ✅ Complete - Full documentation
├── alembic/
│   ├── env.py               ✅ Complete - Alembic environment
│   ├── script.py.mako       ✅ Complete - Migration template
│   └── versions/
│       └── 001_initial.py   ✅ Complete - Initial schema
├── alembic.ini              ✅ Complete - Alembic configuration
└── migrate.py               ✅ Complete - Migration CLI
```

**Database Schema:**
```
agents (configuration)
  ├──< agent_states (runtime metrics) [1:1]
  ├──< tasks (lifecycle) [1:N]
  │     └──< task_executions (history) [1:N]
  ├──< alerts (monitoring) [1:N]
  └──  metrics (time-series, TimescaleDB-ready)
```

**Key Features:**
- Async SQLAlchemy with asyncpg driver
- Connection pooling (size: 10, overflow: 20)
- Repository pattern for data access
- Automatic session management (commit/rollback)
- Comprehensive indexing strategy
- TimescaleDB-ready metrics table
- Migration version control with Alembic
- CLI tool for migration management

**Migration Commands:**
```bash
python migrate.py upgrade head   # Apply migrations
python migrate.py check          # Check database status
python migrate.py create "msg"   # Create new migration
python migrate.py reset          # Reset database (dev only)
```

---

## 🎯 What to Build Next (Priority Order)

### **TASK 1: Orchestrator Service** ✅ COMPLETE (Nov 2024)

**Purpose:** Task routing and agent coordination

**Location:** `backend/orchestrator/`

**What to Build:**

1. **`backend/orchestrator/__init__.py`**
   - Module initialization

2. **`backend/orchestrator/registry.py`**
   ```python
   class AgentRegistry:
       """Manages registered agents and their capabilities."""

       async def register_agent(agent_config: AgentConfig) -> UUID:
           """Register new agent, return agent_id"""

       async def get_agent(agent_id: UUID) -> AgentState:
           """Get agent status"""

       async def find_agents_by_capability(capability: str) -> List[UUID]:
           """Find all agents that can handle this capability"""

       async def update_agent_status(agent_id: UUID, status: AgentStatus):
           """Update agent status (active, idle, error, etc)"""
   ```

3. **`backend/orchestrator/router.py`**
   ```python
   class TaskRouter:
       """Routes tasks to appropriate agents."""

       async def route_task(task: Task) -> UUID:
           """
           Find best agent for task based on:
           - Capability match
           - Agent availability
           - Current load
           Returns: agent_id to assign task to
           """

       async def assign_task(task_id: UUID, agent_id: UUID):
           """Assign task to agent, update task status"""
   ```

4. **`backend/orchestrator/queue.py`**
   ```python
   class TaskQueue:
       """Manages task queue using Redis."""

       async def enqueue_task(task: Task):
           """Add task to queue"""

       async def get_next_task(capability: str) -> Optional[Task]:
           """Get next task matching capability"""

       async def complete_task(task_id: UUID, result: TaskOutput):
           """Mark task complete, store result"""

       async def fail_task(task_id: UUID, error: str):
           """Mark task failed, implement retry logic"""
   ```

**Dependencies:**
- Redis (already in docker-compose.yml)
- PostgreSQL (already in docker-compose.yml)
- Shared models (already built in backend/shared/models.py)

**How to Test:**
```python
# Unit tests
pytest backend/orchestrator/tests/

# Integration test
1. Start docker-compose
2. Register an agent via API
3. Submit a task
4. Verify agent receives task
5. Submit result
6. Verify task marked complete
```

---

### **TASK 2: FastAPI Endpoints** ✅ COMPLETE (Nov 2024)

**Purpose:** REST API for SDK and dashboard

**Location:** `backend/api/`

**Status: IMPLEMENTED** - See `backend/api/main.py` (400+ lines)

1. **`backend/api/main.py`**
   ```python
   from fastapi import FastAPI, HTTPException, Depends
   from backend.shared.models import AgentConfig, Task, TaskResult
   from backend.orchestrator.registry import AgentRegistry
   from backend.orchestrator.queue import TaskQueue
   from backend.gateway.llm_proxy import LLMGateway

   app = FastAPI(title="Agent Orchestration Platform")

   # Initialize services
   registry = AgentRegistry()
   queue = TaskQueue()
   gateway = LLMGateway()

   @app.post("/api/v1/agents")
   async def register_agent(config: AgentConfig):
       """Register new agent"""
       agent_id = await registry.register_agent(config)
       api_key = generate_api_key()  # TODO: implement
       return {"agent_id": agent_id, "api_key": api_key}

   @app.get("/api/v1/agents/{agent_id}")
   async def get_agent(agent_id: UUID):
       """Get agent status and metrics"""
       return await registry.get_agent(agent_id)

   @app.post("/api/v1/tasks")
   async def submit_task(task: Task):
       """Submit new task"""
       task_id = await queue.enqueue_task(task)
       return {"task_id": task_id, "status": "queued"}

   @app.get("/api/v1/agents/{agent_id}/tasks/next")
   async def get_next_task(agent_id: UUID, capabilities: str):
       """Poll for next task (used by SDK)"""
       caps = capabilities.split(",")
       for cap in caps:
           task = await queue.get_next_task(cap)
           if task:
               return task
       return Response(status_code=204)  # No tasks available

   @app.post("/api/v1/tasks/{task_id}/result")
   async def submit_result(task_id: UUID, result: TaskResult):
       """Submit task result"""
       if result.status == "completed":
           await queue.complete_task(task_id, result.output)
       else:
           await queue.fail_task(task_id, result.error)
       return {"status": "ok"}

   @app.post("/api/v1/llm/completions")
   async def llm_completion(request: LLMRequest):
       """Proxy LLM request through gateway"""
       response = await gateway.proxy_request(
           agent_id=request.agent_id,
           provider=request.provider,
           model=request.model,
           messages=request.messages,
           temperature=request.temperature,
           max_tokens=request.max_tokens
       )
       return response

   @app.post("/api/v1/agents/{agent_id}/heartbeat")
   async def heartbeat(agent_id: UUID):
       """Agent heartbeat"""
       await registry.update_heartbeat(agent_id)
       return {"status": "ok"}
   ```

2. **`backend/api/auth.py`**
   ```python
   # API key authentication middleware
   async def verify_api_key(api_key: str = Header(...)):
       """Verify API key is valid"""
       # TODO: Check against database
       if not is_valid_key(api_key):
           raise HTTPException(401, "Invalid API key")
       return api_key
   ```

3. **`backend/api/middleware.py`**
   ```python
   # Rate limiting, CORS, logging middleware
   ```

**How to Run:**
```bash
cd backend
uvicorn api.main:app --reload --port 8000
```

**How to Test:**
```bash
# Manual test
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "test_agent", "capabilities": ["test"]}'

# Automated tests
pytest backend/api/tests/
```

---

### **TASK 3: Observer Service** ✅ COMPLETE (Nov 2024)

**Purpose:** Metrics collection and monitoring

**Location:** `backend/observer/`

**Status: IMPLEMENTED** - See Phase 4 overview above for complete details

**What Was Built:**

1. **`backend/observer/metrics_collector.py`** (400+ lines)
   - Real-time metric collection and caching
   - Per-capability analytics (latency P95/P99, cost, success rate)
   - Per-agent performance tracking
   - Time-series data storage (in-memory for MVP)
   - Automatic metric recording on task completion

2. **`backend/observer/alert_manager.py`** (300+ lines)
   - Alert detection (5 alert types)
   - Alert deduplication and cooldown
   - Alert lifecycle management (active → acknowledged → resolved)
   - Notification handler framework
   - Auto-resolution of cleared alerts

3. **API Endpoints** (added to `backend/api/main.py`)
   - 9 new endpoints for metrics and alerts
   - See Phase 4 overview above for full list

**Note:** For MVP, metrics are stored in-memory. For production, migrate to TimescaleDB:
```sql
-- Production migration (TODO)
CREATE TABLE agent_metrics (
    time TIMESTAMPTZ NOT NULL,
    agent_id UUID NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    tags JSONB
);

SELECT create_hypertable('agent_metrics', 'time');
SELECT agent_id, SUM(metric_value) as total_cost
FROM agent_metrics
WHERE metric_name = 'cost'
  AND time > NOW() - INTERVAL '24 hours'
GROUP BY agent_id;
```

---

### **TASK 4: Database Layer** (MEDIUM PRIORITY)

**Purpose:** Persistent storage for agents, tasks, metrics

**Location:** `backend/database/`

**What to Build:**

1. **`backend/database/schema.sql`**
   ```sql
   -- Agents table
   CREATE TABLE agents (
       agent_id UUID PRIMARY KEY,
       name VARCHAR(255) UNIQUE NOT NULL,
       config JSONB NOT NULL,
       created_at TIMESTAMPTZ DEFAULT NOW(),
       updated_at TIMESTAMPTZ DEFAULT NOW()
   );

   -- Tasks table
   CREATE TABLE tasks (
       task_id UUID PRIMARY KEY,
       capability VARCHAR(100) NOT NULL,
       input JSONB NOT NULL,
       output JSONB,
       status VARCHAR(50) NOT NULL,
       assigned_agent_id UUID REFERENCES agents(agent_id),
       cost FLOAT,
       created_at TIMESTAMPTZ DEFAULT NOW(),
       completed_at TIMESTAMPTZ
   );

   CREATE INDEX idx_tasks_status ON tasks(status);
   CREATE INDEX idx_tasks_capability ON tasks(capability);

   -- LLM requests log (for observability)
   CREATE TABLE llm_requests (
       request_id UUID PRIMARY KEY,
       agent_id UUID REFERENCES agents(agent_id),
       task_id UUID REFERENCES tasks(task_id),
       provider VARCHAR(50) NOT NULL,
       model VARCHAR(100) NOT NULL,
       prompt_tokens INT NOT NULL,
       completion_tokens INT NOT NULL,
       cost FLOAT NOT NULL,
       latency_ms FLOAT NOT NULL,
       created_at TIMESTAMPTZ DEFAULT NOW()
   );

   CREATE INDEX idx_llm_requests_agent ON llm_requests(agent_id);
   CREATE INDEX idx_llm_requests_created ON llm_requests(created_at);
   ```

2. **`backend/database/models.py`**
   ```python
   # SQLAlchemy ORM models
   from sqlalchemy import Column, String, Float, DateTime, JSON
   from sqlalchemy.dialects.postgresql import UUID

   class Agent(Base):
       __tablename__ = "agents"

       agent_id = Column(UUID, primary_key=True)
       name = Column(String(255), unique=True)
       config = Column(JSON)
       # etc.
   ```

3. **`backend/database/migrations/`**
   ```bash
   # Alembic migrations
   alembic init migrations
   alembic revision --autogenerate -m "Initial schema"
   alembic upgrade head
   ```

---

### **TASK 5: Dockerfiles** (MEDIUM PRIORITY)

**Purpose:** Containerization for deployment

**Location:** `deployment/docker/`

**What to Build:**

1. **`backend/Dockerfile`**
   ```dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   # Install dependencies
   COPY backend/requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Copy application code
   COPY backend/ /app/

   # Expose ports
   EXPOSE 8000 9090

   # Run application
   CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

2. **`dashboard/Dockerfile.dev`**
   ```dockerfile
   FROM node:18-alpine

   WORKDIR /app

   COPY dashboard/package*.json ./
   RUN npm install

   COPY dashboard/ .

   EXPOSE 3000

   CMD ["npm", "start"]
   ```

---

### **TASK 6: React Dashboard** (LOWER PRIORITY - Can Wait)

**Purpose:** Real-time monitoring UI

**Location:** `dashboard/`

**What to Build:**

1. **Dashboard pages:**
   - `/` - Overview (system metrics, active agents, task queue)
   - `/agents` - Agent list with status
   - `/agents/:id` - Agent detail (metrics, costs, tasks)
   - `/tasks` - Task queue and history
   - `/costs` - Cost breakdown and trends

2. **Key components:**
   - AgentCard - Show agent status
   - TaskQueue - Real-time task list
   - CostChart - Cost over time
   - MetricsPanel - Key metrics

3. **WebSocket integration:**
   ```typescript
   // Real-time updates from backend
   const ws = new WebSocket('ws://localhost:8000/ws');
   ws.onmessage = (event) => {
       const update = JSON.parse(event.data);
       // Update UI state
   };
   ```

---

## 🔧 Development Workflow

### **Setting Up Development Environment**

```bash
# 1. Clone repository
git clone https://github.com/orchestly-ai/platform.git
cd platform

# 2. Start infrastructure
docker-compose up -d postgres redis

# 3. Install backend dependencies
cd backend
pip install -r requirements.txt

# 4. Install SDK (editable mode)
cd ../sdk/python
pip install -e .

# 5. Run database migrations
cd ../../backend
alembic upgrade head

# 6. Start API server
uvicorn api.main:app --reload --port 8000

# 7. (Optional) Start dashboard
cd ../dashboard
npm install
npm start
```

### **Testing Your Changes**

```bash
# Run backend tests
cd backend
pytest

# Run SDK tests
cd sdk/python
pytest

# Run example agents
cd examples/customer-support
python agents/triage_agent.py
```

### **Git Workflow**

```bash
# Create feature branch
git checkout -b feature/orchestrator-service

# Make changes, commit frequently
git add backend/orchestrator/
git commit -m "Add orchestrator service with task routing"

# Push and create PR
git push origin feature/orchestrator-service
```

---

## 📁 Project Structure Reference

```
platform/agent-orchestration/
├── README.md                     # Main project overview
├── DEVELOPMENT_GUIDE.md          # This file
├── .env.example                  # Environment template
├── docker-compose.yml            # Local development setup
│
├── backend/                      # Python backend services
│   ├── shared/                   # ✅ COMPLETE
│   │   ├── models.py            # Pydantic models
│   │   ├── config.py            # Settings
│   │   └── __init__.py
│   ├── gateway/                  # ✅ COMPLETE
│   │   ├── llm_proxy.py         # LLM Gateway
│   │   └── __init__.py
│   ├── orchestrator/             # ❌ TODO - NEXT TO BUILD
│   │   ├── registry.py          # Agent registry
│   │   ├── router.py            # Task routing
│   │   ├── queue.py             # Task queue
│   │   └── __init__.py
│   ├── api/                      # ❌ TODO
│   │   ├── main.py              # FastAPI app
│   │   ├── auth.py              # Authentication
│   │   └── middleware.py        # Middlewares
│   ├── observer/                 # ❌ TODO
│   │   ├── metrics.py           # Metrics collection
│   │   └── alerts.py            # Alerting
│   ├── database/                 # ❌ TODO
│   │   ├── schema.sql           # Database schema
│   │   ├── models.py            # SQLAlchemy models
│   │   └── migrations/          # Alembic migrations
│   └── requirements.txt          # ✅ COMPLETE
│
├── sdk/python/                   # ✅ COMPLETE - Python SDK
│   ├── agent_orchestrator/
│   │   ├── client.py            # API client
│   │   ├── decorators.py        # @register_agent, @task
│   │   ├── llm.py               # LLM client
│   │   └── __init__.py
│   ├── setup.py                 # PyPI packaging
│   └── README.md                # SDK documentation
│
├── examples/                     # Demo workflows
│   └── customer-support/         # ✅ PARTIAL - 2/4 agents built
│       ├── README.md            # Workflow documentation
│       ├── agents/
│       │   ├── triage_agent.py  # ✅ COMPLETE
│       │   ├── faq_agent.py     # ✅ COMPLETE
│       │   ├── technical_agent.py   # ❌ TODO
│       │   └── billing_agent.py     # ❌ TODO
│       ├── submit_tickets.py    # Test data
│       └── requirements.txt
│
├── dashboard/                    # ❌ TODO - React dashboard
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   └── package.json
│
├── deployment/                   # Deployment configs
│   ├── docker/                   # ❌ TODO - Dockerfiles
│   ├── kubernetes/               # ❌ TODO - K8s manifests
│   └── terraform/                # ❌ TODO - IaC
│
└── docs/                         # Documentation
    └── architecture.md           # ✅ COMPLETE - System design
```

---

## 🎯 Quick Start for New Developer

**"I want to continue this project. What do I do?"**

1. **Read these files first:**
   - `README.md` - Understand the vision
   - `docs/architecture.md` - Understand the system design
   - This file - Understand what's built and what's next

2. **Start with Task 1: Orchestrator Service**
   - This is the highest priority
   - It unblocks the SDK (agents can actually receive tasks)
   - Location: `backend/orchestrator/`
   - See "TASK 1" section above for detailed specs

3. **Test your work:**
   - Run the example agents
   - They should now receive and process tasks
   - Verify in logs and dashboard

4. **Move to Task 2: FastAPI Endpoints**
   - This connects everything together
   - Enables SDK to communicate with orchestrator

---

## 💡 Design Decisions to Know

### **Why Redis for Task Queue?**
- Fast in-memory operations
- Built-in pub/sub for real-time updates
- Easy to scale horizontally
- Can upgrade to Kafka later if needed

### **Why TimescaleDB for Metrics?**
- PostgreSQL-compatible (familiar SQL)
- Optimized for time-series data
- Automatic data compression
- Great for cost/performance trends

### **Why Pydantic Models Everywhere?**
- Type safety at runtime
- Automatic validation
- JSON serialization built-in
- Great IDE autocomplete

### **Why Decorators in SDK?**
- Minimal boilerplate for developers
- Pythonic and intuitive
- Hides complexity of orchestration
- Similar to Flask/FastAPI (familiar pattern)

---

## 🚨 Common Gotchas

1. **UUID vs String:** Always use UUID objects internally, convert to string only for JSON

2. **Async/Await:** All I/O operations should be async (database, Redis, HTTP)

3. **Error Handling:** Always catch and log errors, never let exceptions crash the service

4. **Cost Calculation:** Use exact token counts, not estimates (for accurate billing)

5. **API Keys:** Store hashed, never plaintext. Rotate regularly.

---

## 🔍 Code Patterns to Follow

**When implementing new services, follow these existing patterns:**

### **Pattern 1: Service Initialization (from LLMGateway)**

See: `backend/gateway/llm_proxy.py`

```python
# Global instance pattern
_gateway: Optional[LLMGateway] = None

def get_gateway() -> LLMGateway:
    """Get or create gateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway

# Usage in API
gateway = get_gateway()
response = await gateway.proxy_request(...)
```

**Apply this pattern to:**
- OrchestrationService in `backend/orchestrator/`
- ObserverService in `backend/observer/`

### **Pattern 2: Pydantic Models for Validation (from shared/models.py)**

See: `backend/shared/models.py`

```python
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime

class AgentConfig(BaseModel):
    """Agent configuration with validation."""
    agent_id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Unique agent name")
    cost_limit_daily: float = Field(100.0, description="Max daily cost USD")
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Automatic validation
config = AgentConfig(name="test", cost_limit_daily=50.0)
# Raises ValidationError if invalid
```

**Apply this pattern to:**
- Request/response models in FastAPI
- Database models via SQLAlchemy + Pydantic

### **Pattern 3: Async Error Handling (from SDK client.py)**

See: `sdk/python/agent_orchestrator/client.py`

```python
async def get_next_task(self, capabilities: List[str]) -> Optional[Dict]:
    """Poll for next task with graceful error handling."""
    try:
        response = await self.client.get(f"/api/v1/tasks/next")

        if response.status_code == 204:  # No content = no tasks
            return None

        response.raise_for_status()
        return response.json()

    except httpx.HTTPError as e:
        # Log but don't crash - return None to continue polling
        print(f"Error polling for tasks: {e}")
        return None
```

**Apply this pattern to:**
- All API endpoints
- All service-to-service calls
- Database operations

### **Pattern 4: Settings Management (from shared/config.py)**

See: `backend/shared/config.py`

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Load from environment variables."""
    API_PORT: int = Field(default=8000, description="API server port")
    POSTGRES_HOST: str = Field(default="localhost")

    @property
    def DATABASE_URL(self) -> str:
        """Computed property."""
        return f"postgresql://{self.POSTGRES_USER}@{self.POSTGRES_HOST}"

    class Config:
        env_file = ".env"

# Global instance
settings = Settings()

# Usage anywhere
from backend.shared.config import settings
print(settings.API_PORT)
```

**Apply this pattern to:**
- Any new configuration needs
- Feature flags
- Service-specific settings

### **Pattern 5: Decorator-Based API (from SDK decorators.py)**

See: `sdk/python/agent_orchestrator/decorators.py`

```python
def register_agent(name: str, capabilities: List[str], **kwargs):
    """Decorator that modifies a class."""
    def decorator(cls):
        # Store metadata on class
        cls._agent_config = AgentConfig(name=name, capabilities=capabilities)

        # Add helper methods
        async def _register(self):
            return await client.register_agent(cls._agent_config)

        cls._register = _register
        return cls
    return decorator

# Usage
@register_agent(name="my_agent", capabilities=["task1"])
class MyAgent:
    pass
```

**Apply this pattern to:**
- Any SDK extensions
- Middleware decorators in FastAPI

### **Pattern 6: Comprehensive Docstrings (everywhere)**

Every function should have:

```python
async def route_task(self, task: Task) -> UUID:
    """
    Route task to best available agent.

    Args:
        task: Task to route

    Returns:
        UUID of assigned agent

    Raises:
        ValueError: If no agents match capability
        RuntimeError: If routing fails

    Example:
        >>> agent_id = await router.route_task(task)
        >>> print(f"Assigned to {agent_id}")
    """
```

---

## 📞 Questions?

If you're stuck or unsure about anything:

1. **Check existing code for patterns** (see section above)
2. **Read the architecture.md** for system design decisions
3. **Look at working agents** (triage_agent.py, faq_agent.py) for SDK usage
4. **Review shared/models.py** for data structure examples
5. **Create an issue on GitHub** if truly blocked

---

## 🎯 Quick Reference: Where to Find Things

| Need to... | Look at... |
|-----------|-----------|
| Understand data models | `backend/shared/models.py` |
| See async patterns | `backend/gateway/llm_proxy.py` |
| Learn SDK usage | `examples/customer-support/agents/triage_agent.py` |
| Check settings | `backend/shared/config.py` |
| See error handling | `sdk/python/agent_orchestrator/client.py` |
| Understand architecture | `docs/architecture.md` |
| Get started | `README.md` |

---

**Last Updated:** November 14, 2024
**Project Status:** Phase 3 Complete - Backend Fully Functional
**Next Task:** Observer Service (backend/observer/) for advanced metrics
**Current State:** Agents can now register, receive tasks, and execute!

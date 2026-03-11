# Orchestly

[![CI](https://github.com/orchestly-ai/platform/actions/workflows/ci.yml/badge.svg)](https://github.com/orchestly-ai/platform/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/orchestly-ai/platform)](https://github.com/orchestly-ai/platform)

**Open-source orchestration platform for AI agents.**

Orchestly lets you register, route, monitor, and govern AI agents across your organization. Connect any LLM, build multi-step workflows, and ship reliable AI applications — all from a single dashboard.

## Features

- **Agent Registry** — Register and manage agents across frameworks (LangChain, CrewAI, AutoGen, custom)
- **Workflow Builder** — Visual drag-and-drop workflow designer with branching, loops, and error handling
- **Smart LLM Router** — Route requests across OpenAI, Anthropic, Google, Groq, and more with cost/latency/quality optimization
- **A/B Testing** — Experiment with different LLM configurations and measure real user satisfaction
- **Prompt Registry** — Version-controlled prompt templates with rendering and analytics
- **RBAC & Multi-Tenancy** — Fine-grained permissions, roles, and organization isolation
- **Cost Management** — Track spend per agent, team, and workflow with budget alerts
- **Audit Logs** — Full audit trail for compliance (SOC 2, HIPAA-ready)
- **Human-in-the-Loop** — Approval workflows for sensitive agent actions
- **Integrations Marketplace** — Pre-built connectors for Slack, GitHub, Jira, Salesforce, and 20+ services
- **Real-time Monitoring** — Live metrics, alerts, and agent health dashboards

## Quick Start

### Option 1: Run locally (no Docker needed)

```bash
git clone https://github.com/orchestly-ai/platform.git orchestly
cd orchestly

# Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r backend/requirements.txt

# Start the API (uses SQLite — no Postgres required)
ADMIN_PASSWORD=admin123 USE_SQLITE=true ENABLE_EXTENDED_ROUTERS=true \
  python -m uvicorn backend.api.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the Swagger UI.

Login: `admin@example.com` / `admin123`

To run the **dashboard** (separate terminal):

```bash
cd dashboard
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) for the dashboard.

### Option 2: Docker Compose

```bash
git clone https://github.com/orchestly-ai/platform.git orchestly
cd orchestly
cp .env.example .env
docker compose up
```

This starts PostgreSQL, Redis, the API at `localhost:8000`, and the dashboard at `localhost:3000`.

### Register your first agent

```python
import requests

resp = requests.post("http://localhost:8000/api/v1/agents/register", json={
    "name": "My Agent",
    "framework": "langchain",
    "capabilities": ["summarization", "qa"],
})
print(resp.json())
```

## Architecture

```
orchestly/
├── backend/           # FastAPI + SQLAlchemy async
│   ├── api/           # REST API routes
│   ├── shared/        # Business logic & services
│   ├── database/      # Models & session management
│   └── tests/         # pytest test suite
├── dashboard/         # React + Vite + TypeScript
│   ├── src/
│   │   ├── pages/     # Page components
│   │   ├── components/# Reusable UI components
│   │   └── services/  # API client
│   └── package.json
└── docker-compose.yml
```

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy 2.0 (async), aiosqlite (dev) / asyncpg (prod)
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS
- **Auth**: JWT with RBAC, optional SSO/SAML

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Database (SQLite for dev, PostgreSQL for prod)
DATABASE_URL=sqlite+aiosqlite:///./orchestly.db

# LLM Providers (add your keys)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=

# Auth
JWT_SECRET_KEY=           # Generate with: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
ADMIN_PASSWORD=
```

See [`.env.example`](.env.example) for all available configuration options.

## Development

```bash
# Backend (from project root)
python3 -m venv venv && source venv/bin/activate && pip install -r backend/requirements.txt
USE_SQLITE=true ENABLE_EXTENDED_ROUTERS=true python -m uvicorn backend.api.main:app --reload

# Frontend (separate terminal)
cd dashboard && npm install && npm run dev
```

Run tests:

```bash
USE_SQLITE=true ENABLE_EXTENDED_ROUTERS=true PYTHONPATH=. python -m pytest backend/tests/
```

## Roadmap

See [ROADMAP.md](ROADMAP.md) for what's coming next.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md) for our responsible disclosure policy.

## License

Apache License 2.0 — see [LICENSE](LICENSE).

# Contributing to Orchestly

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- Git

### Backend

```bash
# From project root
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r backend/requirements.txt

# Run the server
USE_SQLITE=true ENABLE_EXTENDED_ROUTERS=true \
  python -m uvicorn backend.api.main:app --reload
```

### Frontend

```bash
cd dashboard
npm install
npm run dev
```

### Running Tests

```bash
# Backend tests (from project root, with venv activated)
USE_SQLITE=true ENABLE_EXTENDED_ROUTERS=true python -m pytest backend/tests/ -v

# Frontend tests
cd dashboard && npm test
```

## Project Structure

```
orchestly/
├── backend/               # FastAPI + SQLAlchemy async
│   ├── api/               # REST API routes & middleware
│   │   ├── routes/        # Endpoint handlers (agents, workflows, etc.)
│   │   └── main.py        # App entry point
│   ├── shared/            # Business logic & services
│   ├── database/          # Models, migrations, session management
│   └── tests/             # pytest test suite (1,100+ tests)
├── dashboard/             # React + Vite + TypeScript frontend
│   ├── src/
│   │   ├── pages/         # Page components
│   │   ├── components/    # Reusable UI components
│   │   └── services/      # API client
│   └── package.json
├── ee/                    # Enterprise features (separate license)
├── examples/              # Ready-to-run example workflows
├── docs/                  # Architecture & API documentation
├── scripts/               # Dev and deployment scripts
├── docker-compose.yml     # One-command deployment
└── helm/                  # Kubernetes Helm charts
```

## Finding Work

New to the project? Here are good ways to get started:

- Browse issues labeled [`good-first-issue`](https://github.com/orchestly-ai/platform/labels/good-first-issue) for beginner-friendly tasks
- Join the [Discord](https://discord.gg/orchestly) **#contributing** channel to ask questions
- Check [GitHub Discussions](https://github.com/orchestly-ai/platform/discussions) for open design discussions you can weigh in on
- Look at the [ROADMAP.md](ROADMAP.md) for upcoming features where help is welcome

## Pull Request Guidelines

1. **Fork** the repository and create a feature branch from `main`.
2. **Write tests** for new functionality.
3. **Follow existing code style** — the project uses:
   - Python: standard library conventions, type hints
   - TypeScript: strict mode, functional React components
4. **Keep PRs focused** — one feature or fix per PR.
5. **Write clear commit messages** describing what and why.
6. **Update documentation** if your change affects public APIs or user-facing behavior.

## Code of Conduct

We follow the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). Be respectful, inclusive, and constructive.

## Reporting Issues

- **Bugs**: Open an issue with steps to reproduce, expected vs actual behavior, and environment details.
- **Feature requests**: Open an issue describing the use case and proposed solution.
- **Security vulnerabilities**: See [SECURITY.md](SECURITY.md) — do NOT open a public issue.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

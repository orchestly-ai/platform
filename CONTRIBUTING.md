# Contributing to Orchestly

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run the server
uvicorn backend.api.main:app --reload
```

### Frontend

```bash
cd dashboard
npm install
npm run dev
```

### Running Tests

```bash
# Backend tests
python -m pytest backend/tests/ -v

# Frontend tests
cd dashboard && npm test
```

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

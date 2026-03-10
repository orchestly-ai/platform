# Security Documentation

This directory contains security documentation for the Agent Orchestration Platform.

## Contents

- **SECURITY_AUDIT.md** - Comprehensive security audit report with findings and recommendations

## Key Security Features

### Authentication
- API Key authentication for agents
- JWT authentication for dashboard users
- Password hashing with bcrypt

### Authorization
- Role-Based Access Control (RBAC)
- Permission-based access
- Multi-tenancy isolation

### Data Protection
- SQL injection prevention via SQLAlchemy ORM
- Input validation with Pydantic
- Audit logging for compliance

### Rate Limiting
- Token bucket algorithm
- Tiered limits by subscription

## Security Testing

Run security tests:
```bash
pytest backend/tests/security/ -v
```

## Reporting Security Issues

Please report security vulnerabilities to security@example.com.

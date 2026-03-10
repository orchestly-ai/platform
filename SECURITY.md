# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Orchestly, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email **security@orchestly.ai** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within 48 hours and provide a timeline for a fix.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | Yes       |

## Security Best Practices

When deploying Orchestly:

- Change the default `JWT_SECRET` in production
- Use PostgreSQL (not SQLite) for production deployments
- Enable HTTPS for all API traffic
- Rotate API keys regularly
- Review and restrict RBAC permissions to least-privilege
- Keep dependencies up to date

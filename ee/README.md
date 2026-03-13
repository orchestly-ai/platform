# Orchestly Enterprise Edition

This directory contains Enterprise Edition features that require a valid license for production use.

## Enterprise Features

| Feature | Description |
|---------|-------------|
| SSO/SAML/OIDC | Enterprise single sign-on with JIT provisioning |
| HIPAA Compliance | Healthcare compliance controls and BAA support |
| Advanced Audit | Audit export, retention policies, compliance reports |
| BYOC | Bring Your Own Compute — customer VPC workers |
| Multi-Cloud Deployment | Deploy across AWS, GCP, Azure |
| White-Label & Partners | Rebrand and resell Orchestly |
| A/B Testing | Statistical significance testing for LLM experiments |
| Time-Travel Debugging | Replay and compare agent executions |
| Advanced Supervisor | Group chat, task decomposition orchestration modes |
| ML Auto-Optimization | ML-based routing and performance optimization |
| Cost Forecasting | Anomaly detection and spend forecasting |
| Advanced HITL | Escalation chains, approval templates |
| Custom RBAC | Custom roles and fine-grained permissions |
| Advanced Analytics | BI-level reporting and dashboards |
| Security Scanning | Advanced prompt injection and vulnerability scanning |
| Marketplace Publishing | Publish and sell agents on the marketplace |

## Activation

Set the `ORCHESTLY_LICENSE_KEY` environment variable:

```bash
export ORCHESTLY_LICENSE_KEY=orch_ent_your_license_key_here
```

Then start the server normally. Enterprise routers will be loaded automatically.

## License

See [LICENSE](LICENSE) in this directory. Enterprise Edition features are free to evaluate but require a license for production use.

# Roadmap

> Last updated: March 2026

## Now (Current)

The core platform is live and production-ready:

- **Workflow Designer** - Visual DAG-based workflow builder with conditional branching, parallel execution, and human-in-the-loop approvals
- **Multi-LLM Routing** - Intelligent routing across 7+ providers (OpenAI, Anthropic, Google, DeepSeek, and more) with automatic fallback, cost optimization, and rate limit management
- **Integrations** - Hybrid OAuth system supporting both platform-managed and customer-managed credentials, unified webhook processing with provider-specific signature verification
- **Human-in-the-Loop** - Approval gates, manual review steps, and escalation workflows
- **Analytics & Cost Tracking** - Per-organization token ledger, usage dashboards, and real-time cost monitoring
- **Dashboard** - React-based management UI for workflows, agents, integrations, and monitoring

## Next (Q2 2026)

Scaling and enterprise deployment:

- **Multi-Region Deployment** - EU-West-1 (GDPR), AP-South-1 regions with geo-routing and cross-region replication
- **Auto-Scaling** - Horizontal pod auto-scaling with burst handling
- **Hybrid Cloud** - Agent runtime deployed in customer VPCs via VPC peering / PrivateLink, with control plane managed by Orchestly
- **Helm Charts** - Production-grade Helm chart for customer-managed Kubernetes deployments

## Later (Q3 2026)

Self-hosted and air-gapped support:

- **Self-Hosted / Air-Gapped** - Full platform deployable on-premise via Helm chart, no external dependencies required
- **Local LLM Support** - Integration with vLLM, Ollama, and Azure OpenAI private endpoints for air-gapped environments
- **SSO / SAML** - Enterprise single sign-on with SCIM provisioning

---

Have a feature request? [Open an issue](https://github.com/orchestly-ai/platform/issues) or start a [discussion](https://github.com/orchestly-ai/platform/discussions).

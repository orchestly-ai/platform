# MCP Architecture Guidelines

## ✅ Correct Directory Structure

Each service should contain its own MCP server wrapper in its directory:

```
orchestly/
├── backend/                         # Orchestration platform backend
│   ├── api/mcp.py                  # MCP client endpoints
│   └── shared/mcp_service.py       # MCP client implementation
├── mcp_calculator_server.py        # Example/demo MCP server
└── mcp_service_wrapper_template.py # Template for teams
│
└── services/
    ├── fintech/
    │   ├── expense-service/
    │   │   ├── backend/                 # Expense service backend
    │   │   └── mcp_server.py           # ✅ Expense MCP server (belongs here)
    │   │
    │   └── property-service/
    │       ├── backend/                 # Property service backend
    │       └── mcp_property_server.py  # ✅ Property MCP server (belongs here)
    │
    ├── legal-tech/
    │   └── contract-service/
    │       ├── backend/                 # Legal service backend
    │       └── mcp_legal_server.py     # ✅ Legal MCP server (belongs here)
    │
    ├── healthcare/
    │   └── backend/
    │       └── mcp_server.py           # ✅ Healthcare MCP server (belongs here)
    │
    ├── hr-tech/
    │   └── recruiting-service/
    │       └── mcp_server.py           # ✅ Recruiting MCP server (belongs here)
    │
    └── supply-chain/
        └── logistics-service/
            └── mcp_server.py           # ✅ Logistics MCP server (belongs here)
```

## 🎯 Key Principle: Service Ownership

**Each service owns its MCP server wrapper** because:

1. **Domain Expertise**: The service team knows their APIs best
2. **Version Control**: MCP server versions with the service
3. **Deployment**: MCP server deploys with the service
4. **Maintenance**: Service team maintains their MCP wrapper
5. **Testing**: MCP tests are part of service test suite

## 📁 What Goes Where?

### In `platform/agent-orchestration/`:
- ✅ **MCP Client code** (orchestrator that discovers/uses tools)
- ✅ **MCP templates** (for teams to use)
- ✅ **Example MCP servers** (calculator, simple demos)
- ✅ **MCP documentation** (architecture, guidelines)
- ❌ **Production service MCP servers** (these go with services)

### In `services/*/`:
- ✅ **Service-specific MCP servers** (exposes that service's APIs)
- ✅ **MCP configuration** (ports, endpoints, tool definitions)
- ✅ **MCP tests** (testing that service's tools)
- ✅ **Service-specific documentation** (how to use that MCP server)

## 🚀 How to Add MCP to Your Service

### Step 1: Copy the template to your service
```bash
cd services/your-service/
cp ../../platform/agent-orchestration/mcp_service_wrapper_template.py mcp_server.py
```

### Step 2: Customize for your service
```python
# In your service's mcp_server.py
YOUR_SERVICE_NAME = "your-service"
YOUR_SERVICE_URL = "http://localhost:9001"  # Your actual service
MCP_PORT = 8010  # Unique port for this MCP server
```

### Step 3: Add to your service's Docker/deployment
```yaml
# docker-compose.yml
services:
  your-service:
    build: .
    ports:
      - "9001:9001"

  your-service-mcp:
    build: .
    command: python mcp_server.py
    ports:
      - "8010:8010"
    environment:
      - SERVICE_URL=http://your-service:9001
```

### Step 4: Register with orchestrator
```bash
curl -X POST http://localhost:8000/mcp/servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Your Service",
    "endpoint_url": "http://localhost:8010/mcp/your_service",
    "transport_type": "http"
  }'
```

## 📊 Port Allocation Strategy

Reserve port ranges for different service categories:

| Service Category | Port Range | Example |
|-----------------|------------|---------|
| Demo/Examples | 8001-8009 | Calculator (8001) |
| Fintech | 8010-8019 | Expense (8010), Property (8011) |
| Legal | 8020-8029 | Contracts (8020) |
| Healthcare | 8030-8039 | Patient (8030) |
| HR Tech | 8040-8049 | Recruiting (8040) |
| Supply Chain | 8050-8059 | Logistics (8050) |
| Sales | 8060-8069 | SDR (8060) |
| Customer Support | 8070-8079 | Support (8070) |

## 🔄 Development Workflow

### Local Development
```bash
# Start your service
cd services/fintech/expense-service
npm run dev  # or python manage.py runserver

# Start your MCP server
python mcp_server.py

# Register with orchestrator
curl -X POST http://localhost:8000/mcp/servers ...
```

### CI/CD Pipeline
```yaml
# .github/workflows/deploy.yml
- name: Test Service
  run: pytest tests/

- name: Test MCP Server
  run: pytest tests/test_mcp_server.py

- name: Build Service + MCP
  run: docker build -t service:latest .

- name: Deploy Both
  run: |
    kubectl apply -f k8s/service.yaml
    kubectl apply -f k8s/mcp-server.yaml
```

## 🏗️ Migration Plan

For the files we just created:

1. **Move** `mcp_property_server.py` → `services/fintech/property-service/`
2. **Move** `mcp_legal_server.py` → `services/legal-tech/contract-service/`
3. **Keep** `mcp_calculator_server.py` in agent-orchestration (it's a demo)
4. **Keep** `mcp_service_wrapper_template.py` in agent-orchestration (it's a template)

## 📝 Service Team Responsibilities

Each service team should:

1. **Create** their MCP server using the template
2. **Define** tools that make sense for their domain
3. **Document** their tools clearly (descriptions, schemas)
4. **Test** their MCP server with the orchestrator
5. **Monitor** tool usage and performance
6. **Version** their MCP API appropriately

## 🎯 Benefits of This Architecture

1. **Decentralized Ownership**: Each team owns their MCP interface
2. **Independent Deployment**: Services and their MCPs deploy together
3. **Clear Boundaries**: Service logic stays with the service
4. **Easier Maintenance**: Teams maintain what they know best
5. **Better Scaling**: Each MCP server scales with its service

## Example: Complete Service Structure

```
services/fintech/expense-service/
├── backend/
│   ├── api/                    # Service API
│   ├── models/                 # Data models
│   └── services/               # Business logic
├── frontend/                   # UI (if applicable)
├── tests/
│   ├── test_api.py            # Service tests
│   └── test_mcp_server.py     # MCP server tests
├── mcp_server.py              # MCP wrapper for this service
├── docker-compose.yml         # Includes both service and MCP
├── requirements.txt           # Dependencies
└── README.md                  # Documentation

# The MCP server runs alongside the service:
# - Expense Service API: port 9001
# - Expense MCP Server: port 8010
```

This architecture ensures that **MCP servers are co-located with the services they wrap**, making the system more maintainable and scalable!
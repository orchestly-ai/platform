# Testing Guide: Shared State Manager, Webhook & HITL Features

## Overview

This guide covers testing for the newly implemented features:
- **Shared State Manager**: Cross-node context passing
- **Webhook Nodes**: Event-driven workflow triggers
- **HITL Nodes**: Human-in-the-loop approval steps
- **Variable Substitution**: `{{node_id.field}}` syntax

---

## Quick Start

### 1. Run Unit Tests

```bash
# Test Shared State Manager
cd .
python -m pytest backend/tests/test_shared_state_manager.py -v

# Run all tests
python -m pytest backend/tests/ -v
```

### 2. Run Demo Script

```bash
# Comprehensive demo of all features
python backend/demos/demo_shared_state_and_workflows.py
```

### 3. Test in Dashboard UI

```bash
# Start backend
cd backend
uvicorn main:app --reload --port 8000

# Start dashboard
cd dashboard
npm run dev
```

---

## Unit Testing

### Shared State Manager Tests

Located in: `backend/tests/test_shared_state_manager.py`

**Test Categories:**
- ✅ Basic storage and retrieval
- ✅ Scope isolation (workflow, agent, global, session)
- ✅ Bulk operations (get_all, clear, keys)
- ✅ State snapshots and restore
- ✅ Complex data types (dicts, lists, nested objects)
- ✅ Metadata tracking
- ✅ Workflow integration scenarios
- ✅ Edge cases (empty values, large data)

**Run specific test class:**
```bash
pytest backend/tests/test_shared_state_manager.py::TestStateStorage -v
pytest backend/tests/test_shared_state_manager.py::TestStateScoping -v
pytest backend/tests/test_shared_state_manager.py::TestWorkflowIntegration -v
```

**Run with coverage:**
```bash
pytest backend/tests/test_shared_state_manager.py --cov=backend.shared.shared_state_manager --cov-report=html
```

---

## Integration Testing

### Manual Workflow Testing

#### Test Case 1: Variable Substitution in Tool Nodes

**Goal:** Test that Tool nodes can reference outputs from previous nodes

1. **Create Workflow:**
   ```json
   {
     "nodes": [
       {
         "id": "user_input",
         "type": "supervisor",
         "data": {
           "label": "Get User ID",
           "llmModel": "gpt-4o-mini",
           "systemPrompt": "Extract user ID from input",
           "prompt": "User ID is: user_123"
         }
       },
       {
         "id": "api_call",
         "type": "tool",
         "data": {
           "label": "Fetch User Data",
           "toolConfig": {
             "url": "https://api.example.com/users/{{user_input.content}}",
             "method": "GET"
           }
         }
       }
     ],
     "edges": [
       {"source": "user_input", "target": "api_call"}
     ]
   }
   ```

2. **Execute Workflow**

3. **Verify:**
   - Node `user_input` output is stored in state
   - Node `api_call` URL contains substituted value: `https://api.example.com/users/user_123`
   - Check browser console for logs

#### Test Case 2: Webhook Node Configuration

**Goal:** Test webhook node properties panel and configuration

1. **In WorkflowDesigner:**
   - Drag "Webhook Listener" node from palette
   - Select the node
   - Properties panel should show:
     - HTTP Method dropdown (POST, GET, PUT, PATCH, DELETE)
     - Authentication Type dropdown
     - Conditional auth fields based on type
     - Response Status Code input

2. **Test Auth Types:**
   - **None:** No additional fields
   - **Basic:** Shows Username + Password fields
   - **Bearer:** Shows Token field
   - **API Key:** Shows Key Name + Key Value fields

3. **Save and Execute:**
   - Configure webhook
   - Save workflow
   - Execute workflow
   - Check execution logs for webhook URL

#### Test Case 3: HITL Approval Node

**Goal:** Test human approval workflow

1. **In WorkflowDesigner:**
   - Drag "Human Approval" node from palette
   - Select the node
   - Properties panel should show:
     - Approval Type: Any / All
     - Timeout (minutes)
     - Timeout Action: Reject / Approve
     - Notification Channels checkboxes
     - Approvers textarea (one email per line)

2. **Configure:**
   ```
   Approval Type: Any
   Timeout: 5 minutes
   Timeout Action: Reject
   Notify Via: Email, Slack
   Approvers:
   manager@company.com
   supervisor@company.com
   ```

3. **Execute Workflow:**
   - Run workflow with HITL node
   - Observe execution pauses at HITL node
   - Check for approval request event
   - Currently auto-approves after 2s (demo mode)

#### Test Case 4: Complete Multi-Node Workflow

**Goal:** Test state passing across multiple nodes

```json
{
  "name": "Customer Support Workflow",
  "nodes": [
    {
      "id": "webhook_trigger",
      "type": "webhook",
      "data": {
        "label": "Support Ticket Webhook",
        "webhookConfig": {
          "method": "POST",
          "authentication": {"type": "api-key"},
          "responseStatus": 200
        }
      }
    },
    {
      "id": "classify_intent",
      "type": "supervisor",
      "data": {
        "label": "Classify Ticket",
        "llmModel": "gpt-4o-mini",
        "prompt": "Classify: {{webhook_trigger.data.message}}"
      }
    },
    {
      "id": "approval_required",
      "type": "hitl",
      "data": {
        "label": "Manager Approval",
        "hitlConfig": {
          "approvalType": "any",
          "timeout": 60,
          "approvers": ["manager@example.com"]
        }
      }
    },
    {
      "id": "create_ticket",
      "type": "tool",
      "data": {
        "label": "Create Zendesk Ticket",
        "toolConfig": {
          "url": "https://api.zendesk.com/tickets",
          "method": "POST",
          "body": "{\"subject\": \"{{classify_intent.content}}\", \"description\": \"{{webhook_trigger.data.message}}\"}"
        }
      }
    }
  ],
  "edges": [
    {"source": "webhook_trigger", "target": "classify_intent"},
    {"source": "classify_intent", "target": "approval_required"},
    {"source": "approval_required", "target": "create_ticket"}
  ]
}
```

**Expected Flow:**
1. Webhook receives data → stored in state
2. LLM classifies → output stored in state
3. HITL approval → waits for approval
4. Tool node → uses `{{classify_intent.content}}` and `{{webhook_trigger.data.message}}`

---

## Testing with Demo Script

### Run All Demos

```bash
python backend/demos/demo_shared_state_and_workflows.py
```

**What it demonstrates:**
1. ✅ Basic state operations (set, get, delete)
2. ✅ Scope isolation between workflows/agents
3. ✅ Node output storage pattern
4. ✅ Variable substitution simulation
5. ✅ State snapshots for time-travel debugging
6. ✅ Webhook and HITL configuration examples

### Expected Output

```
╔══════════════════════════════════════════════════════════════════════════════╗
║               SHARED STATE MANAGER & WORKFLOW DEMO                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

================================================================================
DEMO 1: Basic State Operations
================================================================================

1. Setting workflow state...
   ✓ Stored user_input
   ✓ Stored processing_status

2. Retrieving values...
   user_input = {
     "message": "Hello World",
     "user_id": "user_123"
   }
   processing_status = in_progress

3. Getting all workflow state...
   Found 2 entries:
     - user_input: {'message': 'Hello World', 'user_id': 'user_123'}
     - processing_status: in_progress

4. Clearing workflow state...
   ✓ Cleared 2 entries

[... more demos ...]

================================================================================
✓ All demos completed successfully!
================================================================================
```

---

## Testing State Persistence with Redis

### Setup Redis (Optional)

```bash
# Install Redis
sudo apt-get install redis-server  # Ubuntu
brew install redis                  # macOS

# Start Redis
redis-server

# Verify
redis-cli ping  # Should return PONG
```

### Test with Redis Backend

```python
import redis.asyncio as redis
from backend.shared.shared_state_manager import SharedStateManager, StateScope

async def test_with_redis():
    # Connect to Redis
    redis_client = await redis.from_url("redis://localhost:6379")

    # Create state manager with Redis
    state = SharedStateManager(redis_client=redis_client)

    # Set value
    await state.set("test", "value", StateScope.WORKFLOW, "wf_001")

    # Verify in Redis CLI
    # redis-cli
    # > KEYS state:*
    # > GET state:workflow:wf_001:test

    # Cleanup
    await redis_client.close()
```

---

## Browser-Based Testing

### 1. Open WorkflowDesigner

```
http://localhost:3000/workflows/designer
```

### 2. Test Webhook Node

1. Drag "Webhook Listener" to canvas
2. Click node → Properties panel appears
3. Select HTTP Method: **POST**
4. Select Auth Type: **Bearer Token**
5. Enter Token: `test_bearer_token_123`
6. Set Response Status: **201**
7. Save workflow
8. Execute workflow
9. Open browser console → Check for:
   ```
   Webhook node ready: POST /api/webhooks/node_xxx (auth: bearer, status: 201)
   ```

### 3. Test HITL Node

1. Drag "Human Approval" to canvas
2. Click node → Properties panel appears
3. Set Approval Type: **All Approvers**
4. Set Timeout: **30** minutes
5. Set Timeout Action: **Approve**
6. Check notification channels: **Email**, **Slack**
7. Enter approvers:
   ```
   alice@company.com
   bob@company.com
   ```
8. Save and execute
9. Check WebSocket messages for approval events:
   - `hitl_approval_requested`
   - `hitl_approval_completed`

### 4. Test Variable Substitution

1. Create workflow with 2 nodes:
   - Node A: LLM Supervisor (outputs text)
   - Node B: HTTP Tool
2. In Node B's URL field, enter:
   ```
   https://api.example.com/process?text={{nodeA.content}}
   ```
3. Execute workflow
4. Check network tab → API call should have substituted value

---

## Troubleshooting

### State Not Persisting Between Nodes

**Check:**
1. Is `workflow_id` being passed to `_execute_node`?
2. Are node outputs being stored in state? (Check logs for "Stored output for node...")
3. Is variable substitution being called? (Check for "Variable {{...}} not found" warnings)

**Debug:**
```python
# Add to workflow executor
logger.debug(f"Workflow state: {await self.state_manager.get_all(StateScope.WORKFLOW, str(workflow_id))}")
```

### Webhook Properties Not Showing

**Check:**
1. Is `WebhookNode` component imported in WorkflowDesigner?
2. Is node type `'webhook'` in `nodeTypes` mapping?
3. Is conditional `{selectedNode.data.type === 'webhook' && ...}` correct?

**Verify:**
```javascript
// In browser console
console.log(nodeTypes);  // Should include 'webhook'
console.log(selectedNode);  // Check data structure
```

### HITL Not Pausing Execution

**Note:** Currently auto-approves in demo mode (2s delay)

**For production:**
1. Implement approval API endpoint
2. Store approval requests in database
3. Send notifications via email/Slack
4. Wait for actual approval response
5. Handle timeout logic

---

## Performance Testing

### Test State Manager Under Load

```python
import asyncio
import time
from backend.shared.shared_state_manager import SharedStateManager, StateScope

async def load_test():
    state = SharedStateManager()
    workflow_id = "load_test_001"

    # Write 1000 entries
    start = time.time()
    for i in range(1000):
        await state.set(f"key_{i}", f"value_{i}", StateScope.WORKFLOW, workflow_id)
    write_time = time.time() - start

    # Read 1000 entries
    start = time.time()
    for i in range(1000):
        await state.get(f"key_{i}", StateScope.WORKFLOW, workflow_id)
    read_time = time.time() - start

    print(f"Write 1000 entries: {write_time:.2f}s ({1000/write_time:.0f} ops/sec)")
    print(f"Read 1000 entries:  {read_time:.2f}s ({1000/read_time:.0f} ops/sec)")

    # Cleanup
    await state.clear(StateScope.WORKFLOW, workflow_id)

asyncio.run(load_test())
```

---

## Continuous Integration

### Add to CI Pipeline

```yaml
# .github/workflows/test.yml
name: Test Shared State Manager

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: |
          pytest backend/tests/test_shared_state_manager.py -v --cov

      - name: Run demo
        run: |
          python backend/demos/demo_shared_state_and_workflows.py
```

---

## Next Steps

1. **Write more tests** for edge cases
2. **Add Redis integration tests** with real Redis instance
3. **Create UI tests** with Playwright/Cypress
4. **Performance benchmarks** for large workflows
5. **Load testing** for concurrent executions
6. **Documentation** for production deployment

---

## Resources

- **Source Code:**
  - `backend/shared/shared_state_manager.py`
  - `backend/services/workflow_executor.py`
  - `dashboard/src/pages/WorkflowDesigner.tsx`

- **Tests:**
  - `backend/tests/test_shared_state_manager.py`

- **Demos:**
  - `backend/demos/demo_shared_state_and_workflows.py`

- **Related:**
  - `backend/shared/state_lock_service.py` (Distributed locking)
  - `ROADMAP.md` (Feature roadmap)

---

**Questions or Issues?**

Open an issue on GitHub or check the ROADMAP.md for planned features.

# Simple UI Testing Guide - 5 Minutes

Quick visual tests for all new features in the WorkflowDesigner.

## Setup (30 seconds)

```bash
# Terminal 1: Start backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2: Start frontend
cd dashboard
npm run dev
```

Open: http://localhost:3000/workflows/designer

---

## Test 1: Variable Substitution (Cross-Node Data Passing)

**Time: 2 minutes**

### Step 1: Build the Workflow

1. **Add Node A (Input)**
   - Drag "Supervisor Agent" to canvas
   - Click it → Properties panel opens
   - Set Label: `User Input`
   - Set Prompt: `Extract user ID: user_12345`
   - Leave other defaults

2. **Add Node B (API Call)**
   - Drag "Tool/API Call" to canvas
   - Click it → Properties panel
   - Set Label: `Fetch User`
   - Set URL: `https://jsonplaceholder.typicode.com/users/1`
   - Set Method: `GET`

3. **Connect them**
   - Drag from User Input → Fetch User

### Step 2: Test It

1. Click **"Execute Workflow"** button
2. Watch the execution in real-time
3. **What to look for:**
   - ✅ Both nodes turn green
   - ✅ Node outputs stored in state
   - ✅ Check browser console for: `"Stored output for node..."`

**Expected Console Output:**
```
Stored output for node user_input_1 in workflow state
Stored output for node fetch_user_2 in workflow state
```

---

## Test 2: Webhook Node Configuration

**Time: 1 minute**

### Build Simple Webhook

1. **Add Webhook Node**
   - Drag "Webhook Listener" to canvas
   - Click it → Properties panel appears

2. **Configure It**
   - HTTP Method: **POST**
   - Authentication Type: **Bearer Token**
   - Bearer Token: `my_secret_token_123`
   - Response Status Code: **201**

3. **Save Workflow**

### Verify

**What to look for in Properties Panel:**
- ✅ Method dropdown shows all options (POST, GET, PUT, PATCH, DELETE)
- ✅ Auth dropdown changes fields dynamically
- ✅ When "Bearer Token" selected → Token field appears
- ✅ When "API Key" selected → Key Name + Key Value fields appear
- ✅ When "Basic" selected → Username + Password fields appear

**Expected Behavior:**
- Properties panel renders without errors
- Fields update when auth type changes
- Values are saved in workflow definition

---

## Test 3: HITL (Human Approval) Node

**Time: 1 minute**

### Build Approval Workflow

1. **Add HITL Node**
   - Drag "Human Approval" to canvas
   - Click it → Properties panel

2. **Configure It**
   - Approval Type: **Any**
   - Timeout: **5** minutes
   - Timeout Action: **Reject**
   - Check: **Email** and **Slack**
   - Approvers (one per line):
     ```
     manager@company.com
     supervisor@company.com
     ```

3. **Execute Workflow**
   - Click Execute
   - Watch it pause at HITL node
   - After 2 seconds, auto-approves (demo mode)

### Verify

**What to look for:**
- ✅ Properties panel shows all fields
- ✅ Notification channel checkboxes work
- ✅ Approvers textarea accepts multiple emails
- ✅ During execution: Node shows "running" state
- ✅ WebSocket events: `hitl_approval_requested` → `hitl_approval_completed`

**Expected Console Output:**
```
HITL node requesting approval: type=any, approvers=2, timeout=5min
HITL node approved (2000ms)
```

---

## Test 4: Complete Multi-Node Workflow (All Features)

**Time: 2 minutes**

### Build E2E Workflow

Create this 4-node workflow:

```
[Webhook] → [LLM Classifier] → [HITL Approval] → [API Call]
```

**Node 1: Webhook Trigger**
- Type: Webhook Listener
- Method: POST
- Auth: None
- Status: 200

**Node 2: LLM Classifier**
- Type: Supervisor Agent
- Label: `Classify Request`
- Model: `gpt-4o-mini`
- Prompt: `Classify this ticket: High Priority`

**Node 3: HITL Approval**
- Type: Human Approval
- Approval: Any
- Timeout: 5 min
- Approvers: `admin@company.com`

**Node 4: API Call**
- Type: Tool/API
- Label: `Create Ticket`
- URL: `https://jsonplaceholder.typicode.com/posts`
- Method: POST
- Body:
  ```json
  {
    "title": "Support Request",
    "body": "Classified as high priority",
    "userId": 1
  }
  ```

### Execute and Watch

1. Click **Execute Workflow**
2. **Watch the flow:**
   - ✅ Webhook: Instant (green)
   - ✅ LLM: 1-2 seconds (shows running → green)
   - ✅ HITL: Pauses 2 seconds → auto-approves
   - ✅ API: Makes real HTTP call → green

### What to Look For

**State Management:**
- Open browser DevTools → Console
- Look for: `"Stored output for node webhook_1"`
- Look for: `"Stored output for node classifier_2"`
- Look for: `"Cleared 4 workflow state entries"`

**Execution Events:**
- `execution_started`
- `node_status_changed` (4 times)
- `hitl_approval_requested`
- `hitl_approval_completed`
- `execution_completed`

---

## Test 5: Variable Substitution with Real Data

**Time: 2 minutes**

### Advanced: Reference Previous Nodes

**Node 1: Extract Data**
- Type: Supervisor
- Prompt: `Extract: {"user_id": "12345", "action": "delete"}`

**Node 2: Use the Data**
- Type: Tool/API
- URL: `https://jsonplaceholder.typicode.com/users/{{node_1.user_id}}`
  ⬆️ This will be replaced with "12345"

### How to Test

1. Build the 2-node workflow above
2. Execute it
3. Check console for variable substitution:
   ```
   Variable {{ node_1.user_id }} → 12345
   ```

**Note:** Variable substitution currently works for Tool nodes. The URL will have `{{node_1.user_id}}` replaced with actual data from Node 1's output.

---

## Quick Verification Checklist

Run through this 5-minute checklist:

### ✅ Shared State Manager
- [ ] Create 2-node workflow
- [ ] Execute it
- [ ] Console shows: `"Stored output for node..."`
- [ ] Console shows: `"Cleared X workflow state entries"`

### ✅ Webhook Node
- [ ] Drag Webhook node to canvas
- [ ] Properties panel appears
- [ ] Change auth type → fields update
- [ ] All auth types work (None, Basic, Bearer, API Key)

### ✅ HITL Node
- [ ] Drag HITL node to canvas
- [ ] Properties panel appears
- [ ] Configure approval settings
- [ ] Execute → node pauses → auto-approves

### ✅ Variable Substitution
- [ ] Add Tool node with URL: `https://api.example.com/{{prev_node.field}}`
- [ ] Execute workflow
- [ ] Console shows variable replacement (or warning if not found)

---

## Common Issues & Fixes

### Issue: "Properties panel doesn't show"
**Fix:** Make sure you clicked the node (it should have blue border)

### Issue: "Variables not substituting"
**Fix:**
- Check node_id matches exactly (case-sensitive)
- Check previous node actually stored output
- Look for warning: `"Variable {{ ... }} not found in state"`

### Issue: "Webhook/HITL properties blank"
**Fix:**
- Refresh page
- Check console for JS errors
- Verify node type is exactly "webhook" or "hitl"

### Issue: "Execution stuck"
**Fix:**
- Check backend terminal for errors
- Ensure WebSocket connection is open
- Try refreshing page and re-executing

---

## Visual Confirmation Guide

### Working Shared State Manager
```
Console Output:
✓ Stored output for node node_1 in workflow state
✓ Stored output for node node_2 in workflow state
✓ Cleared 2 workflow state entries for wf_xxx
```

### Working Webhook Node
```
Properties Panel Shows:
┌─────────────────────────────┐
│ HTTP Method         [POST ▼]│
│ Authentication Type [None ▼]│
│ Response Status     [200  ] │
└─────────────────────────────┘
```

### Working HITL Node
```
Properties Panel Shows:
┌────────────────────────────────┐
│ Approval Type    [Any      ▼] │
│ Timeout (min)    [60        ] │
│ Timeout Action   [Reject   ▼] │
│ ☑ Email  ☑ Slack  ☐ Teams    │
│ Approvers:                    │
│ ┌──────────────────────────┐  │
│ │admin@company.com        │  │
│ └──────────────────────────┘  │
└────────────────────────────────┘
```

### Working Variable Substitution
```
Before Execution:
URL: https://api.example.com/{{user_node.id}}

After Execution (in console):
Variable {{ user_node.id }} → user_12345
Final URL: https://api.example.com/user_12345
```

---

## Success Criteria

You've successfully tested everything if:

1. ✅ Can build multi-node workflows
2. ✅ Nodes execute in sequence
3. ✅ Webhook properties panel works
4. ✅ HITL properties panel works
5. ✅ Console shows state operations
6. ✅ Workflow completes without errors

**Total Testing Time: ~5 minutes**

---

## Next: Advanced Testing

For production testing:
- See `docs/TESTING_GUIDE.md` for comprehensive tests
- Run `pytest backend/tests/test_shared_state_manager.py`
- Run `python backend/demos/demo_shared_state_and_workflows.py`

---

**Need Help?**

Check browser console (F12) and backend logs for detailed error messages.

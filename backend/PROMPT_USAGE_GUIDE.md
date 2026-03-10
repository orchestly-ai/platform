# Prompt Registry - Usage Guide

## Where Prompts are Used

The Prompt Registry serves as a centralized prompt management system. Here's where and how prompts can be integrated:

## Visual Workflow Builder Integration

### Using Prompts in the Visual Builder

The workflow designer now has built-in support for Prompt Registry integration. When you add a **Worker Agent** or **Supervisor Agent** node, you can configure its prompt in two ways:

#### Method 1: Select from Registry (Recommended)
1. Click on a Worker or Supervisor node in the workflow canvas
2. In the right sidebar under "Prompt Configuration"
3. Click the **"From Registry"** tab
4. Click **"Select from Prompt Registry"**
5. Browse and search available prompts
6. Click on a prompt template to select it
7. Choose the version (defaults to latest published)
8. Map variables to workflow data using the variable picker

**Visual Indicators:**
- Nodes using registry prompts show a green 📄 icon with the prompt slug
- Version number is displayed (e.g., "customer-support v1.2.0")

#### Method 2: Manual Prompt Entry
1. Click on a Worker or Supervisor node
2. In the right sidebar under "Prompt Configuration"
3. Use the **"Manual Prompt"** tab
4. Type your prompt directly
5. Use `{{variable}}` syntax to insert dynamic values

### Example: Customer Support Workflow

```
1. Create nodes:
   [Trigger] → [Classifier Agent] → [Support Agent] → [Response Formatter]

2. Configure Classifier Agent:
   - Click the node
   - Select "From Registry" tab
   - Choose "customer-query-classifier" prompt
   - Version: "1.0.0"
   - Map variables:
     • {{query}} → {{trigger.user_input}}
     • {{context}} → {{trigger.metadata}}

3. Configure Support Agent:
   - Click the node
   - Select "From Registry" tab
   - Choose "customer-support-agent" prompt
   - Version: "2.1.0"
   - Map variables:
     • {{customer_name}} → {{trigger.customer.name}}
     • {{issue_type}} → {{classifier.category}}
     • {{query}} → {{trigger.user_input}}
```

### Benefits of Using Registry in Visual Builder

✅ **No copy-paste** - Select prompts from a searchable library
✅ **Version control** - Choose specific versions, update workflows easily
✅ **Variable mapping** - Clear UI for mapping workflow data to prompt variables
✅ **Visual feedback** - See which prompts are being used in each node
✅ **Centralized updates** - Update prompt in registry, all workflows can use new version
✅ **Testing** - Test prompts in registry before using in workflows

### 1. **Agent Executions** (Primary Use Case)
When executing AI agents, prompts can be dynamically loaded from the registry:

```python
from backend.shared.prompt_service import PromptService

# In your agent execution logic
prompt_service = PromptService(db_session)

# Render a prompt with variables
result = await prompt_service.render_prompt(
    slug="customer-support-agent",
    variables={
        "customer_name": "John Doe",
        "issue_type": "billing",
        "context": conversation_history
    }
)

# Use the rendered prompt
agent_response = await llm_client.chat(
    messages=[{"role": "system", "content": result["rendered_content"]}],
    model=result["model_hint"] or "gpt-4o"
)

# Track usage for analytics
await prompt_service.track_usage(
    slug="customer-support-agent",
    version=result["version"],
    latency_ms=response_time,
    tokens=agent_response.usage.total_tokens,
    success=True
)
```

### 2. **Workflow Templates**
Integrate prompts into workflow definitions:

```python
workflow_config = {
    "steps": [
        {
            "type": "agent",
            "prompt_slug": "classification-agent",
            "prompt_version": "1.2.0",  # Or use latest published
            "variables": {
                "input_text": "{{workflow.input}}"
            }
        },
        {
            "type": "agent",
            "prompt_slug": "generation-agent",
            "variables": {
                "classification": "{{steps.0.output}}"
            }
        }
    ]
}
```

### 3. **API Endpoints**
Users can test prompts directly via the /api/prompts/{slug}/render endpoint:

```bash
curl -X POST http://localhost:8000/api/prompts/customer-support/render \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
      "customer_name": "Jane Smith",
      "issue": "password reset"
    }
  }'
```

### 4. **Dashboard Testing Panel**
The UI provides a built-in testing panel where users can:
- Select a prompt template
- Fill in variables
- See the rendered output
- Test different versions

### 5. **A/B Testing**
Compare prompt versions for performance:

```python
# Define A/B test variants
variants = [
    {"prompt_slug": "sales-email", "version": "1.0.0"},
    {"prompt_slug": "sales-email", "version": "2.0.0"}
]

# Route 50% traffic to each
for request in incoming_requests:
    variant = random.choice(variants)
    result = await prompt_service.render_prompt(
        slug=variant["prompt_slug"],
        version=variant["version"],
        variables=request.variables
    )
```

## Integration Examples

### Example 1: Customer Support Agent
```python
async def handle_support_ticket(ticket_id: str):
    ticket = await get_ticket(ticket_id)

    # Load prompt from registry
    prompt = await prompt_service.render_prompt(
        slug="customer-support-agent",
        variables={
            "customer_name": ticket.customer_name,
            "issue_description": ticket.description,
            "priority": ticket.priority,
            "history": ticket.conversation_history
        }
    )

    # Execute with LLM
    response = await llm.chat(prompt["rendered_content"])

    # Track usage
    await prompt_service.track_usage(
        slug="customer-support-agent",
        version=prompt["version"],
        latency_ms=response.latency,
        tokens=response.tokens,
        success=response.success
    )

    return response
```

### Example 2: Code Generation
```python
async def generate_code(spec: str):
    prompt = await prompt_service.render_prompt(
        slug="code-generator",
        variables={
            "language": "python",
            "specification": spec,
            "style_guide": "PEP 8"
        }
    )

    code = await llm.chat(
        prompt["rendered_content"],
        model=prompt["model_hint"]  # Use suggested model
    )

    return code
```

### Example 3: Multi-Step Workflow
```python
async def process_document(document: str):
    # Step 1: Classify document
    classification = await prompt_service.render_prompt(
        slug="document-classifier",
        variables={"document": document}
    )

    # Step 2: Extract entities (different prompt based on classification)
    if classification["result"] == "legal":
        extraction = await prompt_service.render_prompt(
            slug="legal-entity-extractor",
            variables={"document": document}
        )
    else:
        extraction = await prompt_service.render_prompt(
            slug="general-entity-extractor",
            variables={"document": document}
        )

    return extraction
```

## Best Practices

1. **Version Control**: Always use published versions in production
2. **Variable Naming**: Use clear, descriptive variable names
3. **Testing**: Test prompts in the UI before deploying
4. **Analytics**: Monitor usage stats to optimize prompts
5. **Model Hints**: Set model hints to guide users on optimal models
6. **Categories**: Organize prompts by category for easy discovery

## Roadmap Features

Future integrations planned:
- [ ] Auto-inject prompts in agent configurations
- [ ] Prompt version rollback in production
- [ ] Prompt performance comparisons
- [ ] Automated prompt optimization based on analytics
- [ ] Integration with evaluation frameworks
- [ ] Export prompts to LangChain/LlamaIndex format

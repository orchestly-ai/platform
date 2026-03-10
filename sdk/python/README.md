# Orchestly Python SDK

Python SDK for integrating agents with the [Orchestly](https://orchestly.ai) platform.

## Installation

```bash
pip install orchestly
```

## Quick Start

### 1. Simple Agent

```python
from orchestly import register_agent, task

@register_agent(
    name="email_classifier",
    capabilities=["email_classification"],
    cost_limit_daily=100.0
)
class EmailAgent:

    @task(timeout=30)
    async def email_classification(self, email: dict) -> dict:
        """Classify an email into a category."""
        return {
            "category": "support",
            "priority": "high",
            "confidence": 0.95
        }

# Run the agent
if __name__ == "__main__":
    import asyncio
    agent = EmailAgent()
    asyncio.run(agent.run_forever())
```

### 2. Agent with LLM Integration

```python
from orchestly import register_agent, task, LLMClient

@register_agent(
    name="content_summarizer",
    capabilities=["text_summarization"],
    llm_provider="openai",
    llm_model="gpt-4o-mini"
)
class SummarizerAgent:

    def __init__(self):
        self.llm = LLMClient(provider="openai", model="gpt-4o-mini")

    @task(timeout=60)
    async def text_summarization(self, data: dict) -> dict:
        """Summarize a long text."""
        summary = await self.llm.generate(
            prompt=f"Summarize this text in 3 sentences:\n\n{data['text']}",
            max_tokens=150
        )
        return {"summary": summary}
```

## CLI

```bash
orchestly serve              # Start the platform API server
orchestly init my-project    # Scaffold a new project
orchestly version            # Show version
```

## Configuration

### Environment Variables

```bash
# Required
export ORCHESTLY_API_URL=http://localhost:8000
export ORCHESTLY_API_KEY=your-api-key-here

# Optional - for LLM integration
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

## API Reference

### OrchestlyClient

```python
from orchestly import OrchestlyClient

async with OrchestlyClient(api_url="...", api_key="...") as client:
    agent_id = await client.register_agent(config)
    task = await client.get_next_task(capabilities=["capability1"])
    await client.submit_result(task_id=task["task_id"], output={"result": "done"})
```

### LLMClient

```python
from orchestly import LLMClient

async with LLMClient(provider="openai", model="gpt-4") as llm:
    result = await llm.generate(prompt="What is the capital of France?", max_tokens=50)
```

## Support

- Documentation: [https://github.com/orchestly-ai/orchestly](https://github.com/orchestly-ai/orchestly)
- Issues: [https://github.com/orchestly-ai/orchestly/issues](https://github.com/orchestly-ai/orchestly/issues)

## License

Apache 2.0 - See [LICENSE](../../LICENSE) for details.

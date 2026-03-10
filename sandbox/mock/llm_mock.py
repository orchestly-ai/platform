"""
Mock LLM Provider for Sandbox Environment

Provides realistic LLM responses without incurring actual API costs.
Simulates different providers, models, and response characteristics.
"""

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class MockLLMResponse:
    """Mock LLM response with realistic metadata."""
    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    latency_ms: int
    finish_reason: str = "stop"


# Cost per 1K tokens by provider/model
MOCK_PRICING = {
    "openai": {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    },
    "anthropic": {
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    },
    "google": {
        "gemini-pro": {"input": 0.00025, "output": 0.0005},
        "gemini-ultra": {"input": 0.0025, "output": 0.0075},
    },
}

# Realistic response templates by scenario
MOCK_RESPONSES = {
    # Customer Support Classification
    "classify_ticket": {
        "high_priority": {
            "content": """Based on my analysis of this customer ticket, I've classified it as follows:

**Priority:** HIGH
**Category:** Billing Issue - Refund Request
**Sentiment:** Frustrated/Urgent
**Confidence:** 0.94

**Key Signals:**
- Customer mentions "overcharged" indicating billing dispute
- Use of urgent language ("immediately", "need help now")
- Previous interaction history shows escalation pattern

**Recommended Actions:**
1. Escalate to billing team within 1 hour
2. Review last 3 transactions
3. Prepare refund options for discussion

**Suggested Response Template:** "I understand your frustration with the billing discrepancy..."
""",
            "tokens": {"prompt": 245, "completion": 187}
        },
        "medium_priority": {
            "content": """Classification complete:

**Priority:** MEDIUM
**Category:** Product Inquiry - Feature Request
**Sentiment:** Neutral/Curious
**Confidence:** 0.89

**Analysis:**
The customer is asking about features that exist in our premium tier. This is an upsell opportunity.

**Recommended Actions:**
1. Provide feature comparison
2. Offer trial of premium features
3. Schedule follow-up in 48 hours
""",
            "tokens": {"prompt": 198, "completion": 132}
        },
        "low_priority": {
            "content": """Classification Result:

**Priority:** LOW
**Category:** General Inquiry - Documentation
**Sentiment:** Neutral
**Confidence:** 0.92

The customer is asking a question that's covered in our FAQ section.

**Recommendation:** Send link to relevant documentation article.
""",
            "tokens": {"prompt": 156, "completion": 78}
        }
    },

    # Sales Lead Scoring
    "lead_qualification": {
        "hot_lead": {
            "content": """## Lead Qualification Analysis

**Lead Score:** 92/100 - HOT LEAD

**Company Profile:**
- Company Size: Enterprise (5000+ employees)
- Industry: Financial Services
- Tech Stack: AWS, Kubernetes, existing AI initiatives
- Annual IT Budget: Estimated $50M+

**Buying Signals:**
- Downloaded pricing PDF
- Attended 2 webinars in past month
- CEO mentioned "AI transformation" in recent interview
- Active RFP process for AI infrastructure

**Recommended Actions:**
1. Immediate outreach from AE
2. Schedule technical deep-dive
3. Prepare custom ROI analysis
4. Fast-track to POC stage

**Estimated Deal Size:** $250K-$500K ARR
**Probability:** 78%
""",
            "tokens": {"prompt": 312, "completion": 256}
        },
        "warm_lead": {
            "content": """## Lead Qualification Analysis

**Lead Score:** 65/100 - WARM LEAD

**Company Profile:**
- Company Size: Mid-Market (500-2000 employees)
- Industry: E-commerce
- Current Stage: Evaluating options

**Buying Signals:**
- Signed up for free trial
- Active usage last 2 weeks
- Asked pricing questions

**Recommended Actions:**
1. Nurture with case studies
2. Offer extended trial
3. Follow up in 2 weeks
""",
            "tokens": {"prompt": 267, "completion": 145}
        }
    },

    # Content Generation
    "content_generation": {
        "blog_post": {
            "content": """# The Future of AI Agent Orchestration: Why Enterprises Need a New Approach

As AI agents become increasingly sophisticated, enterprises face a critical challenge: how to deploy, manage, and scale these autonomous systems in production environments.

## The Problem

Traditional software deployment practices weren't designed for AI agents. Unlike conventional applications, agents:

- Make autonomous decisions that need monitoring
- Consume expensive LLM API calls that need cost control
- Require complex coordination for multi-agent workflows
- Generate unpredictable outputs that need guardrails

## The Solution: Agent Orchestration Platforms

Modern enterprises need purpose-built infrastructure for AI agents. Key capabilities include:

1. **Unified Observability** - Track every decision, every API call
2. **Cost Control** - Real-time budgets and spend limits
3. **Multi-Provider Routing** - Avoid vendor lock-in
4. **Time-Travel Debugging** - Debug agent behavior at any point

## Conclusion

The future belongs to organizations that can effectively orchestrate their AI agents at scale.

---
*Published by AgentOrch Team | 5 min read*
""",
            "tokens": {"prompt": 125, "completion": 342}
        },
        "product_description": {
            "content": """**AgentOrch Pro - Enterprise AI Agent Orchestration**

Deploy AI agents with confidence. AgentOrch provides the infrastructure you need to run autonomous AI systems in production.

**Key Features:**
- Real-time cost tracking and budget enforcement
- Multi-provider LLM routing with automatic failover
- Time-travel debugging for complete visibility
- Enterprise SSO and audit logging

**Perfect For:**
- Engineering teams building AI-powered products
- Enterprises deploying customer-facing AI agents
- Organizations scaling from prototype to production

*Start free, scale as you grow.*
""",
            "tokens": {"prompt": 89, "completion": 156}
        }
    },

    # Sentiment Analysis
    "sentiment_analysis": {
        "positive": {
            "content": """## Sentiment Analysis Results

**Overall Sentiment:** POSITIVE
**Confidence:** 0.91

**Breakdown:**
- Joy: 0.45
- Trust: 0.35
- Anticipation: 0.15
- Neutral: 0.05

**Key Phrases:**
- "love the new feature"
- "exactly what I needed"
- "great customer support"

**Recommended Action:** Flag for testimonial request
""",
            "tokens": {"prompt": 134, "completion": 98}
        },
        "negative": {
            "content": """## Sentiment Analysis Results

**Overall Sentiment:** NEGATIVE
**Confidence:** 0.87

**Breakdown:**
- Frustration: 0.55
- Disappointment: 0.25
- Anger: 0.15
- Neutral: 0.05

**Key Phrases:**
- "doesn't work as expected"
- "wasted my time"
- "need immediate help"

**Recommended Action:** Escalate to support manager
""",
            "tokens": {"prompt": 142, "completion": 102}
        }
    },

    # Code Analysis
    "code_review": {
        "suggestions": {
            "content": """## Code Review Analysis

**Overall Quality:** B+ (Good with minor improvements needed)

**Issues Found:**

1. **Security (High Priority)**
   - Line 45: SQL query uses string interpolation - potential injection risk
   - Suggestion: Use parameterized queries

2. **Performance (Medium)**
   - Line 78-92: N+1 query pattern detected
   - Suggestion: Use batch loading or eager loading

3. **Code Style (Low)**
   - Line 23: Function exceeds 50 lines
   - Suggestion: Extract into smaller functions

**Positive Observations:**
- Good test coverage (87%)
- Clear variable naming
- Proper error handling

**Recommended Actions:**
1. Fix SQL injection vulnerability immediately
2. Refactor N+1 queries before merge
3. Style issues can be addressed in follow-up
""",
            "tokens": {"prompt": 456, "completion": 234}
        }
    },

    # Generic fallback
    "generic": {
        "response": {
            "content": """I've analyzed your request and here's my response:

Based on the context provided, I can help you with this task. The key points to consider are:

1. **Understanding the Problem**: Your request involves processing and analyzing the input data.

2. **Proposed Solution**: I recommend a structured approach that addresses the core requirements.

3. **Next Steps**:
   - Review the analysis above
   - Implement suggested changes
   - Monitor for expected outcomes

Let me know if you need any clarification or have additional requirements.
""",
            "tokens": {"prompt": 150, "completion": 120}
        }
    }
}


class MockLLMProvider:
    """
    Mock LLM provider that simulates realistic responses.

    Used in sandbox environment to avoid actual API costs while
    providing realistic demo experiences.
    """

    def __init__(
        self,
        simulate_latency: bool = True,
        failure_rate: float = 0.0,
        latency_range: tuple = (200, 800),
    ):
        """
        Initialize mock provider.

        Args:
            simulate_latency: Whether to add realistic latency
            failure_rate: Probability of simulated failures (0.0 to 1.0)
            latency_range: Min/max latency in milliseconds
        """
        self.simulate_latency = simulate_latency
        self.failure_rate = failure_rate
        self.latency_range = latency_range
        self.call_history: List[Dict[str, Any]] = []

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        provider: str = "openai",
        scenario: Optional[str] = None,
        variant: Optional[str] = None,
        **kwargs
    ) -> MockLLMResponse:
        """
        Generate mock LLM completion.

        Args:
            messages: Chat messages
            model: Model name
            provider: Provider name
            scenario: Optional scenario for response selection
            variant: Optional variant within scenario
            **kwargs: Additional parameters (ignored but logged)

        Returns:
            MockLLMResponse with realistic content and metadata
        """
        start_time = time.time()

        # Simulate failure if configured
        if random.random() < self.failure_rate:
            raise RuntimeError(f"Simulated {provider} API failure")

        # Simulate latency
        if self.simulate_latency:
            latency_ms = random.randint(*self.latency_range)
            await asyncio.sleep(latency_ms / 1000)
        else:
            latency_ms = 50

        # Detect scenario from message content if not specified
        if not scenario:
            scenario, variant = self._detect_scenario(messages)

        # Get mock response
        response_data = self._get_mock_response(scenario, variant)

        # Calculate realistic token counts
        prompt_tokens = response_data.get("tokens", {}).get("prompt", 150)
        completion_tokens = response_data.get("tokens", {}).get("completion", 100)
        total_tokens = prompt_tokens + completion_tokens

        # Calculate cost based on pricing
        cost = self._calculate_cost(provider, model, prompt_tokens, completion_tokens)

        # Record call
        self.call_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider,
            "model": model,
            "scenario": scenario,
            "tokens": total_tokens,
            "cost": cost,
            "latency_ms": latency_ms,
        })

        return MockLLMResponse(
            content=response_data["content"],
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            latency_ms=latency_ms,
        )

    def _detect_scenario(self, messages: List[Dict[str, str]]) -> tuple:
        """Detect scenario from message content."""
        # Get combined message content
        content = " ".join(m.get("content", "") for m in messages).lower()

        # Pattern matching for scenarios
        if any(word in content for word in ["classify", "ticket", "priority", "support"]):
            if any(word in content for word in ["urgent", "overcharged", "refund", "angry"]):
                return "classify_ticket", "high_priority"
            elif any(word in content for word in ["feature", "premium", "upgrade"]):
                return "classify_ticket", "medium_priority"
            return "classify_ticket", "low_priority"

        if any(word in content for word in ["lead", "qualify", "sales", "prospect"]):
            if any(word in content for word in ["enterprise", "large", "fortune"]):
                return "lead_qualification", "hot_lead"
            return "lead_qualification", "warm_lead"

        if any(word in content for word in ["blog", "article", "write", "content", "generate"]):
            if any(word in content for word in ["blog", "article", "post"]):
                return "content_generation", "blog_post"
            return "content_generation", "product_description"

        if any(word in content for word in ["sentiment", "feeling", "emotion", "analyze"]):
            if any(word in content for word in ["love", "great", "excellent", "happy"]):
                return "sentiment_analysis", "positive"
            elif any(word in content for word in ["hate", "terrible", "angry", "frustrated"]):
                return "sentiment_analysis", "negative"
            return "sentiment_analysis", "positive"

        if any(word in content for word in ["code", "review", "bug", "security"]):
            return "code_review", "suggestions"

        return "generic", "response"

    def _get_mock_response(self, scenario: str, variant: str) -> Dict[str, Any]:
        """Get mock response for scenario."""
        if scenario in MOCK_RESPONSES and variant in MOCK_RESPONSES[scenario]:
            return MOCK_RESPONSES[scenario][variant]
        return MOCK_RESPONSES["generic"]["response"]

    def _calculate_cost(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate mock cost based on pricing."""
        pricing = MOCK_PRICING.get(provider, {}).get(model, {"input": 0.001, "output": 0.002})
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        if not self.call_history:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "by_provider": {},
                "by_model": {},
            }

        return {
            "total_calls": len(self.call_history),
            "total_tokens": sum(c["tokens"] for c in self.call_history),
            "total_cost": sum(c["cost"] for c in self.call_history),
            "by_provider": self._aggregate_by_field("provider"),
            "by_model": self._aggregate_by_field("model"),
            "by_scenario": self._aggregate_by_field("scenario"),
        }

    def _aggregate_by_field(self, field: str) -> Dict[str, Any]:
        """Aggregate stats by field."""
        result = {}
        for call in self.call_history:
            key = call[field]
            if key not in result:
                result[key] = {"calls": 0, "tokens": 0, "cost": 0.0}
            result[key]["calls"] += 1
            result[key]["tokens"] += call["tokens"]
            result[key]["cost"] += call["cost"]
        return result

    def reset_history(self):
        """Reset call history."""
        self.call_history = []


# Singleton for demo use
_mock_provider: Optional[MockLLMProvider] = None


def get_mock_provider() -> MockLLMProvider:
    """Get or create the mock LLM provider singleton."""
    global _mock_provider
    if _mock_provider is None:
        _mock_provider = MockLLMProvider()
    return _mock_provider

#!/usr/bin/env python3
"""
Demo: Universal Schema for Provider Normalization

Shows the provider normalization layer from ROADMAP.md:
1. Creating provider-agnostic requests
2. Converting to OpenAI format
3. Converting to Anthropic format
4. Converting to DeepSeek format
5. Parsing responses back to universal format
6. Tool call handling across providers
7. Cost calculation across providers

Reference: ROADMAP.md Section "Provider Normalization Layer"

Key Design Decisions:
- Single UniversalRequest/Response format for all providers
- Adapters handle provider-specific quirks
- Tool calls normalized across different APIs
- Cost calculation with cache support
"""

import asyncio
import sys
import json
from pathlib import Path

# Add parent directories to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

from backend.shared.universal_schema import (
    UniversalRole,
    UniversalMessage,
    UniversalToolCall,
    UniversalRequest,
    UniversalResponse,
    ToolDefinition,
    ToolParameter,
    ModelConfig,
    TokenUsage,
    ContentBlock,
    ContentType,
    create_text_message,
    create_tool_result_message,
    messages_to_json,
)
from backend.shared.provider_adapters import (
    OpenAIAdapter,
    AnthropicAdapter,
    DeepSeekAdapter,
    get_adapter,
)


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_json(label: str, data: dict):
    """Print JSON data with label."""
    print(f"\n{label}:")
    print(json.dumps(data, indent=2, default=str))


def demo_universal_request():
    """Demo 1: Create a universal request."""
    print_header("Demo 1: Universal Request Format")
    print("\nCreate a provider-agnostic request that works with any LLM.\n")

    # Create messages
    messages = [
        UniversalMessage(
            role=UniversalRole.SYSTEM,
            content="You are a helpful assistant that provides weather information.",
        ),
        UniversalMessage(
            role=UniversalRole.USER,
            content="What's the weather like in New York?",
        ),
    ]

    # Create tools
    weather_tool = ToolDefinition(
        name="get_weather",
        description="Get the current weather for a location",
        parameters=[
            ToolParameter(name="location", type="string", description="City name", required=True),
            ToolParameter(name="unit", type="string", description="Temperature unit", enum=["celsius", "fahrenheit"]),
        ],
    )

    # Create request
    request = UniversalRequest(
        messages=messages,
        model_config=ModelConfig(
            model="gpt-4",
            temperature=0.7,
            max_tokens=500,
        ),
        tools=[weather_tool],
        tool_choice="auto",
    )

    print("Universal Request Created:")
    print(f"  Messages: {len(request.messages)}")
    print(f"  Model: {request.model_config.model}")
    print(f"  Tools: {[t.name for t in request.tools]}")
    print(f"  System: {request.get_system_message()[:50]}...")

    print("\n[OK] Universal request format works!")
    return request


def demo_openai_conversion(request: UniversalRequest):
    """Demo 2: Convert to OpenAI format."""
    print_header("Demo 2: OpenAI Format Conversion")
    print("\nConvert universal request to OpenAI API format.\n")

    adapter = OpenAIAdapter()
    openai_format = adapter.to_provider_format(request)

    print_json("OpenAI API Payload", openai_format)

    # Simulate response
    print("\nSimulated OpenAI Response:")
    mock_response = {
        "id": "chatcmpl-123abc",
        "object": "chat.completion",
        "model": "gpt-4-0613",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_weather_123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "New York", "unit": "fahrenheit"}'
                    }
                }]
            },
            "finish_reason": "tool_calls"
        }],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 45,
            "total_tokens": 195
        }
    }

    universal_response = adapter.from_provider_format(mock_response, latency_ms=250)
    print(f"\n  Parsed Response:")
    print(f"    Has tool calls: {universal_response.has_tool_calls()}")
    print(f"    Tool: {universal_response.get_tool_calls()[0].name}")
    print(f"    Args: {universal_response.get_tool_calls()[0].arguments}")
    print(f"    Cost: ${universal_response.cost:.6f}")

    print("\n[OK] OpenAI conversion works!")
    return universal_response


def demo_anthropic_conversion(request: UniversalRequest):
    """Demo 3: Convert to Anthropic format."""
    print_header("Demo 3: Anthropic Format Conversion")
    print("\nConvert universal request to Anthropic Claude API format.\n")

    # Modify request for Anthropic
    anthropic_request = UniversalRequest(
        messages=request.messages,
        model_config=ModelConfig(
            model="claude-3-5-sonnet-20241022",
            temperature=0.7,
            max_tokens=500,
        ),
        tools=request.tools,
        tool_choice="auto",
    )

    adapter = AnthropicAdapter()
    anthropic_format = adapter.to_provider_format(anthropic_request)

    print_json("Anthropic API Payload", anthropic_format)

    # Note the differences
    print("\nKey Differences from OpenAI:")
    print("  - System message is separate 'system' field")
    print("  - Tools use 'input_schema' instead of 'parameters'")
    print("  - Tool choice uses {'type': 'auto'} format")

    # Simulate response
    mock_response = {
        "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "I'll check the weather for you."},
            {
                "type": "tool_use",
                "id": "toolu_01A09q90qw90lq917835lqs",
                "name": "get_weather",
                "input": {"location": "New York", "unit": "fahrenheit"}
            }
        ],
        "model": "claude-3-5-sonnet-20241022",
        "stop_reason": "tool_use",
        "usage": {
            "input_tokens": 175,
            "output_tokens": 62,
            "cache_read_input_tokens": 50,
        }
    }

    universal_response = adapter.from_provider_format(mock_response, latency_ms=180)
    print(f"\nParsed Response:")
    print(f"  Content: {universal_response.message.content[:50]}...")
    print(f"  Tool: {universal_response.get_tool_calls()[0].name}")
    print(f"  Cache tokens: {universal_response.usage.cache_read_tokens}")
    print(f"  Cost: ${universal_response.cost:.6f}")

    print("\n[OK] Anthropic conversion works!")
    return universal_response


def demo_deepseek_conversion(request: UniversalRequest):
    """Demo 4: Convert to DeepSeek format."""
    print_header("Demo 4: DeepSeek Format Conversion")
    print("\nConvert universal request to DeepSeek API format.\n")

    # Modify request for DeepSeek
    deepseek_request = UniversalRequest(
        messages=request.messages,
        model_config=ModelConfig(
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=500,
        ),
        tools=request.tools,
        tool_choice="auto",
    )

    adapter = DeepSeekAdapter()
    deepseek_format = adapter.to_provider_format(deepseek_request)

    print_json("DeepSeek API Payload", deepseek_format)

    print("\nDeepSeek uses OpenAI-compatible format with:")
    print("  - Different model names (deepseek-chat, deepseek-coder)")
    print("  - Cache hit tracking in usage")
    print("  - Much lower pricing")

    # Simulate response
    mock_response = {
        "id": "cmpl-123456",
        "object": "chat.completion",
        "model": "deepseek-chat",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "The weather in New York is currently 45°F with partly cloudy skies.",
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 25,
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 70,
        }
    }

    universal_response = adapter.from_provider_format(mock_response, latency_ms=120)
    print(f"\nParsed Response:")
    print(f"  Content: {universal_response.message.content}")
    print(f"  Cache hit tokens: {universal_response.usage.cache_read_tokens}")
    print(f"  Cost: ${universal_response.cost:.6f}")

    print("\n[OK] DeepSeek conversion works!")


def demo_tool_call_flow():
    """Demo 5: Complete tool call flow."""
    print_header("Demo 5: Tool Call Flow Across Providers")
    print("\nHandle tool calls when switching between providers.\n")

    # Initial request with tool call response
    openai_adapter = OpenAIAdapter()
    anthropic_adapter = AnthropicAdapter()

    # Parse tool call from OpenAI
    print("1. Tool call received from OpenAI:")
    openai_tool_response = {
        "id": "cmpl-123",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "NYC", "unit": "celsius"}'
                    }
                }]
            },
            "finish_reason": "tool_calls"
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
        "model": "gpt-4",
    }

    tool_call_response = openai_adapter.from_provider_format(openai_tool_response)
    print(f"   Tool: {tool_call_response.get_tool_calls()[0].name}")
    print(f"   Args: {tool_call_response.get_tool_calls()[0].arguments}")

    # Create tool result
    print("\n2. Executing tool and getting result...")
    tool_result = '{"temperature": 8, "conditions": "Cloudy", "humidity": 75}'
    print(f"   Result: {tool_result}")

    # Create new request with tool result for Anthropic
    print("\n3. Creating request with tool result for Anthropic:")
    messages = [
        UniversalMessage(role=UniversalRole.SYSTEM, content="You are a weather assistant."),
        UniversalMessage(role=UniversalRole.USER, content="What's the weather in NYC?"),
        tool_call_response.message,  # The tool call
        create_tool_result_message("call_abc123", tool_result),  # The result
    ]

    anthropic_request = UniversalRequest(
        messages=messages,
        model_config=ModelConfig(model="claude-3-sonnet", max_tokens=200),
    )

    anthropic_format = anthropic_adapter.to_provider_format(anthropic_request)

    print(f"   Messages sent to Anthropic: {len(anthropic_format['messages'])}")
    print(f"   Tool result type: {anthropic_format['messages'][-1]['content'][0]['type']}")

    print("\n[OK] Tool calls work seamlessly across providers!")


def demo_cost_comparison():
    """Demo 6: Cost comparison across providers."""
    print_header("Demo 6: Cost Comparison")
    print("\nCompare costs for same workload across providers.\n")

    input_tokens = 10000
    output_tokens = 2000

    print(f"Workload: {input_tokens:,} input tokens, {output_tokens:,} output tokens\n")

    providers = [
        ("OpenAI GPT-4", OpenAIAdapter(), "gpt-4"),
        ("OpenAI GPT-4o", OpenAIAdapter(), "gpt-4o"),
        ("OpenAI GPT-4o-mini", OpenAIAdapter(), "gpt-4o-mini"),
        ("Anthropic Claude 3.5 Sonnet", AnthropicAdapter(), "claude-3-5-sonnet-20241022"),
        ("Anthropic Claude 3.5 Haiku", AnthropicAdapter(), "claude-3-5-haiku-20241022"),
        ("DeepSeek Chat", DeepSeekAdapter(), "deepseek-chat"),
        ("DeepSeek V3", DeepSeekAdapter(), "deepseek-v3"),
    ]

    print("┌─────────────────────────────┬────────────┬─────────────┐")
    print("│ Provider / Model            │ Cost       │ vs GPT-4    │")
    print("├─────────────────────────────┼────────────┼─────────────┤")

    gpt4_cost = None
    for name, adapter, model in providers:
        cost = adapter.calculate_cost(model, input_tokens, output_tokens)
        if gpt4_cost is None:
            gpt4_cost = cost
            comparison = "baseline"
        else:
            ratio = cost / gpt4_cost
            if ratio < 0.01:
                comparison = f"{ratio*100:.1f}%"
            elif ratio < 1:
                comparison = f"{ratio*100:.0f}%"
            else:
                comparison = f"{ratio:.1f}x"

        print(f"│ {name:<27} │ ${cost:>8.4f} │ {comparison:>11} │")

    print("└─────────────────────────────┴────────────┴─────────────┘")

    print("\n[OK] Cost comparison shows significant price differences!")


def demo_multi_modal():
    """Demo 7: Multi-modal content handling."""
    print_header("Demo 7: Multi-Modal Content")
    print("\nHandle images and other content types.\n")

    # Create multi-modal message
    content_blocks = [
        ContentBlock(type=ContentType.TEXT, content="What's in this image?"),
        ContentBlock(
            type=ContentType.IMAGE_URL,
            content="https://example.com/sunset.jpg",
            metadata={"alt": "A sunset over the ocean"},
        ),
    ]

    message = UniversalMessage(
        role=UniversalRole.USER,
        content=content_blocks,
    )

    print("Multi-modal message created:")
    print(f"  Content blocks: {len(content_blocks)}")
    print(f"  Types: {[b.type.value for b in content_blocks]}")

    # Convert to OpenAI format
    request = UniversalRequest(
        messages=[message],
        model_config=ModelConfig(model="gpt-4o"),
    )

    adapter = OpenAIAdapter()
    openai_format = adapter.to_provider_format(request)

    print("\nOpenAI format:")
    print(f"  Content type: {type(openai_format['messages'][0]['content'])}")
    if isinstance(openai_format['messages'][0]['content'], list):
        for item in openai_format['messages'][0]['content']:
            print(f"    - {item['type']}")

    print("\n[OK] Multi-modal content handled correctly!")


def demo_use_cases():
    """Demo 8: Common use cases."""
    print_header("Demo 8: Use Case Reference")
    print("\nFrom ROADMAP.md - Provider Normalization Benefits:\n")

    print("┌────────────────────────────────────────────────────────────┐")
    print("│ Benefit                                                    │")
    print("├────────────────────────────────────────────────────────────┤")
    print("│ 1. No raw provider JSON in database - clean data model    │")
    print("│ 2. Easy provider switching for failover                   │")
    print("│ 3. Consistent tool call handling                          │")
    print("│ 4. Unified cost tracking across providers                 │")
    print("│ 5. Provider-specific quirks isolated in adapters          │")
    print("│ 6. Future provider support without core changes           │")
    print("└────────────────────────────────────────────────────────────┘")

    print("\nAdapter Responsibilities:")
    print("  - to_provider_format(): Universal → Provider-specific")
    print("  - from_provider_format(): Provider-specific → Universal")
    print("  - validate_messages(): Enforce provider constraints")
    print("  - calculate_cost(): Provider-specific pricing")

    print("\n" + "-" * 60)
    print("Universal Schema enables seamless multi-provider operations!")
    print("-" * 60)


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("  UNIVERSAL SCHEMA DEMO")
    print("  Provider Normalization Layer")
    print("=" * 60)
    print("\nReference: ROADMAP.md Section 'Provider Normalization Layer'")

    try:
        request = demo_universal_request()
        demo_openai_conversion(request)
        demo_anthropic_conversion(request)
        demo_deepseek_conversion(request)
        demo_tool_call_flow()
        demo_cost_comparison()
        demo_multi_modal()
        demo_use_cases()

        print("\n" + "=" * 60)
        print("  ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nKey Takeaways:")
        print("  1. UniversalRequest/Response work with any provider")
        print("  2. Adapters handle provider-specific format differences")
        print("  3. Tool calls are normalized across OpenAI/Anthropic/DeepSeek")
        print("  4. Cost calculation includes cache pricing where supported")
        print("  5. Multi-modal content handled consistently")
        print("  6. Easy to add new providers with adapter pattern")
        print()

    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

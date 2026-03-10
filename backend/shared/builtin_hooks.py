"""
Built-in Hooks - Common Hook Implementations

Provides ready-to-use hooks for common scenarios:
- Cost guardrails
- Input validation
- PII redaction
- Output validation
- Prompt enrichment
- Custom authentication

These hooks serve as examples and can be used out-of-the-box.
"""

import re
import logging
from typing import Any, Dict, List, Optional

from backend.shared.hook_manager import (
    HookContext,
    HookExecutionResult,
    HookResult,
    HookType
)

logger = logging.getLogger(__name__)


# ============================================================================
# PRE-LLM HOOKS
# ============================================================================

async def cost_guardrail_hook(data: Dict[str, Any], context: HookContext) -> HookExecutionResult:
    """
    Block LLM calls that exceed cost threshold.

    Configuration in context.metadata:
        max_cost: float - Maximum allowed cost per call

    Example:
        context.metadata = {"max_cost": 0.10}
    """
    max_cost = context.metadata.get("max_cost", float('inf'))

    if context.estimated_cost and context.estimated_cost > max_cost:
        return HookExecutionResult(
            hook_name="cost_guardrail",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.BLOCK,
            blocked_reason=f"Estimated cost ${context.estimated_cost:.4f} exceeds limit ${max_cost:.4f}",
            metadata={"estimated_cost": context.estimated_cost, "max_cost": max_cost}
        )

    return HookExecutionResult(
        hook_name="cost_guardrail",
        hook_type=HookType.PRE_LLM_CALL,
        result=HookResult.CONTINUE,
        metadata={"estimated_cost": context.estimated_cost, "max_cost": max_cost}
    )


async def token_limit_hook(data: Dict[str, Any], context: HookContext) -> HookExecutionResult:
    """
    Block LLM calls that exceed token threshold.

    Configuration in context.metadata:
        max_tokens: int - Maximum allowed tokens per call
    """
    max_tokens = context.metadata.get("max_tokens", float('inf'))

    if context.estimated_tokens and context.estimated_tokens > max_tokens:
        return HookExecutionResult(
            hook_name="token_limit",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.BLOCK,
            blocked_reason=f"Estimated tokens {context.estimated_tokens} exceeds limit {max_tokens}",
            metadata={"estimated_tokens": context.estimated_tokens, "max_tokens": max_tokens}
        )

    return HookExecutionResult(
        hook_name="token_limit",
        hook_type=HookType.PRE_LLM_CALL,
        result=HookResult.CONTINUE
    )


async def prompt_length_validator_hook(data: Dict[str, Any], context: HookContext) -> HookExecutionResult:
    """
    Validate that prompts meet length requirements.

    Configuration in context.metadata:
        min_length: int - Minimum prompt length
        max_length: int - Maximum prompt length
    """
    min_length = context.metadata.get("min_length", 0)
    max_length = context.metadata.get("max_length", 100000)

    # Extract prompt from messages
    messages = data.get("messages", [])
    if not messages:
        return HookExecutionResult(
            hook_name="prompt_length_validator",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.BLOCK,
            blocked_reason="No messages in prompt"
        )

    # Calculate total prompt length
    total_length = sum(len(msg.get("content", "")) for msg in messages)

    if total_length < min_length:
        return HookExecutionResult(
            hook_name="prompt_length_validator",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.BLOCK,
            blocked_reason=f"Prompt too short: {total_length} < {min_length}"
        )

    if total_length > max_length:
        return HookExecutionResult(
            hook_name="prompt_length_validator",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.BLOCK,
            blocked_reason=f"Prompt too long: {total_length} > {max_length}"
        )

    return HookExecutionResult(
        hook_name="prompt_length_validator",
        hook_type=HookType.PRE_LLM_CALL,
        result=HookResult.CONTINUE,
        metadata={"prompt_length": total_length}
    )


async def prompt_enrichment_hook(data: Dict[str, Any], context: HookContext) -> HookExecutionResult:
    """
    Add context or instructions to prompts.

    Configuration in context.metadata:
        system_prefix: str - Text to prepend to system message
        user_prefix: str - Text to prepend to user messages
    """
    system_prefix = context.metadata.get("system_prefix", "")
    user_prefix = context.metadata.get("user_prefix", "")

    messages = data.get("messages", [])
    modified = False

    for msg in messages:
        if msg.get("role") == "system" and system_prefix:
            msg["content"] = f"{system_prefix}\n\n{msg['content']}"
            modified = True
        elif msg.get("role") == "user" and user_prefix:
            msg["content"] = f"{user_prefix}\n\n{msg['content']}"
            modified = True

    if modified:
        return HookExecutionResult(
            hook_name="prompt_enrichment",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.MODIFY,
            modified_data=data,
            metadata={"enriched": True}
        )

    return HookExecutionResult(
        hook_name="prompt_enrichment",
        hook_type=HookType.PRE_LLM_CALL,
        result=HookResult.CONTINUE
    )


async def banned_words_filter_hook(data: Dict[str, Any], context: HookContext) -> HookExecutionResult:
    """
    Block prompts containing banned words.

    Configuration in context.metadata:
        banned_words: List[str] - List of banned words
        case_sensitive: bool - Whether matching is case-sensitive
    """
    banned_words = context.metadata.get("banned_words", [])
    case_sensitive = context.metadata.get("case_sensitive", False)

    messages = data.get("messages", [])

    for msg in messages:
        content = msg.get("content", "")
        if not case_sensitive:
            content = content.lower()

        for word in banned_words:
            check_word = word if case_sensitive else word.lower()
            if check_word in content:
                return HookExecutionResult(
                    hook_name="banned_words_filter",
                    hook_type=HookType.PRE_LLM_CALL,
                    result=HookResult.BLOCK,
                    blocked_reason=f"Prompt contains banned word: {word}",
                    metadata={"banned_word": word}
                )

    return HookExecutionResult(
        hook_name="banned_words_filter",
        hook_type=HookType.PRE_LLM_CALL,
        result=HookResult.CONTINUE
    )


# ============================================================================
# POST-LLM HOOKS
# ============================================================================

async def pii_redaction_hook(data: str, context: HookContext) -> HookExecutionResult:
    """
    Redact PII (Personal Identifiable Information) from LLM outputs.

    Redacts:
    - Social Security Numbers (SSN)
    - Credit Card Numbers
    - Email Addresses
    - Phone Numbers
    - IP Addresses

    Configuration in context.metadata:
        redact_ssn: bool - Redact SSNs (default: True)
        redact_credit_cards: bool - Redact credit cards (default: True)
        redact_emails: bool - Redact emails (default: True)
        redact_phones: bool - Redact phone numbers (default: True)
        redact_ips: bool - Redact IP addresses (default: False)
        replacement: str - Replacement text (default: "[REDACTED]")
    """
    config = context.metadata
    replacement = config.get("replacement", "[REDACTED]")

    modified_text = data
    redactions = []

    # SSN pattern: XXX-XX-XXXX
    if config.get("redact_ssn", True):
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        if re.search(ssn_pattern, modified_text):
            modified_text = re.sub(ssn_pattern, f"{replacement}_SSN", modified_text)
            redactions.append("SSN")

    # Credit card pattern: XXXX-XXXX-XXXX-XXXX or XXXXXXXXXXXXXXXX
    if config.get("redact_credit_cards", True):
        cc_pattern = r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
        if re.search(cc_pattern, modified_text):
            modified_text = re.sub(cc_pattern, f"{replacement}_CC", modified_text)
            redactions.append("credit_card")

    # Email pattern
    if config.get("redact_emails", True):
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, modified_text):
            modified_text = re.sub(email_pattern, f"{replacement}_EMAIL", modified_text)
            redactions.append("email")

    # Phone number pattern: (XXX) XXX-XXXX or XXX-XXX-XXXX
    if config.get("redact_phones", True):
        phone_pattern = r'\b(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b'
        if re.search(phone_pattern, modified_text):
            modified_text = re.sub(phone_pattern, f"{replacement}_PHONE", modified_text)
            redactions.append("phone")

    # IP address pattern
    if config.get("redact_ips", False):
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        if re.search(ip_pattern, modified_text):
            modified_text = re.sub(ip_pattern, f"{replacement}_IP", modified_text)
            redactions.append("ip_address")

    if redactions:
        logger.info(f"PII redaction applied: {', '.join(redactions)}")
        return HookExecutionResult(
            hook_name="pii_redaction",
            hook_type=HookType.POST_LLM_CALL,
            result=HookResult.MODIFY,
            modified_data=modified_text,
            metadata={"redactions": redactions}
        )

    return HookExecutionResult(
        hook_name="pii_redaction",
        hook_type=HookType.POST_LLM_CALL,
        result=HookResult.CONTINUE
    )


async def output_length_validator_hook(data: str, context: HookContext) -> HookExecutionResult:
    """
    Validate output length.

    Configuration in context.metadata:
        min_length: int - Minimum output length
        max_length: int - Maximum output length
    """
    min_length = context.metadata.get("min_length", 0)
    max_length = context.metadata.get("max_length", 100000)

    output_length = len(data) if isinstance(data, str) else 0

    if output_length < min_length:
        return HookExecutionResult(
            hook_name="output_length_validator",
            hook_type=HookType.POST_LLM_CALL,
            result=HookResult.BLOCK,
            blocked_reason=f"Output too short: {output_length} < {min_length}",
            metadata={"output_length": output_length}
        )

    if output_length > max_length:
        return HookExecutionResult(
            hook_name="output_length_validator",
            hook_type=HookType.POST_LLM_CALL,
            result=HookResult.BLOCK,
            blocked_reason=f"Output too long: {output_length} > {max_length}",
            metadata={"output_length": output_length}
        )

    return HookExecutionResult(
        hook_name="output_length_validator",
        hook_type=HookType.POST_LLM_CALL,
        result=HookResult.CONTINUE,
        metadata={"output_length": output_length}
    )


async def json_validator_hook(data: str, context: HookContext) -> HookExecutionResult:
    """
    Validate that output is valid JSON.

    Configuration in context.metadata:
        require_json: bool - Whether to require valid JSON
        extract_json: bool - Try to extract JSON from markdown code blocks
    """
    import json

    require_json = context.metadata.get("require_json", True)
    extract_json = context.metadata.get("extract_json", True)

    text = data

    # Try to extract JSON from markdown code blocks
    if extract_json and "```json" in text:
        match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
        if match:
            text = match.group(1)

    # Validate JSON
    try:
        parsed = json.loads(text)
        logger.debug("Output is valid JSON")

        if text != data:
            # We extracted JSON from markdown
            return HookExecutionResult(
                hook_name="json_validator",
                hook_type=HookType.POST_LLM_CALL,
                result=HookResult.MODIFY,
                modified_data=text,
                metadata={"valid_json": True, "extracted": True}
            )

        return HookExecutionResult(
            hook_name="json_validator",
            hook_type=HookType.POST_LLM_CALL,
            result=HookResult.CONTINUE,
            metadata={"valid_json": True}
        )

    except json.JSONDecodeError as e:
        if require_json:
            return HookExecutionResult(
                hook_name="json_validator",
                hook_type=HookType.POST_LLM_CALL,
                result=HookResult.BLOCK,
                blocked_reason=f"Output is not valid JSON: {str(e)}",
                metadata={"valid_json": False, "error": str(e)}
            )

        return HookExecutionResult(
            hook_name="json_validator",
            hook_type=HookType.POST_LLM_CALL,
            result=HookResult.CONTINUE,
            metadata={"valid_json": False}
        )


async def content_filter_hook(data: str, context: HookContext) -> HookExecutionResult:
    """
    Filter inappropriate content from outputs.

    Configuration in context.metadata:
        blocked_patterns: List[str] - Regex patterns to block
        case_sensitive: bool - Case sensitive matching
    """
    blocked_patterns = context.metadata.get("blocked_patterns", [])
    case_sensitive = context.metadata.get("case_sensitive", False)

    flags = 0 if case_sensitive else re.IGNORECASE

    for pattern in blocked_patterns:
        if re.search(pattern, data, flags=flags):
            return HookExecutionResult(
                hook_name="content_filter",
                hook_type=HookType.POST_LLM_CALL,
                result=HookResult.BLOCK,
                blocked_reason=f"Output matches blocked pattern: {pattern}",
                metadata={"matched_pattern": pattern}
            )

    return HookExecutionResult(
        hook_name="content_filter",
        hook_type=HookType.POST_LLM_CALL,
        result=HookResult.CONTINUE
    )


# ============================================================================
# PRE-TOOL HOOKS
# ============================================================================

async def url_whitelist_hook(data: Dict[str, Any], context: HookContext) -> HookExecutionResult:
    """
    Ensure tool calls only access whitelisted URLs.

    Configuration in context.metadata:
        allowed_domains: List[str] - List of allowed domains
    """
    from urllib.parse import urlparse

    allowed_domains = context.metadata.get("allowed_domains", [])
    url = data.get("url") or context.url

    if not url:
        return HookExecutionResult(
            hook_name="url_whitelist",
            hook_type=HookType.PRE_TOOL_CALL,
            result=HookResult.CONTINUE
        )

    parsed = urlparse(url)
    domain = parsed.netloc

    if allowed_domains and domain not in allowed_domains:
        return HookExecutionResult(
            hook_name="url_whitelist",
            hook_type=HookType.PRE_TOOL_CALL,
            result=HookResult.BLOCK,
            blocked_reason=f"Domain {domain} not in whitelist",
            metadata={"domain": domain, "allowed": allowed_domains}
        )

    return HookExecutionResult(
        hook_name="url_whitelist",
        hook_type=HookType.PRE_TOOL_CALL,
        result=HookResult.CONTINUE,
        metadata={"domain": domain}
    )


async def auth_injection_hook(data: Dict[str, Any], context: HookContext) -> HookExecutionResult:
    """
    Inject authentication headers dynamically.

    Configuration in context.metadata:
        auth_token_source: Callable - Function that returns auth token
        header_name: str - Auth header name (default: Authorization)
    """
    auth_token_source = context.metadata.get("auth_token_source")
    header_name = context.metadata.get("header_name", "Authorization")

    if not auth_token_source:
        return HookExecutionResult(
            hook_name="auth_injection",
            hook_type=HookType.PRE_TOOL_CALL,
            result=HookResult.CONTINUE
        )

    # Get fresh auth token
    if asyncio.iscoroutinefunction(auth_token_source):
        token = await auth_token_source()
    else:
        token = auth_token_source()

    # Inject into headers
    if "headers" not in data:
        data["headers"] = {}

    data["headers"][header_name] = token

    logger.debug(f"Injected auth token into {header_name} header")

    return HookExecutionResult(
        hook_name="auth_injection",
        hook_type=HookType.PRE_TOOL_CALL,
        result=HookResult.MODIFY,
        modified_data=data,
        metadata={"header_injected": header_name}
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def register_builtin_hooks(manager, config: Optional[Dict[str, Any]] = None):
    """
    Register all built-in hooks with a HookManager.

    Args:
        manager: HookManager instance
        config: Configuration dict for hooks

    Example:
        from backend.shared.hook_manager import get_hook_manager
        from backend.shared.builtin_hooks import register_builtin_hooks

        manager = get_hook_manager()
        config = {
            "cost_guardrail": {"max_cost": 0.10},
            "pii_redaction": {"enabled": True}
        }
        register_builtin_hooks(manager, config)
    """
    config = config or {}

    # Register pre-LLM hooks
    if config.get("cost_guardrail", {}).get("enabled", False):
        manager.register_hook(
            HookType.PRE_LLM_CALL,
            "cost_guardrail",
            cost_guardrail_hook,
            priority=10,
            description="Block LLM calls exceeding cost threshold"
        )

    if config.get("token_limit", {}).get("enabled", False):
        manager.register_hook(
            HookType.PRE_LLM_CALL,
            "token_limit",
            token_limit_hook,
            priority=20,
            description="Block LLM calls exceeding token threshold"
        )

    if config.get("prompt_length_validator", {}).get("enabled", False):
        manager.register_hook(
            HookType.PRE_LLM_CALL,
            "prompt_length_validator",
            prompt_length_validator_hook,
            priority=30,
            description="Validate prompt length requirements"
        )

    # Register post-LLM hooks
    if config.get("pii_redaction", {}).get("enabled", False):
        manager.register_hook(
            HookType.POST_LLM_CALL,
            "pii_redaction",
            pii_redaction_hook,
            priority=10,
            description="Redact PII from LLM outputs"
        )

    if config.get("json_validator", {}).get("enabled", False):
        manager.register_hook(
            HookType.POST_LLM_CALL,
            "json_validator",
            json_validator_hook,
            priority=20,
            description="Validate JSON output format"
        )

    # Register pre-tool hooks
    if config.get("url_whitelist", {}).get("enabled", False):
        manager.register_hook(
            HookType.PRE_TOOL_CALL,
            "url_whitelist",
            url_whitelist_hook,
            priority=10,
            description="Restrict tool calls to whitelisted URLs"
        )

    logger.info("Registered built-in hooks")

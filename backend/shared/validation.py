"""
Input Validation and Sanitization

Provides additional validation and sanitization beyond Pydantic models
to prevent injection attacks and ensure data integrity.
"""

import re
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, status


# ============================================================================
# String Sanitization
# ============================================================================

def sanitize_string(
    value: str,
    max_length: int = 1000,
    allow_special_chars: bool = False
) -> str:
    """
    Sanitize string input.

    Args:
        value: Input string
        max_length: Maximum allowed length
        allow_special_chars: Whether to allow special characters

    Returns:
        Sanitized string

    Raises:
        ValueError: If input is invalid
    """
    if not isinstance(value, str):
        raise ValueError("Value must be a string")

    # Trim whitespace
    value = value.strip()

    # Check length
    if len(value) > max_length:
        raise ValueError(f"String exceeds maximum length of {max_length}")

    # Remove null bytes
    if '\x00' in value:
        raise ValueError("String contains null bytes")

    # Check for control characters
    if any(ord(c) < 32 for c in value if c not in '\n\r\t'):
        raise ValueError("String contains invalid control characters")

    # Check for special characters if not allowed
    if not allow_special_chars:
        if not re.match(r'^[a-zA-Z0-9\s\-_.,!?@]+$', value):
            raise ValueError("String contains disallowed special characters")

    return value


def sanitize_agent_name(name: str) -> str:
    """
    Sanitize agent name.

    Args:
        name: Agent name

    Returns:
        Sanitized name

    Raises:
        ValueError: If name is invalid
    """
    name = sanitize_string(name, max_length=100, allow_special_chars=False)

    # Check minimum length
    if len(name) < 3:
        raise ValueError("Agent name must be at least 3 characters")

    # Must start with letter or number
    if not re.match(r'^[a-zA-Z0-9]', name):
        raise ValueError("Agent name must start with letter or number")

    return name


def sanitize_capability_name(name: str) -> str:
    """
    Sanitize capability name.

    Args:
        name: Capability name

    Returns:
        Sanitized name

    Raises:
        ValueError: If name is invalid
    """
    name = sanitize_string(name, max_length=100, allow_special_chars=False)

    # Check format (lowercase with underscores)
    if not re.match(r'^[a-z0-9_]+$', name):
        raise ValueError("Capability name must be lowercase alphanumeric with underscores")

    return name


# ============================================================================
# JSON Sanitization
# ============================================================================

def sanitize_json(
    data: Dict[str, Any],
    max_depth: int = 10,
    max_keys: int = 100,
    max_string_length: int = 10000
) -> Dict[str, Any]:
    """
    Sanitize JSON data recursively.

    Args:
        data: Input dictionary
        max_depth: Maximum nesting depth
        max_keys: Maximum number of keys
        max_string_length: Maximum string value length

    Returns:
        Sanitized dictionary

    Raises:
        ValueError: If data structure is invalid
    """
    def _sanitize_recursive(obj: Any, depth: int = 0) -> Any:
        """Recursively sanitize object."""
        if depth > max_depth:
            raise ValueError(f"JSON depth exceeds maximum of {max_depth}")

        if isinstance(obj, dict):
            if len(obj) > max_keys:
                raise ValueError(f"JSON has too many keys (max {max_keys})")

            return {
                str(k): _sanitize_recursive(v, depth + 1)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            if len(obj) > max_keys:
                raise ValueError(f"Array has too many items (max {max_keys})")

            return [_sanitize_recursive(item, depth + 1) for item in obj]
        elif isinstance(obj, str):
            if len(obj) > max_string_length:
                raise ValueError(f"String exceeds maximum length of {max_string_length}")

            # Remove null bytes
            if '\x00' in obj:
                raise ValueError("String contains null bytes")

            return obj
        elif isinstance(obj, (int, float, bool, type(None))):
            return obj
        else:
            raise ValueError(f"Unsupported data type: {type(obj)}")

    return _sanitize_recursive(data)


# ============================================================================
# Numeric Validation
# ============================================================================

def validate_cost(cost: float) -> float:
    """
    Validate cost value.

    Args:
        cost: Cost in USD

    Returns:
        Validated cost

    Raises:
        ValueError: If cost is invalid
    """
    if not isinstance(cost, (int, float)):
        raise ValueError("Cost must be a number")

    if cost < 0:
        raise ValueError("Cost cannot be negative")

    if cost > 1000000:  # $1M max
        raise ValueError("Cost exceeds maximum allowed value")

    # Round to 4 decimal places
    return round(cost, 4)


def validate_priority(priority: int) -> int:
    """
    Validate task priority.

    Args:
        priority: Priority value

    Returns:
        Validated priority

    Raises:
        ValueError: If priority is invalid
    """
    if not isinstance(priority, int):
        raise ValueError("Priority must be an integer")

    if priority < 0 or priority > 100:
        raise ValueError("Priority must be between 0 and 100")

    return priority


# ============================================================================
# ID Validation
# ============================================================================

def validate_uuid(value: Any) -> UUID:
    """
    Validate UUID.

    Args:
        value: UUID string or object

    Returns:
        UUID object

    Raises:
        HTTPException: If UUID is invalid
    """
    try:
        if isinstance(value, UUID):
            return value
        return UUID(str(value))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID: {value}"
        )


# ============================================================================
# SQL Injection Prevention
# ============================================================================

def validate_sql_safe(value: str) -> str:
    """
    Validate string is safe for SQL queries.

    Note: This is a defense-in-depth measure. Always use parameterized queries.

    Args:
        value: Input string

    Returns:
        Validated string

    Raises:
        ValueError: If string contains SQL keywords
    """
    # Check for common SQL keywords (case-insensitive)
    sql_keywords = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
        'ALTER', 'EXEC', 'EXECUTE', 'UNION', 'DECLARE', '--', ';--'
    ]

    value_upper = value.upper()
    for keyword in sql_keywords:
        if keyword in value_upper:
            raise ValueError(f"Input contains disallowed SQL keyword: {keyword}")

    return value


# ============================================================================
# XSS Prevention
# ============================================================================

def sanitize_html(value: str) -> str:
    """
    Sanitize HTML to prevent XSS attacks.

    Args:
        value: Input string

    Returns:
        Sanitized string with HTML entities escaped
    """
    if not isinstance(value, str):
        return value

    # Escape HTML entities
    replacements = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '&': '&amp;',
    }

    for char, entity in replacements.items():
        value = value.replace(char, entity)

    return value


# ============================================================================
# Command Injection Prevention
# ============================================================================

def validate_no_shell_chars(value: str) -> str:
    """
    Validate string doesn't contain shell metacharacters.

    Args:
        value: Input string

    Returns:
        Validated string

    Raises:
        ValueError: If string contains shell metacharacters
    """
    shell_chars = ['|', '&', ';', '$', '`', '\n', '(', ')', '<', '>', '!']

    for char in shell_chars:
        if char in value:
            raise ValueError(f"Input contains disallowed character: {char}")

    return value


# ============================================================================
# Path Traversal Prevention
# ============================================================================

def validate_safe_path(path: str) -> str:
    """
    Validate path doesn't contain traversal sequences.

    Args:
        path: File path

    Returns:
        Validated path

    Raises:
        ValueError: If path contains traversal sequences
    """
    # Check for path traversal
    if '..' in path:
        raise ValueError("Path contains traversal sequence")

    # Check for absolute paths
    if path.startswith('/') or path.startswith('\\'):
        raise ValueError("Absolute paths not allowed")

    # Check for drive letters (Windows)
    if re.match(r'^[a-zA-Z]:', path):
        raise ValueError("Drive letters not allowed")

    return path


# ============================================================================
# Rate Limit Validation
# ============================================================================

def validate_within_rate_limit(
    identifier: str,
    limit: int,
    window_seconds: int,
    counter: Dict[str, Dict[str, Any]]
) -> bool:
    """
    Check if request is within rate limit.

    Args:
        identifier: Unique identifier (e.g., API key, IP)
        limit: Maximum requests allowed
        window_seconds: Time window in seconds
        counter: Counter dictionary (modified in place)

    Returns:
        True if within limit, False otherwise
    """
    import time

    now = time.time()

    if identifier not in counter:
        counter[identifier] = {
            'count': 1,
            'window_start': now,
        }
        return True

    entry = counter[identifier]

    # Reset if window expired
    if now - entry['window_start'] > window_seconds:
        entry['count'] = 1
        entry['window_start'] = now
        return True

    # Increment counter
    entry['count'] += 1

    return entry['count'] <= limit


# ============================================================================
# Comprehensive Validation
# ============================================================================

def validate_task_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize task input data.

    Args:
        data: Task input data

    Returns:
        Sanitized data

    Raises:
        HTTPException: If validation fails
    """
    try:
        # Sanitize JSON structure
        sanitized = sanitize_json(data, max_depth=5, max_keys=50)

        # Validate specific fields if present
        if 'name' in sanitized:
            sanitized['name'] = sanitize_string(sanitized['name'], max_length=200)

        if 'description' in sanitized:
            sanitized['description'] = sanitize_string(
                sanitized['description'],
                max_length=2000,
                allow_special_chars=True
            )

        return sanitized

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {str(e)}"
        )

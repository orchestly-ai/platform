"""
URL Validator — SSRF Protection

Blocks requests to private/internal IP ranges, localhost, link-local,
and cloud metadata endpoints to prevent Server-Side Request Forgery.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Cloud metadata endpoints (AWS, GCP, Azure, DigitalOcean)
_BLOCKED_HOSTS = frozenset({
    "169.254.169.254",   # AWS / GCP / DO metadata
    "metadata.google.internal",
    "metadata.google",
    "100.100.100.200",   # Alibaba Cloud metadata
})

_BLOCKED_SCHEMES = frozenset({"file", "ftp", "gopher", "dict", "ldap", "telnet"})


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is in a private/reserved range."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        )
    except ValueError:
        return False


def validate_url(url: str) -> str:
    """
    Validate a URL is safe for server-side requests.

    Raises ValueError if the URL targets a private/internal address,
    cloud metadata endpoint, or uses a blocked scheme.

    Returns the validated URL on success.
    """
    parsed = urlparse(url)

    # Block dangerous schemes
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        raise ValueError(f"Blocked URL scheme: {parsed.scheme}")

    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Only HTTP(S) URLs are allowed, got: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    # Block known metadata endpoints
    if hostname.lower() in _BLOCKED_HOSTS:
        raise ValueError(f"Blocked metadata endpoint: {hostname}")

    # Block localhost variants
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValueError(f"Blocked localhost address: {hostname}")

    # Resolve hostname and check IP
    try:
        resolved_ips = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
        for family, type_, proto, canonname, sockaddr in resolved_ips:
            ip_str = sockaddr[0]
            if _is_private_ip(ip_str):
                raise ValueError(
                    f"URL resolves to private/internal IP: {hostname} -> {ip_str}"
                )
            if ip_str in _BLOCKED_HOSTS:
                raise ValueError(
                    f"URL resolves to blocked metadata IP: {hostname} -> {ip_str}"
                )
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")

    return url

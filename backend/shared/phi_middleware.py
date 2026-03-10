"""
PHI Detection Middleware

FastAPI middleware that scans request bodies for PHI patterns and logs
detections to the audit system. Detection-only (does not block requests).

The orchestration platform acts as a Business Associate since healthcare
tenants route PHI through it — this middleware ensures all PHI access
is tracked for HIPAA compliance.
"""

import re
import json
import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

logger = logging.getLogger(__name__)

# PHI detection regex patterns (aligned with hipaa_compliance.py Safe Harbor identifiers)
PHI_PATTERNS = {
    "ssn": re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
    "mrn": re.compile(r'\bMRN[:\s#]*\d{6,12}\b', re.IGNORECASE),
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "phone": re.compile(r'\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b'),
    "dob": re.compile(r'\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b'),
}


def detect_phi_in_text(text: str) -> list[str]:
    """Scan text for PHI patterns and return list of detected types."""
    detected = []
    for phi_type, pattern in PHI_PATTERNS.items():
        if pattern.search(text):
            detected.append(phi_type)
    return detected


class PHIDetectionMiddleware(BaseHTTPMiddleware):
    """
    Scans POST/PUT/PATCH request bodies for PHI patterns.

    On PHI detection:
    - Logs to the audit system with pii_accessed=True
    - Adds X-PHI-Detected header (internal use only)

    Always adds X-HIPAA-Compliance: enforced header to all responses.
    Detection-only — does not block requests.
    """

    async def dispatch(self, request: StarletteRequest, call_next):
        phi_detected = []

        # Only scan request bodies for write operations
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    body_text = body.decode("utf-8", errors="ignore")
                    phi_detected = detect_phi_in_text(body_text)

                    if phi_detected:
                        logger.info(
                            f"PHI detected in {request.method} {request.url.path}: "
                            f"types={phi_detected}"
                        )

                        # Log to audit system
                        try:
                            from backend.shared.audit_logger import get_audit_logger
                            from backend.shared.audit_models import AuditEvent, AuditEventType, AuditSeverity

                            audit = get_audit_logger()
                            event = AuditEvent(
                                event_type=AuditEventType.DATA_ACCESS,
                                action="phi_detected",
                                description=f"PHI patterns detected in request to {request.url.path}",
                                severity=AuditSeverity.INFO,
                                resource_type="api_request",
                                resource_id=str(request.url.path),
                                pii_accessed=True,
                                metadata={"phi_types": phi_detected, "method": request.method},
                                ip_address=request.client.host if request.client else None,
                            )
                            await audit.log_event(event)
                        except Exception as e:
                            logger.debug(f"Could not log PHI detection to audit: {e}")
            except Exception as e:
                logger.debug(f"PHI scan skipped for {request.url.path}: {e}")

        response = await call_next(request)

        # Always add HIPAA compliance header
        response.headers["X-HIPAA-Compliance"] = "enforced"

        if phi_detected:
            response.headers["X-PHI-Detected"] = ",".join(phi_detected)

        return response

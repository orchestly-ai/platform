"""
Gmail Integration

Real Gmail integration using Google OAuth 2.0 and Gmail API.
Supports sending emails, reading inbox, managing labels, etc.

OAuth Scopes Required:
- gmail.send - Send emails
- gmail.readonly - Read emails
- gmail.modify - Modify emails and labels
"""

import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging

from backend.shared.integrations.base import (
    OAuthIntegration,
    OAuthConfig,
    OAuthTokens,
    IntegrationResult,
)

logger = logging.getLogger(__name__)

# Gmail API base URL
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


class GmailIntegration(OAuthIntegration):
    """
    Gmail integration with full OAuth 2.0 support.

    Supports:
    - send_email: Send emails
    - get_messages: Get inbox messages
    - get_message: Get a specific message
    - search_messages: Search emails
    - add_label: Add labels to messages
    - mark_as_read: Mark messages as read
    - get_labels: Get all labels
    """

    name = "gmail"
    display_name = "Gmail"
    description = "Send and receive emails through Gmail"
    icon_url = "https://www.gstatic.com/images/branding/product/2x/gmail_2020q4_48dp.png"
    documentation_url = "https://developers.google.com/gmail/api"

    # OAuth configuration - in production, load from environment
    OAUTH_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    OAUTH_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:3000/integrations/gmail/callback")

    DEFAULT_SCOPES = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    def get_oauth_config(self) -> Optional[OAuthConfig]:
        """Return Google OAuth configuration."""
        return OAuthConfig(
            client_id=self.OAUTH_CLIENT_ID,
            client_secret=self.OAUTH_CLIENT_SECRET,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=self.DEFAULT_SCOPES,
            redirect_uri=self.OAUTH_REDIRECT_URI,
        )

    async def validate_credentials(self) -> bool:
        """Validate Gmail credentials by getting user profile."""
        access_token = self.get_access_token()
        if not access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API_BASE}/users/me/profile",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Gmail credential validation failed: {e}")
            return False

    async def refresh_tokens(self) -> Optional[OAuthTokens]:
        """Refresh Google OAuth tokens."""
        refresh_token = self.get_refresh_token()
        if not refresh_token:
            return None

        oauth_config = self.get_oauth_config()
        if not oauth_config:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    oauth_config.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": oauth_config.client_id,
                        "client_secret": oauth_config.client_secret,
                        "refresh_token": refresh_token,
                    },
                )
                data = response.json()

                if "access_token" in data:
                    expires_at = datetime.utcnow() + timedelta(
                        seconds=data.get("expires_in", 3600)
                    )
                    return OAuthTokens(
                        access_token=data["access_token"],
                        refresh_token=data.get("refresh_token", refresh_token),
                        token_type="Bearer",
                        expires_at=expires_at,
                        scope=data.get("scope"),
                    )
                else:
                    logger.error(f"Gmail token refresh failed: {data.get('error')}")
                    return None
        except Exception as e:
            logger.error(f"Gmail token refresh error: {e}")
            return None

    def get_available_actions(self) -> List[Dict[str, Any]]:
        """Return list of available Gmail actions."""
        return [
            {
                "name": "send_email",
                "display_name": "Send Email",
                "description": "Send an email",
                "input_schema": {
                    "type": "object",
                    "required": ["to", "subject", "body"],
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email address",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject",
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body (HTML supported)",
                        },
                        "cc": {
                            "type": "string",
                            "description": "CC email addresses (comma-separated)",
                        },
                        "bcc": {
                            "type": "string",
                            "description": "BCC email addresses (comma-separated)",
                        },
                        "is_html": {
                            "type": "boolean",
                            "description": "Whether the body is HTML",
                            "default": False,
                        },
                    },
                },
            },
            {
                "name": "get_messages",
                "display_name": "Get Messages",
                "description": "Get inbox messages",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum messages to return",
                            "default": 10,
                        },
                        "label_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by label IDs",
                            "default": ["INBOX"],
                        },
                    },
                },
            },
            {
                "name": "get_message",
                "display_name": "Get Message",
                "description": "Get a specific message by ID",
                "input_schema": {
                    "type": "object",
                    "required": ["message_id"],
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "Message ID",
                        },
                    },
                },
            },
            {
                "name": "search_messages",
                "display_name": "Search Messages",
                "description": "Search emails using Gmail query syntax",
                "input_schema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Gmail search query (e.g., 'from:example@gmail.com')",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results",
                            "default": 10,
                        },
                    },
                },
            },
            {
                "name": "add_label",
                "display_name": "Add Label",
                "description": "Add a label to a message",
                "input_schema": {
                    "type": "object",
                    "required": ["message_id", "label_ids"],
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "Message ID",
                        },
                        "label_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Label IDs to add",
                        },
                    },
                },
            },
            {
                "name": "mark_as_read",
                "display_name": "Mark as Read",
                "description": "Mark a message as read",
                "input_schema": {
                    "type": "object",
                    "required": ["message_id"],
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "Message ID",
                        },
                    },
                },
            },
            {
                "name": "get_labels",
                "display_name": "Get Labels",
                "description": "Get all Gmail labels",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "test_connection",
                "display_name": "Test Connection",
                "description": "Test the Gmail connection",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute a Gmail action."""
        start_time = datetime.utcnow()

        # Check if token needs refresh
        if self.is_token_expired():
            new_tokens = await self.refresh_tokens()
            if new_tokens:
                self.credentials["access_token"] = new_tokens.access_token
                if new_tokens.refresh_token:
                    self.credentials["refresh_token"] = new_tokens.refresh_token

        access_token = self.get_access_token()
        if not access_token:
            return IntegrationResult(
                success=False,
                error_message="No access token available. Please authenticate with Gmail.",
                error_code="NO_TOKEN",
            )

        try:
            # Route to appropriate action handler
            if action_name == "send_email":
                result = await self._send_email(access_token, parameters)
            elif action_name == "get_messages":
                result = await self._get_messages(access_token, parameters)
            elif action_name == "get_message":
                result = await self._get_message(access_token, parameters)
            elif action_name == "search_messages":
                result = await self._search_messages(access_token, parameters)
            elif action_name == "add_label":
                result = await self._add_label(access_token, parameters)
            elif action_name == "mark_as_read":
                result = await self._mark_as_read(access_token, parameters)
            elif action_name == "get_labels":
                result = await self._get_labels(access_token)
            elif action_name == "test_connection":
                result = await self.test_connection()
            else:
                result = IntegrationResult(
                    success=False,
                    error_message=f"Unknown action: {action_name}",
                    error_code="UNKNOWN_ACTION",
                )

            # Calculate duration
            end_time = datetime.utcnow()
            result.duration_ms = (end_time - start_time).total_seconds() * 1000
            return result

        except Exception as e:
            logger.error(f"Gmail action {action_name} failed: {e}")
            end_time = datetime.utcnow()
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                duration_ms=(end_time - start_time).total_seconds() * 1000,
            )

    async def _send_email(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Send an email."""
        # Create message
        if params.get("is_html", False):
            message = MIMEMultipart("alternative")
            message.attach(MIMEText(params["body"], "html"))
        else:
            message = MIMEText(params["body"])

        message["to"] = params["to"]
        message["subject"] = params["subject"]

        if params.get("cc"):
            message["cc"] = params["cc"]
        if params.get("bcc"):
            message["bcc"] = params["bcc"]

        # Encode message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GMAIL_API_BASE}/users/me/messages/send",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"raw": raw},
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "message_id": data.get("id"),
                        "thread_id": data.get("threadId"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", {}).get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _get_messages(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Get inbox messages."""
        max_results = params.get("max_results", 10)
        label_ids = params.get("label_ids", ["INBOX"])

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/users/me/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "maxResults": max_results,
                    "labelIds": label_ids,
                },
            )

            if response.status_code == 200:
                data = response.json()
                messages = []

                # Get details for each message
                for msg in data.get("messages", [])[:max_results]:
                    msg_response = await client.get(
                        f"{GMAIL_API_BASE}/users/me/messages/{msg['id']}",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                    )
                    if msg_response.status_code == 200:
                        msg_data = msg_response.json()
                        headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
                        messages.append({
                            "id": msg_data.get("id"),
                            "thread_id": msg_data.get("threadId"),
                            "snippet": msg_data.get("snippet"),
                            "from": headers.get("From"),
                            "subject": headers.get("Subject"),
                            "date": headers.get("Date"),
                        })

                return IntegrationResult(
                    success=True,
                    data={"messages": messages, "count": len(messages)},
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", {}).get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _get_message(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Get a specific message."""
        message_id = params["message_id"]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "full"},
            )

            if response.status_code == 200:
                data = response.json()
                headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}

                # Get body
                body = ""
                payload = data.get("payload", {})
                if "body" in payload and payload["body"].get("data"):
                    body = base64.urlsafe_b64decode(payload["body"]["data"]).decode()
                elif "parts" in payload:
                    for part in payload["parts"]:
                        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                            body = base64.urlsafe_b64decode(part["body"]["data"]).decode()
                            break

                return IntegrationResult(
                    success=True,
                    data={
                        "id": data.get("id"),
                        "thread_id": data.get("threadId"),
                        "snippet": data.get("snippet"),
                        "from": headers.get("From"),
                        "to": headers.get("To"),
                        "subject": headers.get("Subject"),
                        "date": headers.get("Date"),
                        "body": body,
                        "label_ids": data.get("labelIds", []),
                    },
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", {}).get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _search_messages(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Search messages using Gmail query syntax."""
        query = params["query"]
        max_results = params.get("max_results", 10)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/users/me/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "q": query,
                    "maxResults": max_results,
                },
            )

            if response.status_code == 200:
                data = response.json()
                message_ids = [m["id"] for m in data.get("messages", [])]
                return IntegrationResult(
                    success=True,
                    data={
                        "message_ids": message_ids,
                        "count": len(message_ids),
                        "estimated_total": data.get("resultSizeEstimate", 0),
                    },
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", {}).get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _add_label(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Add labels to a message."""
        message_id = params["message_id"]
        label_ids = params["label_ids"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GMAIL_API_BASE}/users/me/messages/{message_id}/modify",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"addLabelIds": label_ids},
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={"label_ids": data.get("labelIds", [])},
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", {}).get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _mark_as_read(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Mark a message as read."""
        message_id = params["message_id"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GMAIL_API_BASE}/users/me/messages/{message_id}/modify",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"removeLabelIds": ["UNREAD"]},
            )

            if response.status_code == 200:
                return IntegrationResult(success=True, data={"marked_as_read": True})
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", {}).get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _get_labels(self, token: str) -> IntegrationResult:
        """Get all Gmail labels."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/users/me/labels",
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                data = response.json()
                labels = [
                    {
                        "id": label["id"],
                        "name": label["name"],
                        "type": label.get("type"),
                    }
                    for label in data.get("labels", [])
                ]
                return IntegrationResult(
                    success=True,
                    data={"labels": labels, "count": len(labels)},
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", {}).get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )


# OAuth flow helper functions
def get_gmail_oauth_url(state: str, scopes: Optional[List[str]] = None) -> str:
    """Generate the Google OAuth authorization URL."""
    config = GmailIntegration({}, {}).get_oauth_config()
    if not config:
        raise ValueError("Gmail OAuth not configured")

    scope_str = " ".join(scopes or config.scopes)
    return (
        f"{config.authorize_url}"
        f"?client_id={config.client_id}"
        f"&redirect_uri={config.redirect_uri}"
        f"&response_type=code"
        f"&scope={scope_str}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )


async def exchange_gmail_code(code: str) -> Optional[Dict[str, Any]]:
    """Exchange OAuth code for tokens."""
    config = GmailIntegration({}, {}).get_oauth_config()
    if not config:
        return None

    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.token_url,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": config.redirect_uri,
            },
        )
        data = response.json()

        if "access_token" in data:
            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token"),
                "token_type": data.get("token_type", "Bearer"),
                "scope": data.get("scope"),
                "expires_in": data.get("expires_in"),
            }
        else:
            logger.error(f"Gmail OAuth exchange failed: {data.get('error')}")
            return None

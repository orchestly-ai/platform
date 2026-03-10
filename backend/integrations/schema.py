"""
Integration Schema

Pydantic models for declarative integration configuration.
Integrations are defined in YAML files and loaded at runtime.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator


class AuthType(str, Enum):
    """Authentication types supported by integrations."""
    API_KEY = "api_key"
    BOT_TOKEN = "bot_token"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    BEARER = "bearer"
    NONE = "none"


class IntegrationCategory(str, Enum):
    """Categories for organizing integrations."""
    AI = "ai"
    COMMUNICATION = "communication"
    CRM = "crm"
    PROJECT_MANAGEMENT = "project_management"
    DEVELOPER_TOOLS = "developer_tools"
    STORAGE = "storage"
    EMAIL = "email"
    SOCIAL = "social"
    ANALYTICS = "analytics"
    PAYMENTS = "payments"
    CUSTOM = "custom"


class ActionType(str, Enum):
    """How the action is executed."""
    HTTP = "http"  # Simple HTTP request
    SDK = "sdk"    # Custom Python code


class HttpMethod(str, Enum):
    """HTTP methods for API calls."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ParameterType(str, Enum):
    """Parameter data types."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    PASSWORD = "password"  # Hidden input


class TriggerType(str, Enum):
    """How triggers are activated."""
    WEBHOOK = "webhook"
    POLLING = "polling"
    WEBSOCKET = "websocket"


# ============ Auth Configuration ============

class AuthField(BaseModel):
    """A field required for authentication."""
    name: str = Field(..., description="Field identifier")
    label: str = Field(..., description="Display label")
    type: ParameterType = Field(default=ParameterType.STRING)
    required: bool = Field(default=True)
    help: Optional[str] = Field(default=None, description="Help text for user")
    placeholder: Optional[str] = Field(default=None)
    default: Optional[str] = Field(default=None)


class OAuthConfig(BaseModel):
    """OAuth2-specific configuration."""
    provider: str = Field(..., description="Nango provider key or custom")
    scopes: List[str] = Field(default_factory=list)
    authorization_url: Optional[str] = Field(default=None, description="For custom OAuth")
    token_url: Optional[str] = Field(default=None, description="For custom OAuth")


class AuthConfig(BaseModel):
    """Authentication configuration for an integration."""
    type: AuthType = Field(..., description="Authentication type")
    fields: List[AuthField] = Field(default_factory=list, description="Required auth fields")
    oauth: Optional[OAuthConfig] = Field(default=None, description="OAuth2 config if applicable")
    header_name: Optional[str] = Field(default=None, description="Custom auth header name")
    header_prefix: Optional[str] = Field(default=None, description="e.g., 'Bearer', 'Bot'")

    @validator('fields', always=True)
    def set_default_fields(cls, v, values):
        """Set default fields based on auth type."""
        if not v and 'type' in values:
            auth_type = values['type']
            if auth_type == AuthType.API_KEY:
                return [AuthField(
                    name="api_key",
                    label="API Key",
                    type=ParameterType.PASSWORD,
                    required=True
                )]
            elif auth_type == AuthType.BOT_TOKEN:
                return [AuthField(
                    name="bot_token",
                    label="Bot Token",
                    type=ParameterType.PASSWORD,
                    required=True
                )]
        return v


# ============ Action Configuration ============

class ActionParameter(BaseModel):
    """A parameter for an action."""
    name: str = Field(..., description="Parameter identifier")
    label: Optional[str] = Field(default=None, description="Display label")
    type: ParameterType = Field(default=ParameterType.STRING)
    required: bool = Field(default=False)
    default: Optional[Any] = Field(default=None)
    description: Optional[str] = Field(default=None)
    supports_templates: bool = Field(default=True, description="Allow {{variable}} syntax")
    enum: Optional[List[str]] = Field(default=None, description="Allowed values")

    @validator('label', always=True)
    def default_label(cls, v, values):
        if not v and 'name' in values:
            # Convert snake_case to Title Case
            return values['name'].replace('_', ' ').title()
        return v


class ResponseMapping(BaseModel):
    """Map response data to output fields."""
    # Key is output field name, value is JSONPath expression
    mappings: Dict[str, str] = Field(default_factory=dict)


class HttpActionConfig(BaseModel):
    """Configuration for HTTP-based actions."""
    method: HttpMethod = Field(default=HttpMethod.POST)
    url: str = Field(..., description="URL with {{}} placeholders")
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = Field(default=None)
    query_params: Optional[Dict[str, str]] = Field(default=None)
    response_type: str = Field(default="json", description="json, text, binary")
    success_codes: List[int] = Field(default=[200, 201, 204])


class SdkActionConfig(BaseModel):
    """Configuration for SDK-based actions."""
    handler: str = Field(..., description="Python path: module.function")
    async_handler: bool = Field(default=True)


class ActionConfig(BaseModel):
    """Configuration for a single action."""
    name: str = Field(..., description="Action identifier")
    display_name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    type: ActionType = Field(default=ActionType.HTTP)

    # Parameters
    parameters: List[ActionParameter] = Field(default_factory=list)

    # HTTP config (when type=http)
    http: Optional[HttpActionConfig] = Field(default=None)

    # SDK config (when type=sdk)
    sdk: Optional[SdkActionConfig] = Field(default=None)

    # Response mapping
    response: Optional[ResponseMapping] = Field(default=None)

    # Rate limiting
    rate_limit: Optional[int] = Field(default=None, description="Max calls per minute")

    @validator('display_name', always=True)
    def default_display_name(cls, v, values):
        if not v and 'name' in values:
            return values['name'].replace('_', ' ').title()
        return v


# ============ Trigger Configuration ============

class TriggerConfig(BaseModel):
    """Configuration for a trigger."""
    name: str = Field(..., description="Trigger identifier")
    display_name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    type: TriggerType = Field(default=TriggerType.WEBHOOK)

    # Webhook config
    webhook_path: Optional[str] = Field(default=None, description="Path for webhook endpoint")

    # Polling config
    polling_interval: Optional[int] = Field(default=None, description="Seconds between polls")
    polling_endpoint: Optional[str] = Field(default=None)

    # Output schema
    output_fields: List[ActionParameter] = Field(default_factory=list)


# ============ Main Integration Config ============

class IntegrationConfig(BaseModel):
    """
    Complete configuration for an integration.

    This is the root schema that YAML files are validated against.
    """
    # Identity
    id: str = Field(..., description="Unique identifier (slug)")
    name: str = Field(..., description="Display name")
    display_name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    long_description: Optional[str] = Field(default=None)

    # Classification
    category: IntegrationCategory = Field(default=IntegrationCategory.CUSTOM)
    tags: List[str] = Field(default_factory=list)

    # Visuals
    icon_url: Optional[str] = Field(default=None)
    color: Optional[str] = Field(default=None, description="Brand color hex")

    # Authentication
    auth: AuthConfig = Field(..., description="Authentication configuration")

    # Actions
    actions: Dict[str, ActionConfig] = Field(default_factory=dict)

    # Triggers
    triggers: Dict[str, TriggerConfig] = Field(default_factory=dict)

    # Metadata
    version: str = Field(default="1.0.0")
    documentation_url: Optional[str] = Field(default=None)
    homepage_url: Optional[str] = Field(default=None)

    # Feature flags
    is_enabled: bool = Field(default=True)
    requires_oauth: bool = Field(default=False)
    supports_test_connection: bool = Field(default=True)

    @validator('display_name', always=True)
    def default_display_name(cls, v, values):
        if not v and 'name' in values:
            return values['name']
        return v

    @validator('requires_oauth', always=True)
    def check_oauth(cls, v, values):
        if 'auth' in values and values['auth'].type == AuthType.OAUTH2:
            return True
        return v

    def get_action(self, action_name: str) -> Optional[ActionConfig]:
        """Get an action by name."""
        return self.actions.get(action_name)

    def get_auth_fields(self) -> List[AuthField]:
        """Get required auth fields."""
        return self.auth.fields

    def is_oauth(self) -> bool:
        """Check if this integration uses OAuth."""
        return self.auth.type == AuthType.OAUTH2


# ============ Runtime Models ============

class IntegrationCredentials(BaseModel):
    """Credentials for an integration instance."""
    integration_id: str
    auth_type: AuthType
    data: Dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def api_key(self) -> Optional[str]:
        return self.data.get('api_key')

    @property
    def bot_token(self) -> Optional[str]:
        return self.data.get('bot_token')

    @property
    def access_token(self) -> Optional[str]:
        return self.data.get('access_token')


class ActionExecutionRequest(BaseModel):
    """Request to execute an action."""
    integration_id: str
    action_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    credentials: Optional[IntegrationCredentials] = Field(default=None)


class ActionExecutionResult(BaseModel):
    """Result of action execution."""
    success: bool
    data: Optional[Dict[str, Any]] = Field(default=None)
    error: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None)
    duration_ms: float = Field(default=0)
    raw_response: Optional[Dict[str, Any]] = Field(default=None)

#!/usr/bin/env python3
"""
Integration CLI Tool

Generate and manage integration YAML configurations.

Usage:
    python -m backend.integrations.cli generate
    python -m backend.integrations.cli validate <config_file>
    python -m backend.integrations.cli list
    python -m backend.integrations.cli test <integration_id>
"""

import argparse
import os
import sys
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.integrations.schema import (
    IntegrationConfig,
    IntegrationCategory,
    AuthType,
    ParameterType,
)
from backend.integrations.registry import IntegrationRegistry

CONFIGS_DIR = Path(__file__).parent / "configs"

# Template for common API patterns
TEMPLATES = {
    "api_key_rest": {
        "auth_type": "api_key",
        "description": "REST API with API key authentication",
        "example_actions": ["list", "get", "create", "update", "delete"],
    },
    "oauth2_rest": {
        "auth_type": "oauth2",
        "description": "REST API with OAuth2 authentication",
        "example_actions": ["list", "get", "create", "update", "delete"],
    },
    "bot_token": {
        "auth_type": "bot_token",
        "description": "Bot/App token authentication (Discord, Telegram)",
        "example_actions": ["send_message", "get_channel", "list_members"],
    },
}


class IntegrationGenerator:
    """Interactive generator for integration YAML configs."""

    def __init__(self):
        self.config: Dict[str, Any] = {}

    def prompt(self, message: str, default: Optional[str] = None, required: bool = True) -> str:
        """Prompt user for input."""
        if default:
            message = f"{message} [{default}]"
        message = f"{message}: "

        while True:
            value = input(message).strip()
            if not value and default:
                return default
            if not value and required:
                print("  This field is required.")
                continue
            return value

    def prompt_choice(self, message: str, choices: List[str], default: Optional[str] = None) -> str:
        """Prompt user to select from choices."""
        print(f"\n{message}")
        for i, choice in enumerate(choices, 1):
            marker = " (default)" if choice == default else ""
            print(f"  {i}. {choice}{marker}")

        while True:
            value = input("Enter number or value: ").strip()
            if not value and default:
                return default
            if value.isdigit() and 1 <= int(value) <= len(choices):
                return choices[int(value) - 1]
            if value in choices:
                return value
            print(f"  Please enter 1-{len(choices)} or a valid choice.")

    def prompt_bool(self, message: str, default: bool = True) -> bool:
        """Prompt for yes/no."""
        yn = "[Y/n]" if default else "[y/N]"
        value = input(f"{message} {yn}: ").strip().lower()
        if not value:
            return default
        return value in ('y', 'yes', 'true', '1')

    def generate_interactive(self) -> Dict[str, Any]:
        """Generate config interactively."""
        print("\n" + "=" * 60)
        print("  Integration YAML Generator")
        print("=" * 60)

        # Basic info
        print("\n--- Basic Information ---")
        self.config["id"] = self.prompt("Integration ID (lowercase, no spaces)", required=True)
        self.config["name"] = self.prompt("Internal name", default=self.config["id"])
        self.config["display_name"] = self.prompt("Display name", default=self.config["id"].replace("_", " ").title())
        self.config["description"] = self.prompt("Description", required=True)

        # Category
        categories = [c.value for c in IntegrationCategory]
        self.config["category"] = self.prompt_choice("Select category:", categories, default="custom")

        # Version and URLs
        self.config["version"] = self.prompt("Version", default="1.0.0")
        self.config["icon_url"] = self.prompt("Icon URL", required=False) or None
        self.config["documentation_url"] = self.prompt("Documentation URL", required=False) or None

        # Authentication
        print("\n--- Authentication ---")
        auth_types = [t.value for t in AuthType]
        auth_type = self.prompt_choice("Select auth type:", auth_types, default="api_key")

        self.config["auth"] = self._generate_auth_config(auth_type)

        # Actions
        print("\n--- Actions ---")
        self.config["actions"] = {}

        while True:
            action = self._generate_action()
            if action:
                self.config["actions"][action["name"]] = action
                print(f"  Added action: {action['name']}")

            if not self.prompt_bool("\nAdd another action?", default=True):
                break

        return self.config

    def _generate_auth_config(self, auth_type: str) -> Dict[str, Any]:
        """Generate auth configuration."""
        auth = {"type": auth_type, "fields": []}

        if auth_type == "api_key":
            field_name = self.prompt("API key field name", default="api_key")
            field_label = self.prompt("API key label", default="API Key")
            help_text = self.prompt("Help text (where to get the key)", required=False)

            auth["fields"] = [{
                "name": field_name,
                "label": field_label,
                "type": "password",
                "required": True,
            }]
            if help_text:
                auth["fields"][0]["help"] = help_text

        elif auth_type == "bot_token":
            auth["fields"] = [{
                "name": "bot_token",
                "label": "Bot Token",
                "type": "password",
                "required": True,
            }]

        elif auth_type == "oauth2":
            provider = self.prompt("Nango provider key", default=self.config["id"])
            scopes = self.prompt("OAuth scopes (comma-separated)", required=False)

            auth["oauth"] = {
                "provider": provider,
                "scopes": [s.strip() for s in scopes.split(",")] if scopes else [],
            }

        return auth

    def _generate_action(self) -> Optional[Dict[str, Any]]:
        """Generate a single action configuration."""
        print("\n  -- New Action --")
        name = self.prompt("  Action name (snake_case)")
        if not name:
            return None

        action = {
            "name": name,
            "display_name": self.prompt("  Display name", default=name.replace("_", " ").title()),
            "description": self.prompt("  Description", required=False),
            "type": "http",
        }

        # HTTP config
        print("\n  -- HTTP Configuration --")
        method = self.prompt_choice("  HTTP method:", ["GET", "POST", "PUT", "PATCH", "DELETE"], default="GET")
        url = self.prompt("  API URL (use {{auth.xxx}} and {{parameters.xxx}} for variables)")

        action["http"] = {
            "method": method,
            "url": url,
            "headers": {},
        }

        # Auth header
        if self.config["auth"]["type"] == "api_key":
            header_style = self.prompt_choice(
                "  Authorization header style:",
                ["Bearer {{auth.api_key}}", "Basic {{auth.api_key}}", "X-API-Key: {{auth.api_key}}", "Custom"],
                default="Bearer {{auth.api_key}}"
            )
            if header_style == "Custom":
                header_name = self.prompt("  Header name", default="Authorization")
                header_value = self.prompt("  Header value template")
                action["http"]["headers"][header_name] = header_value
            elif header_style.startswith("X-API-Key"):
                action["http"]["headers"]["X-API-Key"] = "{{auth.api_key}}"
            else:
                action["http"]["headers"]["Authorization"] = header_style

        # Body for POST/PUT/PATCH
        if method in ["POST", "PUT", "PATCH"]:
            content_type = self.prompt_choice(
                "  Content-Type:",
                ["application/json", "application/x-www-form-urlencoded"],
                default="application/json"
            )
            action["http"]["headers"]["Content-Type"] = content_type

            if self.prompt_bool("  Add request body fields?", default=True):
                action["http"]["body"] = {}
                while True:
                    field = self.prompt("    Body field name (empty to finish)", required=False)
                    if not field:
                        break
                    value = self.prompt(f"    Value for {field} (use {{{{parameters.xxx}}}})")
                    action["http"]["body"][field] = value

        # Query params for GET
        if method == "GET" and self.prompt_bool("  Add query parameters?", default=False):
            action["http"]["query_params"] = {}
            while True:
                param = self.prompt("    Query param name (empty to finish)", required=False)
                if not param:
                    break
                value = self.prompt(f"    Value for {param}")
                action["http"]["query_params"][param] = value

        # Parameters
        action["parameters"] = []
        if self.prompt_bool("  Add action parameters?", default=True):
            while True:
                param = self._generate_parameter()
                if not param:
                    break
                action["parameters"].append(param)

        return action

    def _generate_parameter(self) -> Optional[Dict[str, Any]]:
        """Generate a single parameter."""
        name = self.prompt("    Parameter name (empty to finish)", required=False)
        if not name:
            return None

        param_types = [t.value for t in ParameterType]

        return {
            "name": name,
            "label": self.prompt("    Label", default=name.replace("_", " ").title()),
            "type": self.prompt_choice("    Type:", param_types, default="string"),
            "required": self.prompt_bool("    Required?", default=True),
            "description": self.prompt("    Description", required=False) or None,
        }

    def save_config(self, config: Dict[str, Any], filename: Optional[str] = None) -> Path:
        """Save configuration to YAML file."""
        if not filename:
            filename = f"{config['id']}.yaml"

        filepath = CONFIGS_DIR / filename

        # Clean up None values
        config = self._clean_config(config)

        with open(filepath, 'w') as f:
            f.write(f"# {config['display_name']} Integration\n")
            f.write(f"# Generated by Integration CLI\n\n")
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        return filepath

    def _clean_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Remove None values and empty dicts/lists."""
        if isinstance(config, dict):
            return {
                k: self._clean_config(v)
                for k, v in config.items()
                if v is not None and v != {} and v != []
            }
        elif isinstance(config, list):
            return [self._clean_config(v) for v in config if v is not None]
        return config


def cmd_generate(args):
    """Generate a new integration config."""
    generator = IntegrationGenerator()

    if args.template:
        if args.template not in TEMPLATES:
            print(f"Unknown template: {args.template}")
            print(f"Available templates: {', '.join(TEMPLATES.keys())}")
            return 1
        # Use template as starting point
        print(f"Using template: {args.template}")
        print(f"  {TEMPLATES[args.template]['description']}")

    try:
        config = generator.generate_interactive()
        filepath = generator.save_config(config)
        print(f"\nConfig saved to: {filepath}")
        print("\nNext steps:")
        print(f"  1. Edit {filepath} to refine the configuration")
        print(f"  2. Run: python -m backend.integrations.cli validate {filepath}")
        print(f"  3. Test: python -m backend.integrations.cli test {config['id']}")
        return 0
    except KeyboardInterrupt:
        print("\n\nGeneration cancelled.")
        return 1


def cmd_validate(args):
    """Validate an integration config."""
    filepath = Path(args.config_file)

    if not filepath.exists():
        # Try in configs directory
        filepath = CONFIGS_DIR / args.config_file
        if not filepath.exists():
            filepath = CONFIGS_DIR / f"{args.config_file}.yaml"

    if not filepath.exists():
        print(f"Config file not found: {args.config_file}")
        return 1

    print(f"Validating: {filepath}")

    try:
        with open(filepath) as f:
            config_data = yaml.safe_load(f)

        # Validate with Pydantic
        config = IntegrationConfig(**config_data)

        print(f"  ID: {config.id}")
        print(f"  Name: {config.display_name}")
        print(f"  Auth: {config.auth.type.value}")
        print(f"  Actions: {len(config.actions)}")
        for action_name, action in config.actions.items():
            print(f"    - {action_name}: {action.type.value}")
        print(f"  Triggers: {len(config.triggers)}")

        print("\nValidation: PASSED")
        return 0

    except yaml.YAMLError as e:
        print(f"\nYAML Error: {e}")
        return 1
    except Exception as e:
        print(f"\nValidation Error: {e}")
        return 1


def cmd_list(args):
    """List all integration configs."""
    registry = IntegrationRegistry()
    registry.load_all()

    integrations = registry.list_all()

    if not integrations:
        print("No integrations found.")
        return 0

    print(f"\nFound {len(integrations)} integrations:\n")
    print(f"{'ID':<20} {'Name':<25} {'Auth':<12} {'Actions':<8} {'Category':<15}")
    print("-" * 80)

    for integration in sorted(integrations, key=lambda x: x.id):
        print(f"{integration.id:<20} {integration.display_name:<25} {integration.auth.type.value:<12} {len(integration.actions):<8} {integration.category.value:<15}")

    return 0


def cmd_test(args):
    """Test an integration with credentials."""
    import asyncio

    registry = IntegrationRegistry()
    registry.load_all()

    integration = registry.get(args.integration_id)
    if not integration:
        print(f"Integration not found: {args.integration_id}")
        return 1

    print(f"\nTesting: {integration.display_name}")
    print(f"Auth type: {integration.auth.type.value}")

    # Collect credentials
    credentials = {}
    for field in integration.auth.fields:
        if field.type == ParameterType.PASSWORD:
            import getpass
            value = getpass.getpass(f"{field.label}: ")
        else:
            value = input(f"{field.label}: ")
        credentials[field.name] = value

    # Import here to avoid circular imports
    from backend.integrations.http_executor import test_connection
    from backend.integrations.schema import IntegrationCredentials

    creds = IntegrationCredentials(
        integration_id=integration.id,
        auth_type=integration.auth.type,
        data=credentials
    )

    print("\nTesting connection...")
    result = asyncio.run(test_connection(integration, creds))

    if result.success:
        print(f"Connection successful! ({result.duration_ms:.0f}ms)")
        if result.data:
            print(f"Response: {result.data}")
    else:
        print(f"Connection failed: {result.error}")
        if result.error_code:
            print(f"Error code: {result.error_code}")

    return 0 if result.success else 1


def cmd_from_openapi(args):
    """Generate integration config from OpenAPI spec."""
    import json

    spec_path = Path(args.spec_file)
    if not spec_path.exists():
        print(f"OpenAPI spec not found: {args.spec_file}")
        return 1

    print(f"Parsing OpenAPI spec: {spec_path}")

    with open(spec_path) as f:
        if spec_path.suffix in ['.yaml', '.yml']:
            spec = yaml.safe_load(f)
        else:
            spec = json.load(f)

    # Extract basic info
    info = spec.get('info', {})
    integration_id = args.id or info.get('title', 'api').lower().replace(' ', '_')

    config = {
        "id": integration_id,
        "name": integration_id,
        "display_name": info.get('title', integration_id),
        "description": info.get('description', ''),
        "version": info.get('version', '1.0.0'),
        "category": "custom",
        "auth": {
            "type": "api_key",
            "fields": [{
                "name": "api_key",
                "label": "API Key",
                "type": "password",
                "required": True,
            }]
        },
        "actions": {}
    }

    # Extract servers
    servers = spec.get('servers', [])
    base_url = servers[0]['url'] if servers else 'https://api.example.com'

    # Extract paths
    paths = spec.get('paths', {})
    action_count = 0

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method not in ['get', 'post', 'put', 'patch', 'delete']:
                continue

            operation_id = operation.get('operationId', f"{method}_{path.replace('/', '_')}")
            action_name = operation_id.lower().replace('-', '_')

            action = {
                "name": action_name,
                "display_name": operation.get('summary', action_name.replace('_', ' ').title()),
                "description": operation.get('description', ''),
                "type": "http",
                "http": {
                    "method": method.upper(),
                    "url": f"{base_url}{path}",
                    "headers": {
                        "Authorization": "Bearer {{auth.api_key}}"
                    }
                },
                "parameters": []
            }

            # Extract parameters
            for param in operation.get('parameters', []):
                param_config = {
                    "name": param['name'],
                    "label": param['name'].replace('_', ' ').title(),
                    "type": _openapi_type_to_param_type(param.get('schema', {}).get('type', 'string')),
                    "required": param.get('required', False),
                    "description": param.get('description', ''),
                }
                action["parameters"].append(param_config)

                # Update URL or add query params
                if param['in'] == 'path':
                    action["http"]["url"] = action["http"]["url"].replace(
                        f"{{{param['name']}}}",
                        f"{{{{parameters.{param['name']}}}}}"
                    )
                elif param['in'] == 'query':
                    if "query_params" not in action["http"]:
                        action["http"]["query_params"] = {}
                    action["http"]["query_params"][param['name']] = f"{{{{parameters.{param['name']}}}}}"

            config["actions"][action_name] = action
            action_count += 1

    print(f"Generated {action_count} actions from {len(paths)} paths")

    # Save
    generator = IntegrationGenerator()
    filepath = generator.save_config(config)
    print(f"Saved to: {filepath}")

    return 0


def _openapi_type_to_param_type(openapi_type: str) -> str:
    """Convert OpenAPI type to our parameter type."""
    mapping = {
        'string': 'string',
        'integer': 'integer',
        'number': 'number',
        'boolean': 'boolean',
        'array': 'array',
        'object': 'object',
    }
    return mapping.get(openapi_type, 'string')


def cmd_mock_test(args):
    """Run mock tests for an integration (no API calls)."""
    import asyncio

    try:
        from backend.integrations.testing import run_integration_tests, generate_all_test_files
    except ImportError:
        print("Testing framework not available. Install test dependencies.")
        return 1

    if args.all:
        # Generate tests for all integrations
        output_dir = Path(args.output) if args.output else Path("tests/integrations")
        print(f"Generating test files to: {output_dir}")
        generate_all_test_files(output_dir)
        print("\nDone! Run tests with: pytest tests/integrations/")
        return 0

    # Run tests for specific integration
    integration_id = args.integration_id
    if not integration_id:
        print("Please specify an integration ID or use --all")
        return 1

    print(f"\nRunning mock tests for: {integration_id}")
    print("(No actual API calls will be made)")

    result = asyncio.run(run_integration_tests(integration_id, verbose=True))

    if result.failed > 0:
        print(f"\n{result.failed} test(s) failed!")
        return 1

    print(f"\nAll {result.passed} test(s) passed!")
    return 0


def cmd_gen_tests(args):
    """Generate pytest test files for integrations."""
    from pathlib import Path

    try:
        from backend.integrations.testing import IntegrationTestRunner, generate_all_test_files
    except ImportError:
        print("Testing framework not available.")
        return 1

    output_dir = Path(args.output) if args.output else Path("tests/integrations")
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.integration_id:
        # Generate for single integration
        try:
            runner = IntegrationTestRunner(args.integration_id)
            filename = f"test_{args.integration_id}.py"
            runner.generate_test_file(output_dir / filename)
            print(f"Generated: {output_dir / filename}")
        except Exception as e:
            print(f"Error: {e}")
            return 1
    else:
        # Generate for all
        generate_all_test_files(output_dir)

    print(f"\nTest files generated in: {output_dir}")
    print("Run with: pytest tests/integrations/")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Integration CLI - Generate and manage integration YAML configs"
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate a new integration config')
    gen_parser.add_argument('--template', '-t', help='Start from a template (api_key_rest, oauth2_rest, bot_token)')

    # Validate command
    val_parser = subparsers.add_parser('validate', help='Validate an integration config')
    val_parser.add_argument('config_file', help='Path to YAML config file or integration ID')

    # List command
    subparsers.add_parser('list', help='List all integration configs')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test an integration with credentials')
    test_parser.add_argument('integration_id', help='Integration ID to test')

    # From OpenAPI command
    openapi_parser = subparsers.add_parser('from-openapi', help='Generate config from OpenAPI spec')
    openapi_parser.add_argument('spec_file', help='Path to OpenAPI spec (JSON or YAML)')
    openapi_parser.add_argument('--id', help='Integration ID (default: from spec title)')

    # Mock test command (no actual API calls)
    mock_parser = subparsers.add_parser('mock-test', help='Run mock tests (no API calls)')
    mock_parser.add_argument('integration_id', nargs='?', help='Integration ID to test')
    mock_parser.add_argument('--all', action='store_true', help='Generate tests for all integrations')
    mock_parser.add_argument('--output', '-o', help='Output directory for generated tests')

    # Generate test files command
    gen_tests_parser = subparsers.add_parser('gen-tests', help='Generate pytest test files')
    gen_tests_parser.add_argument('integration_id', nargs='?', help='Integration ID (omit for all)')
    gen_tests_parser.add_argument('--output', '-o', default='tests/integrations', help='Output directory')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        'generate': cmd_generate,
        'validate': cmd_validate,
        'list': cmd_list,
        'test': cmd_test,
        'from-openapi': cmd_from_openapi,
        'mock-test': cmd_mock_test,
        'gen-tests': cmd_gen_tests,
    }

    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())

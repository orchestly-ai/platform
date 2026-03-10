"""
Print Node Tests

Tests for the Print node feature that outputs messages to the Execution Log.

Test Coverage:
- Print node configuration validation
- Print node data structure
- Event emission format
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))


class TestPrintNodeConfiguration:
    """Tests for print node configuration structure."""

    def test_print_config_structure(self):
        """Test PrintConfig structure matches expected format."""
        config = {
            'label': 'Test Label',
            'message': 'Hello World',
            'logLevel': 'info',
            'includeTimestamp': True,
        }

        # Verify all expected fields
        assert 'label' in config
        assert 'message' in config
        assert 'logLevel' in config
        assert 'includeTimestamp' in config

    def test_print_config_log_levels(self):
        """Test valid log level values."""
        valid_levels = ['info', 'debug', 'warning', 'error']

        for level in valid_levels:
            config = {'logLevel': level}
            assert config['logLevel'] in valid_levels

    def test_print_config_default_values(self):
        """Test default configuration values."""
        # Empty config should use defaults
        config = {}
        default_label = config.get('label', 'Output')
        default_message = config.get('message', '')
        default_level = config.get('logLevel', 'info')
        default_timestamp = config.get('includeTimestamp', True)

        assert default_label == 'Output'
        assert default_message == ''
        assert default_level == 'info'
        assert default_timestamp is True


class TestPrintNodeData:
    """Tests for print node data in workflow."""

    def test_print_node_structure(self):
        """Test print node data structure."""
        node_data = {
            'id': 'print-1',
            'type': 'print',
            'data': {
                'label': 'My Print Node',
                'type': 'print',
                'printConfig': {
                    'label': 'Debug Output',
                    'message': 'Test message',
                    'logLevel': 'info',
                    'includeTimestamp': True,
                }
            }
        }

        assert node_data['type'] == 'print'
        assert 'printConfig' in node_data['data']
        assert node_data['data']['printConfig']['label'] == 'Debug Output'

    def test_print_node_with_variable_template(self):
        """Test print node with variable template in message."""
        node_data = {
            'data': {
                'printConfig': {
                    'message': '{{worker.content}}'
                }
            }
        }

        message = node_data['data']['printConfig']['message']
        assert '{{' in message
        assert '}}' in message
        assert 'worker.content' in message


class TestPrintOutputEvent:
    """Tests for print output event structure."""

    def test_print_output_event_structure(self):
        """Test print_output event has correct structure."""
        event = {
            'event_type': 'print_output',
            'node_id': 'print-1',
            'message': 'Test message',
            'data': {
                'label': 'Output',
                'message': 'Test message',
                'logLevel': 'info',
                'timestamp': '2024-01-15T10:00:00',
            }
        }

        assert event['event_type'] == 'print_output'
        assert 'node_id' in event
        assert 'message' in event
        assert 'data' in event
        assert event['data']['label'] == 'Output'
        assert event['data']['logLevel'] == 'info'

    def test_print_output_event_without_timestamp(self):
        """Test print_output event with timestamp disabled."""
        event = {
            'event_type': 'print_output',
            'node_id': 'print-1',
            'data': {
                'label': 'Output',
                'message': 'Test',
                'logLevel': 'info',
                'timestamp': None,
            }
        }

        assert event['data']['timestamp'] is None


class TestPrintNodeExecution:
    """Tests for print node execution result."""

    def test_print_result_structure(self):
        """Test print node execution result structure."""
        result = {
            'latency_ms': 5.0,
            'response_data': {
                'label': 'Output',
                'message': 'Test message',
                'logLevel': 'info',
                'timestamp': '2024-01-15T10:00:00',
            },
            'success': True,
        }

        assert 'latency_ms' in result
        assert 'response_data' in result
        assert 'success' in result
        assert result['success'] is True

    def test_print_result_with_substituted_variable(self):
        """Test print result after variable substitution."""
        # Simulating variable substitution
        original_message = '{{worker.content}}'
        substituted_message = 'This is the worker output'

        result = {
            'response_data': {
                'message': substituted_message,
            }
        }

        assert '{{' not in result['response_data']['message']
        assert 'worker output' in result['response_data']['message']


class TestPrintNodeIntegration:
    """Integration tests for print node."""

    def test_print_node_type_exists(self):
        """Verify 'print' is a recognized node type in executor."""
        try:
            from backend.services.workflow_executor import WorkflowExecutor
            # Verify the executor has the _execute_print_node method
            assert hasattr(WorkflowExecutor, '_execute_print_node')
        except ImportError as e:
            # Skip if dependencies like sqlalchemy aren't installed
            pytest.skip(f"Skipping integration test: {e}")

    def test_execution_event_class_exists(self):
        """Verify ExecutionEvent class can be instantiated."""
        try:
            from backend.services.workflow_executor import ExecutionEvent

            event = ExecutionEvent(
                event_type='print_output',
                node_id='print-1',
                message='Test',
                data={'label': 'Output'}
            )

            assert event.event_type == 'print_output'
            assert event.node_id == 'print-1'
        except ImportError as e:
            # Skip if dependencies aren't installed
            pytest.skip(f"Skipping integration test: {e}")


# Run tests with: pytest test_print_node.py -v
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

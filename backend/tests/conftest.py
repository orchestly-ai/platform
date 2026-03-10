"""
Pytest configuration for backend tests.

This file handles conditional test skipping based on available dependencies
and ensures the project root is on the Python path so that `from backend.xxx`
imports work correctly.
"""

import os
import sys
from unittest.mock import MagicMock

# Ensure the project root (agent-orchestration/) is on sys.path so tests
# can import `backend.shared.*`, `backend.orchestrator.*`, etc.
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Create mock numpy to prevent import errors in tests that don't actually need it
# This allows test collection to succeed even without numpy installed
if 'numpy' not in sys.modules:
    sys.modules['numpy'] = MagicMock()
    sys.modules['numpy.random'] = MagicMock()
    sys.modules['numpy.linalg'] = MagicMock()

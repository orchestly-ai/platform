"""
Tests for enterprise license gating.

Verifies that:
- License detection works correctly based on ORCHESTLY_LICENSE_KEY env var
- Enterprise feature enforcement raises 403 without a license
- The license status endpoint returns correct information
"""

import os
import pytest
from unittest.mock import patch


class TestLicenseDetection:
    """Tests for ee/license.py functions."""

    def test_has_enterprise_license_with_valid_key(self):
        with patch.dict(os.environ, {"ORCHESTLY_LICENSE_KEY": "orch_ent_test123"}):
            from ee.license import has_enterprise_license
            assert has_enterprise_license() is True

    def test_has_enterprise_license_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            # Need to clear the env var for this test
            env = os.environ.copy()
            env.pop("ORCHESTLY_LICENSE_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                from ee.license import has_enterprise_license
                assert has_enterprise_license() is False

    def test_has_enterprise_license_with_invalid_prefix(self):
        with patch.dict(os.environ, {"ORCHESTLY_LICENSE_KEY": "invalid_key_123"}):
            from ee.license import has_enterprise_license
            assert has_enterprise_license() is False

    def test_get_license_status_community(self):
        env = os.environ.copy()
        env.pop("ORCHESTLY_LICENSE_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            from ee.license import get_license_status
            status = get_license_status()
            assert status["edition"] == "community"
            assert status["licensed"] is False

    def test_get_license_status_enterprise(self):
        with patch.dict(os.environ, {"ORCHESTLY_LICENSE_KEY": "orch_ent_test_license_key_12345"}):
            from ee.license import get_license_status
            status = get_license_status()
            assert status["edition"] == "enterprise"
            assert status["licensed"] is True
            assert "key_hint" in status
            # Verify key is masked
            assert "test_license_key_12345" not in status["key_hint"]


class TestEnforceEnterpriseFeature:
    """Tests for enforce_enterprise_feature in plan_enforcement."""

    def test_enforce_enterprise_feature_raises_without_license(self):
        from fastapi import HTTPException
        env = os.environ.copy()
        env.pop("ORCHESTLY_LICENSE_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            # Reload to pick up the env change
            with patch("backend.shared.plan_enforcement.has_enterprise_license", return_value=False):
                from backend.shared.plan_enforcement import enforce_enterprise_feature
                with pytest.raises(HTTPException) as exc_info:
                    enforce_enterprise_feature("sso_saml")
                assert exc_info.value.status_code == 403
                assert exc_info.value.detail["error"] == "enterprise_required"

    def test_enforce_enterprise_feature_passes_with_license(self):
        with patch("backend.shared.plan_enforcement.has_enterprise_license", return_value=True):
            from backend.shared.plan_enforcement import enforce_enterprise_feature
            # Should not raise
            enforce_enterprise_feature("sso_saml")


class TestEnterpriseFeaturesList:
    """Tests for ENTERPRISE_FEATURES list in rbac_models."""

    def test_enterprise_features_contains_expected(self):
        from backend.shared.rbac_models import ENTERPRISE_FEATURES
        expected = [
            "sso_saml", "hipaa_compliance", "advanced_audit", "byoc",
            "multi_cloud", "white_label", "ab_testing", "time_travel",
            "advanced_supervisor", "ml_optimization", "cost_forecasting",
            "advanced_hitl", "custom_rbac", "advanced_analytics",
            "security_scanning", "marketplace_publishing",
        ]
        assert ENTERPRISE_FEATURES == expected

    def test_paid_features_alias(self):
        from backend.shared.rbac_models import PAID_FEATURES, ENTERPRISE_FEATURES
        assert PAID_FEATURES is ENTERPRISE_FEATURES

    def test_community_plan_limits_raised(self):
        from backend.shared.rbac_models import PLAN_LIMITS
        community = PLAN_LIMITS["community"]
        assert community["max_users"] == 5
        assert community["max_agents"] == 50
        assert community["max_workflows"] == 100

"""Tests for HMAC-SHA256 bundle signing and verification."""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
from unittest.mock import MagicMock

import pytest

from prefect.bundles import (
    SerializedBundle,
    _get_bundle_signing_key,
    _sign_bundle,
    _verify_bundle_signature,
    create_bundle_for_flow_run,
)
from prefect.flows import flow


def _make_unsigned_bundle() -> SerializedBundle:
    """Create a minimal unsigned bundle for testing."""
    return {
        "function": "dW51c2Vk",
        "context": "dW51c2Vk",
        "flow_run": {"id": "test-run"},
        "dependencies": "requests>=2.0",
    }


class TestGetBundleSigningKey:
    """Tests for _get_bundle_signing_key."""

    def test_returns_empty_bytes_when_unset(self, monkeypatch):
        monkeypatch.delenv("PREFECT_BUNDLE_SIGNING_KEY", raising=False)
        assert _get_bundle_signing_key() == b""

    def test_returns_encoded_key_when_set(self, monkeypatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "mysecret")
        assert _get_bundle_signing_key() == b"mysecret"


class TestSignBundle:
    """Tests for _sign_bundle."""

    def test_noop_without_key(self, monkeypatch):
        monkeypatch.delenv("PREFECT_BUNDLE_SIGNING_KEY", raising=False)
        bundle = _make_unsigned_bundle()
        _sign_bundle(bundle)
        assert "signature" not in bundle

    def test_adds_signature_with_key(self, monkeypatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "testsecret")
        bundle = _make_unsigned_bundle()
        _sign_bundle(bundle)
        assert "signature" in bundle
        assert isinstance(bundle["signature"], str)
        assert len(bundle["signature"]) == 64  # SHA256 hex digest

    def test_signature_covers_all_fields(self, monkeypatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "testsecret")
        bundle = _make_unsigned_bundle()
        _sign_bundle(bundle)

        # Manually compute expected signature
        content = {k: v for k, v in bundle.items() if k != "signature"}
        payload = json.dumps(content, sort_keys=True).encode("utf-8")
        expected = hmac_mod.new(b"testsecret", payload, hashlib.sha256).hexdigest()
        assert bundle["signature"] == expected

    def test_signature_changes_when_dependencies_modified(self, monkeypatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "testsecret")
        bundle1 = _make_unsigned_bundle()
        _sign_bundle(bundle1)

        bundle2 = _make_unsigned_bundle()
        bundle2["dependencies"] = "malicious-package"
        _sign_bundle(bundle2)

        assert bundle1["signature"] != bundle2["signature"]


class TestVerifyBundleSignature:
    """Tests for _verify_bundle_signature."""

    def test_noop_without_key(self, monkeypatch):
        monkeypatch.delenv("PREFECT_BUNDLE_SIGNING_KEY", raising=False)
        bundle = _make_unsigned_bundle()
        _verify_bundle_signature(bundle)  # Should not raise

    def test_rejects_unsigned_bundle_when_key_set(self, monkeypatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "testsecret")
        bundle = _make_unsigned_bundle()
        with pytest.raises(ValueError, match="unsigned bundle rejected"):
            _verify_bundle_signature(bundle)

    def test_accepts_correctly_signed_bundle(self, monkeypatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "testsecret")
        bundle = _make_unsigned_bundle()
        _sign_bundle(bundle)
        _verify_bundle_signature(bundle)  # Should not raise

    def test_rejects_tampered_bundle(self, monkeypatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "testsecret")
        bundle = _make_unsigned_bundle()
        _sign_bundle(bundle)
        bundle["dependencies"] = "malicious-package"
        with pytest.raises(ValueError, match="HMAC mismatch"):
            _verify_bundle_signature(bundle)

    def test_rejects_wrong_key(self, monkeypatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "key1")
        bundle = _make_unsigned_bundle()
        _sign_bundle(bundle)
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "key2")
        with pytest.raises(ValueError, match="HMAC mismatch"):
            _verify_bundle_signature(bundle)


class TestBundleSigningIntegration:
    """Integration tests for bundle signing in create_bundle_for_flow_run."""

    def test_create_bundle_adds_signature_when_key_set(self, monkeypatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SIGNING_KEY", "integration-test-key")
        import prefect.bundles as bundles_module

        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"prefect>=3.0.0\n",
        )

        @flow
        def my_flow():
            return "hello"

        mock_flow_run = MagicMock()
        mock_flow_run.model_dump.return_value = {"id": "test-id"}

        result = create_bundle_for_flow_run(my_flow, mock_flow_run)
        assert "signature" in result["bundle"]
        assert isinstance(result["bundle"]["signature"], str)

    def test_create_bundle_no_signature_without_key(self, monkeypatch):
        monkeypatch.delenv("PREFECT_BUNDLE_SIGNING_KEY", raising=False)
        import prefect.bundles as bundles_module

        monkeypatch.setattr(
            bundles_module.subprocess,
            "check_output",
            lambda *args, **kwargs: b"",
        )

        @flow
        def my_flow():
            return "hello"

        mock_flow_run = MagicMock()
        mock_flow_run.model_dump.return_value = {"id": "test-id"}

        result = create_bundle_for_flow_run(my_flow, mock_flow_run)
        assert "signature" not in result["bundle"]

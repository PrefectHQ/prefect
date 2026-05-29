"""Tests for bundle HMAC signature security."""

import json
import os
import warnings
from unittest.mock import patch

import pytest

from prefect.bundles import (
    SecurityError,
    _compute_bundle_signature,
    _deserialize_bundle_object,
    _get_bundle_secret,
    _serialize_bundle_object,
)


class TestGetBundleSecret:
    def test_returns_none_when_env_var_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("PREFECT_BUNDLE_SECRET", raising=False)
        assert _get_bundle_secret() is None

    def test_returns_bytes_when_env_var_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "my-secret-key")
        assert _get_bundle_secret() == b"my-secret-key"


class TestSerializeBundleObject:
    def test_legacy_format_without_secret(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("PREFECT_BUNDLE_SECRET", raising=False)
        obj = {"key": "value"}
        serialized = _serialize_bundle_object(obj)

        # Should be a plain base64 string, not JSON
        assert not serialized.startswith("{")
        # Should round-trip
        deserialized = _deserialize_bundle_object(serialized)
        assert deserialized == obj

    def test_signed_format_with_secret(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "my-secret-key")
        obj = {"key": "value"}
        serialized = _serialize_bundle_object(obj)

        # Should be a JSON string with version, payload, and signature
        data = json.loads(serialized)
        assert data["v"] == "prefect-bundle-sig-v1"
        assert "p" in data
        assert "s" in data
        assert isinstance(data["s"], str)
        assert len(data["s"]) == 64  # hex-encoded SHA256

    def test_different_secrets_produce_different_signatures(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        obj = {"key": "value"}

        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "secret-a")
        serialized_a = _serialize_bundle_object(obj)

        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "secret-b")
        serialized_b = _serialize_bundle_object(obj)

        data_a = json.loads(serialized_a)
        data_b = json.loads(serialized_b)

        # Same payload but different signatures
        assert data_a["p"] == data_b["p"]
        assert data_a["s"] != data_b["s"]


class TestDeserializeBundleObject:
    def test_deserialize_signed_with_correct_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "my-secret-key")
        obj = {"key": "value"}
        serialized = _serialize_bundle_object(obj)

        deserialized = _deserialize_bundle_object(serialized)
        assert deserialized == obj

    def test_deserialize_signed_with_wrong_secret_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "correct-secret")
        obj = {"key": "value"}
        serialized = _serialize_bundle_object(obj)

        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "wrong-secret")
        with pytest.raises(SecurityError, match="signature verification failed"):
            _deserialize_bundle_object(serialized)

    def test_deserialize_signed_without_secret_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "my-secret-key")
        obj = {"key": "value"}
        serialized = _serialize_bundle_object(obj)

        monkeypatch.delenv("PREFECT_BUNDLE_SECRET", raising=False)
        with pytest.raises(
            SecurityError, match="no PREFECT_BUNDLE_SECRET is configured"
        ):
            _deserialize_bundle_object(serialized)

    def test_deserialize_legacy_emits_warning_without_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv("PREFECT_BUNDLE_SECRET", raising=False)
        obj = {"key": "value"}
        # Create a legacy-format serialized object directly
        import base64
        import gzip
        import cloudpickle

        legacy = base64.b64encode(gzip.compress(cloudpickle.dumps(obj))).decode()

        with pytest.warns(RuntimeWarning, match="insecure"):
            deserialized = _deserialize_bundle_object(legacy)

        assert deserialized == obj

    def test_deserialize_legacy_emits_warning_with_secret_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "my-secret-key")
        obj = {"key": "value"}
        import base64
        import gzip
        import cloudpickle

        legacy = base64.b64encode(gzip.compress(cloudpickle.dumps(obj))).decode()

        with pytest.warns(RuntimeWarning, match="insecure"):
            deserialized = _deserialize_bundle_object(legacy)

        assert deserialized == obj

    def test_tampered_payload_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "my-secret-key")
        obj = {"key": "value"}
        serialized = _serialize_bundle_object(obj)

        data = json.loads(serialized)
        # Tamper with the payload by changing one character
        data["p"] = data["p"][:-1] + ("A" if data["p"][-1] != "A" else "B")
        tampered = json.dumps(data)

        with pytest.raises(SecurityError, match="signature verification failed"):
            _deserialize_bundle_object(tampered)

    def test_tampered_signature_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "my-secret-key")
        obj = {"key": "value"}
        serialized = _serialize_bundle_object(obj)

        data = json.loads(serialized)
        # Tamper with the signature by changing one character
        data["s"] = data["s"][:-1] + ("0" if data["s"][-1] != "0" else "1")
        tampered = json.dumps(data)

        with pytest.raises(SecurityError, match="signature verification failed"):
            _deserialize_bundle_object(tampered)

    def test_malformed_signed_bundle_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("PREFECT_BUNDLE_SECRET", "my-secret-key")

        # Missing payload and signature keys
        malformed = json.dumps({"v": "prefect-bundle-sig-v1"})

        with pytest.raises(SecurityError, match="Malformed signed bundle"):
            _deserialize_bundle_object(malformed)


class TestComputeBundleSignature:
    def test_deterministic_output(self):
        secret = b"secret"
        payload = b"payload"
        sig1 = _compute_bundle_signature(payload, secret)
        sig2 = _compute_bundle_signature(payload, secret)
        assert sig1 == sig2
        assert len(sig1) == 64

    def test_different_secrets_different_signatures(self):
        payload = b"payload"
        sig1 = _compute_bundle_signature(payload, b"secret1")
        sig2 = _compute_bundle_signature(payload, b"secret2")
        assert sig1 != sig2

    def test_different_payloads_different_signatures(self):
        secret = b"secret"
        sig1 = _compute_bundle_signature(b"payload1", secret)
        sig2 = _compute_bundle_signature(b"payload2", secret)
        assert sig1 != sig2


class TestSecurityError:
    def test_is_exception_subclass(self):
        assert issubclass(SecurityError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(SecurityError, match="test error"):
            raise SecurityError("test error")

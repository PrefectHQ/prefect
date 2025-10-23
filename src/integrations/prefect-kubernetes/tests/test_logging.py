import json
import logging
from typing import Any

from prefect_kubernetes._logging import KopfObjectJsonFormatter


class TestKopfObjectJsonFormatter:
    """Tests for the KopfObjectJsonFormatter"""

    def test_filters_unserializable_kopf_fields(self):
        """
        Test that kopf-specific fields (k8s_skip, k8s_ref, settings) are
        filtered out from the log record.
        """
        formatter = KopfObjectJsonFormatter()

        # Create a log record with kopf-specific fields
        record = logging.LogRecord(
            name="kopf.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add kopf-specific attributes that should be filtered
        record.k8s_skip = True  # type: ignore
        record.k8s_ref = {"kind": "Pod", "name": "test-pod"}  # type: ignore
        record.settings = {"some": "settings"}  # type: ignore

        # Format the record
        formatted = formatter.format(record)
        log_dict = json.loads(formatted)

        # Verify kopf fields are NOT in the output
        assert "k8s_skip" not in log_dict, "k8s_skip should be filtered out"
        assert "settings" not in log_dict, "settings should be filtered out"

    def test_adds_severity_field(self):
        """Test that the formatter adds a severity field with correct values"""
        formatter = KopfObjectJsonFormatter()

        # Test different log levels
        test_cases = [
            (logging.DEBUG, "debug"),
            (logging.INFO, "info"),
            (logging.WARNING, "warn"),
            (logging.ERROR, "error"),
            (logging.CRITICAL, "fatal"),
        ]

        for level, expected_severity in test_cases:
            record = logging.LogRecord(
                name="kopf.test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg=f"Test message at {logging.getLevelName(level)}",
                args=(),
                exc_info=None,
            )

            formatted = formatter.format(record)
            log_dict = json.loads(formatted)

            assert "severity" in log_dict, (
                f"severity field should be present for {logging.getLevelName(level)}"
            )
            assert log_dict["severity"] == expected_severity, (
                f"Expected severity '{expected_severity}' for {logging.getLevelName(level)}, "
                f"got '{log_dict['severity']}'"
            )

    def test_adds_kubernetes_object_reference(self):
        """Test that k8s_ref is added to the output under the 'object' key"""
        formatter = KopfObjectJsonFormatter()

        record = logging.LogRecord(
            name="kopf.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add k8s_ref attribute
        k8s_ref: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "Pod",
            "name": "test-pod",
            "uid": "12345",
            "namespace": "default",
        }
        record.k8s_ref = k8s_ref  # type: ignore

        formatted = formatter.format(record)
        log_dict = json.loads(formatted)

        # Verify the object field contains the k8s_ref
        assert "object" in log_dict, (
            "object field should be present when k8s_ref is set"
        )
        assert log_dict["object"] == k8s_ref, "object field should contain the k8s_ref"

    def test_custom_refkey(self):
        """Test that a custom refkey can be used instead of 'object'"""
        formatter = KopfObjectJsonFormatter(refkey="k8s_resource")

        record = logging.LogRecord(
            name="kopf.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        k8s_ref = {"kind": "Pod", "name": "test-pod"}
        record.k8s_ref = k8s_ref  # type: ignore

        formatted = formatter.format(record)
        log_dict = json.loads(formatted)

        # Verify custom refkey is used
        assert "k8s_resource" in log_dict, "Custom refkey should be present"
        assert log_dict["k8s_resource"] == k8s_ref

    def test_json_output_is_valid(self):
        """Test that the formatter produces valid JSON"""
        formatter = KopfObjectJsonFormatter()

        record = logging.LogRecord(
            name="kopf.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        # Should not raise a JSONDecodeError
        log_dict = json.loads(formatted)

        # Verify expected fields are present
        assert "message" in log_dict, "message field should be present"
        assert "severity" in log_dict, "severity field should be present"
        assert log_dict["message"] == "Test message"

    def test_timestamp_is_included(self):
        """Test that timestamp is included in the output"""
        formatter = KopfObjectJsonFormatter()

        record = logging.LogRecord(
            name="kopf.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        log_dict = json.loads(formatted)

        # The formatter should include a timestamp
        assert "timestamp" in log_dict, "timestamp field should be present"

    def test_log_with_extra_fields(self):
        """Test that extra fields are included in the output"""
        formatter = KopfObjectJsonFormatter()

        record = logging.LogRecord(
            name="kopf.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra custom field
        record.custom_field = "custom_value"  # type: ignore

        formatted = formatter.format(record)
        log_dict = json.loads(formatted)

        # Custom field should be present
        assert "custom_field" in log_dict
        assert log_dict["custom_field"] == "custom_value"

    def test_no_k8s_ref_attribute(self):
        """Test that formatter works correctly when k8s_ref is not present"""
        formatter = KopfObjectJsonFormatter()

        record = logging.LogRecord(
            name="kopf.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Don't set k8s_ref
        formatted = formatter.format(record)
        log_dict = json.loads(formatted)

        # Should work fine, just without the object field
        assert "message" in log_dict
        assert "severity" in log_dict
        # object field should not be present if k8s_ref is not set
        assert "object" not in log_dict or log_dict["object"] is None

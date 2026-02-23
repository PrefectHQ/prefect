from __future__ import annotations

import logging
import sys
from unittest.mock import patch

from prefect.runner._exit_code_interpreter import (
    _STATUS_CONTROL_C_EXIT,
    ExitCodeResult,
    interpret_exit_code,
)


class TestExitCodeResult:
    def test_dataclass_fields(self):
        result = ExitCodeResult(
            exit_code=1, level=logging.ERROR, help_message=None, is_crash=True
        )
        assert result.exit_code == 1
        assert result.level == logging.ERROR
        assert result.help_message is None
        assert result.is_crash is True

    def test_dataclass_with_help_message(self):
        result = ExitCodeResult(
            exit_code=-9, level=logging.INFO, help_message="killed", is_crash=True
        )
        assert result.help_message == "killed"


class TestInterpretExitCode:
    def test_sigkill_exit_code(self):
        result = interpret_exit_code(-9)
        assert result.exit_code == -9
        assert result.level == logging.INFO
        assert result.is_crash is True
        assert result.help_message is not None
        assert "SIGKILL" in result.help_message

    def test_sigterm_exit_code(self):
        result = interpret_exit_code(-15)
        assert result.exit_code == -15
        assert result.level == logging.INFO
        assert result.is_crash is True
        assert result.help_message is not None
        assert "SIGTERM" in result.help_message

    def test_oom_exit_code_247(self):
        result = interpret_exit_code(247)
        assert result.exit_code == 247
        assert result.level == logging.ERROR
        assert result.is_crash is True
        assert result.help_message is not None
        assert "memory" in result.help_message

    def test_generic_nonzero_exit_code(self):
        result = interpret_exit_code(1)
        assert result.exit_code == 1
        assert result.level == logging.ERROR
        assert result.is_crash is True
        assert result.help_message is None

    def test_another_generic_exit_code(self):
        result = interpret_exit_code(137)
        assert result.exit_code == 137
        assert result.level == logging.ERROR
        assert result.is_crash is True
        assert result.help_message is None

    @patch("prefect.runner._exit_code_interpreter.sys")
    def test_windows_ctrl_c_exit(self, mock_sys):
        mock_sys.platform = "win32"
        result = interpret_exit_code(_STATUS_CONTROL_C_EXIT)
        assert result.exit_code == _STATUS_CONTROL_C_EXIT
        assert result.level == logging.INFO
        assert result.is_crash is True
        assert result.help_message is not None
        assert "Ctrl+C" in result.help_message

    def test_windows_ctrl_c_exit_not_on_linux(self):
        """On non-Windows platforms, the STATUS_CONTROL_C_EXIT code is not
        recognized and falls through to the default."""
        if sys.platform == "win32":
            return
        result = interpret_exit_code(_STATUS_CONTROL_C_EXIT)
        assert result.level == logging.ERROR
        assert result.help_message is None

    def test_all_nonzero_codes_are_crashes(self):
        """Every non-zero exit code should produce is_crash=True."""
        for code in [-9, -15, 247, 1, 2, 42, 127, 255]:
            result = interpret_exit_code(code)
            assert result.is_crash is True, f"exit_code={code} should be a crash"

    def test_status_control_c_exit_constant(self):
        assert _STATUS_CONTROL_C_EXIT == -1073741510

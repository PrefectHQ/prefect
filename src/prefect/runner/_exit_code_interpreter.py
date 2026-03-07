from __future__ import annotations

import logging
import sys
from dataclasses import dataclass


@dataclass
class ExitCodeResult:
    exit_code: int
    level: int  # logging.INFO or logging.ERROR
    help_message: str | None
    is_crash: bool  # True -> propose Crashed; False -> propose Failed


# Windows STATUS_CONTROL_C_EXIT — matches runner.py line 1727
_STATUS_CONTROL_C_EXIT = 0xC000013A


def interpret_exit_code(exit_code: int) -> ExitCodeResult:
    """Interpret a non-zero process exit code.

    Source: runner.py lines 1375-1412 (in `_submit_run_and_capture_errors`)
            and lines 790-830 (in `execute_bundle`) -- identical logic in both.

    `ProcessHandle.returncode` already normalizes `SpawnProcess.exitcode` vs
    `Process.returncode`. Callers pass `handle.returncode` directly.

    Called only for non-zero exit codes. For exit_code == 0, the flow itself
    proposed its terminal state.
    """
    level = logging.ERROR
    help_message: str | None = None
    is_crash = True  # all non-zero codes produce Crashed by default

    if exit_code == -9:
        level = logging.INFO
        help_message = (
            "This indicates that the process exited due to a SIGKILL signal. "
            "Typically, this is either caused by manual cancellation or "
            "high memory usage causing the operating system to terminate the process."
        )
    elif exit_code == -15:
        level = logging.INFO
        help_message = (
            "This indicates that the process exited due to a SIGTERM signal. "
            "Typically, this is caused by manual cancellation."
        )
    elif exit_code == 247:
        help_message = (
            "This indicates that the process was terminated due to high memory usage."
        )
    elif sys.platform == "win32" and exit_code == _STATUS_CONTROL_C_EXIT:
        level = logging.INFO
        help_message = (
            "Process was terminated due to a Ctrl+C or Ctrl+Break signal. "
            "Typically, this is caused by manual cancellation."
        )

    return ExitCodeResult(
        exit_code=exit_code,
        level=level,
        help_message=help_message,
        is_crash=is_crash,
    )

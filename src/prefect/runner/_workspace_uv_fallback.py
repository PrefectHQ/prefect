from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Iterator, Sequence

from prefect.logging import get_logger

logger = get_logger(__name__)

_COMMAND_WAIT_INTERVAL_SECONDS = 0.1
_CHILD_TERMINATION_GRACE_SECONDS = 20.0
_TERMINATION_SIGNAL_EXIT_CODES = {
    128 + signal.SIGINT,
    128 + signal.SIGTERM,
}


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    received_termination_signal: bool = False


def _normalized_exit_code(returncode: int) -> int:
    if returncode < 0:
        return 128 + abs(returncode)
    return returncode


def _was_terminated(result: CommandResult) -> bool:
    return (
        result.received_termination_signal
        or result.returncode < 0
        or result.returncode in _TERMINATION_SIGNAL_EXIT_CODES
    )


def _send_signal_to_process_tree(process: subprocess.Popen[bytes], signum: int) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signum)
        else:
            os.killpg(process.pid, signum)
    except OSError:
        pass


def _kill_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        pass


def _open_process(command: Sequence[str]) -> subprocess.Popen[bytes]:
    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)


@contextmanager
def _forward_termination_signals(
    process: subprocess.Popen[bytes],
) -> Iterator[list[int]]:
    received_signals: list[int] = []
    previous_handlers = {
        signal.SIGINT: signal.getsignal(signal.SIGINT),
        signal.SIGTERM: signal.getsignal(signal.SIGTERM),
    }

    def forward_signal(signum: int, frame: FrameType | None) -> None:
        received_signals.append(signum)
        _send_signal_to_process_tree(process, signum)

    for signum in previous_handlers:
        signal.signal(signum, forward_signal)

    try:
        yield received_signals
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def _wait_for_process(
    process: subprocess.Popen[bytes], received_signals: list[int]
) -> CommandResult:
    termination_deadline: float | None = None

    while True:
        try:
            return CommandResult(
                process.wait(timeout=_COMMAND_WAIT_INTERVAL_SECONDS),
                received_termination_signal=bool(received_signals),
            )
        except subprocess.TimeoutExpired:
            if not received_signals:
                continue

            if termination_deadline is None:
                termination_deadline = (
                    time.monotonic() + _CHILD_TERMINATION_GRACE_SECONDS
                )

            if time.monotonic() < termination_deadline:
                continue

            _kill_process_tree(process)
            return CommandResult(
                process.wait(),
                received_termination_signal=True,
            )


def _run_command(command: Sequence[str]) -> CommandResult:
    process = _open_process(command)
    with _forward_termination_signals(process) as received_signals:
        return _wait_for_process(process, received_signals)


def _default_engine_command() -> list[str]:
    return [sys.executable, "-m", "prefect.engine"]


def _uv_engine_command(
    uv_run_base_command: Sequence[str], engine_started_marker: Path
) -> list[str]:
    return [
        *uv_run_base_command,
        "python",
        "-m",
        "prefect.runner._workspace_uv_engine",
        str(engine_started_marker),
    ]


def _run_uv_with_default_engine_fallback(uv_run_base_command: Sequence[str]) -> int:
    with tempfile.TemporaryDirectory(prefix="prefect-uv-engine-") as tmp_dir:
        engine_started_marker = Path(tmp_dir) / "started"
        uv_engine_command = _uv_engine_command(
            uv_run_base_command, engine_started_marker
        )

        try:
            uv_result = _run_command(uv_engine_command)
        except OSError as exc:
            logger.warning(
                "Falling back to the default flow-run command because `uv run` "
                "could not start in the prepared workspace: %s",
                exc,
            )
            return _normalized_exit_code(
                _run_command(_default_engine_command()).returncode
            )

        if (
            _was_terminated(uv_result)
            or uv_result.returncode == 0
            or engine_started_marker.exists()
        ):
            return _normalized_exit_code(uv_result.returncode)

        logger.warning(
            "Falling back to the default flow-run command because `uv run` exited "
            "before the Prefect engine started."
        )
        return _normalized_exit_code(_run_command(_default_engine_command()).returncode)


def main(argv: list[str] | None = None) -> int:
    uv_run_base_command = sys.argv[1:] if argv is None else argv
    if not uv_run_base_command:
        print("Expected a `uv run` command.", file=sys.stderr)
        return 2

    return _run_uv_with_default_engine_fallback(uv_run_base_command)


if __name__ == "__main__":
    raise SystemExit(main())

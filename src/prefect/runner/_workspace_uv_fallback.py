from __future__ import annotations

import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from signal import SIGINT, SIGTERM, getsignal, signal
from types import FrameType
from typing import Iterator, Sequence

from prefect.logging import get_logger

logger = get_logger(__name__)


@contextmanager
def _forward_termination_signals(process: subprocess.Popen[bytes]) -> Iterator[None]:
    previous_handlers = {SIGINT: getsignal(SIGINT), SIGTERM: getsignal(SIGTERM)}

    def forward_signal(signum: int, frame: FrameType | None) -> None:
        if process.poll() is None:
            try:
                process.send_signal(signum)
            except OSError:
                pass

    for signum in previous_handlers:
        signal(signum, forward_signal)

    try:
        yield
    finally:
        for signum, handler in previous_handlers.items():
            signal(signum, handler)


def _run_command(command: Sequence[str]) -> int:
    process = subprocess.Popen(command)
    with _forward_termination_signals(process):
        return process.wait()


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
            uv_return_code = _run_command(uv_engine_command)
        except OSError as exc:
            logger.warning(
                "Falling back to the default flow-run command because `uv run` "
                "could not start in the prepared workspace: %s",
                exc,
            )
            return _run_command(_default_engine_command())

        if uv_return_code == 0 or engine_started_marker.exists():
            return uv_return_code

        logger.warning(
            "Falling back to the default flow-run command because `uv run` exited "
            "before the Prefect engine started."
        )
        return _run_command(_default_engine_command())


def main(argv: list[str] | None = None) -> int:
    uv_run_base_command = sys.argv[1:] if argv is None else argv
    if not uv_run_base_command:
        print("Expected a `uv run` command.", file=sys.stderr)
        return 2

    return _run_uv_with_default_engine_fallback(uv_run_base_command)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

from prefect.runner import _workspace_uv_engine, _workspace_uv_fallback


def test_uv_fallback_returns_uv_result_after_engine_starts(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> _workspace_uv_fallback.CommandResult:
        calls.append(command)
        Path(command[-1]).touch()
        return _workspace_uv_fallback.CommandResult(7)

    monkeypatch.setattr(_workspace_uv_fallback, "_run_command", fake_run_command)

    assert (
        _workspace_uv_fallback._run_uv_with_default_engine_fallback(
            ["/opt/bin/uv", "run", "--project", "/workspace/project"]
        )
        == 7
    )

    assert calls == [
        [
            "/opt/bin/uv",
            "run",
            "--project",
            "/workspace/project",
            "python",
            "-m",
            "prefect.runner._workspace_uv_engine",
            calls[0][-1],
        ]
    ]


def test_uv_fallback_returns_success_without_default_engine(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> _workspace_uv_fallback.CommandResult:
        calls.append(command)
        return _workspace_uv_fallback.CommandResult(0)

    monkeypatch.setattr(_workspace_uv_fallback, "_run_command", fake_run_command)

    assert (
        _workspace_uv_fallback._run_uv_with_default_engine_fallback(
            ["/opt/bin/uv", "run", "--project", "/workspace/project"]
        )
        == 0
    )

    assert len(calls) == 1
    assert calls[0][:4] == ["/opt/bin/uv", "run", "--project", "/workspace/project"]


def test_uv_fallback_runs_default_engine_when_uv_exits_before_engine_starts(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> _workspace_uv_fallback.CommandResult:
        calls.append(command)
        if command[0] == "/opt/bin/uv":
            return _workspace_uv_fallback.CommandResult(1)
        return _workspace_uv_fallback.CommandResult(0)

    monkeypatch.setattr(_workspace_uv_fallback, "_run_command", fake_run_command)

    assert (
        _workspace_uv_fallback._run_uv_with_default_engine_fallback(
            ["/opt/bin/uv", "run", "--project", "/workspace/project"]
        )
        == 0
    )

    assert calls[0][:4] == ["/opt/bin/uv", "run", "--project", "/workspace/project"]
    assert calls[1] == [sys.executable, "-m", "prefect.engine"]


def test_uv_fallback_runs_default_engine_when_uv_cannot_start(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> _workspace_uv_fallback.CommandResult:
        calls.append(command)
        if command[0] == "/opt/bin/uv":
            raise OSError("uv unavailable")
        return _workspace_uv_fallback.CommandResult(0)

    monkeypatch.setattr(_workspace_uv_fallback, "_run_command", fake_run_command)

    assert (
        _workspace_uv_fallback._run_uv_with_default_engine_fallback(
            ["/opt/bin/uv", "run", "--project", "/workspace/project"]
        )
        == 0
    )

    assert calls[0][:4] == ["/opt/bin/uv", "run", "--project", "/workspace/project"]
    assert calls[1] == [sys.executable, "-m", "prefect.engine"]


def test_uv_fallback_does_not_run_default_engine_after_termination_signal(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> _workspace_uv_fallback.CommandResult:
        calls.append(command)
        return _workspace_uv_fallback.CommandResult(
            128 + signal.SIGTERM,
            received_termination_signal=True,
        )

    monkeypatch.setattr(_workspace_uv_fallback, "_run_command", fake_run_command)

    assert (
        _workspace_uv_fallback._run_uv_with_default_engine_fallback(
            ["/opt/bin/uv", "run", "--project", "/workspace/project"]
        )
        == 128 + signal.SIGTERM
    )

    assert len(calls) == 1
    assert calls[0][:4] == ["/opt/bin/uv", "run", "--project", "/workspace/project"]


def test_run_command_kills_child_tree_after_forwarded_termination_signal(
    monkeypatch: pytest.MonkeyPatch,
):
    handlers: dict[int, Callable[[int, object], None] | object] = {}
    restored_handlers: dict[int, object] = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }
    forwarded_signals: list[int] = []

    class FakeProcess:
        pid = 4242
        returncode: int | None = None
        killed = False
        wait_calls = 0

        def poll(self) -> int | None:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            self.wait_calls += 1
            if self.killed:
                self.returncode = -signal.SIGKILL
                return self.returncode

            if self.wait_calls == 1:
                handler = handlers[signal.SIGTERM]
                assert callable(handler)
                handler(signal.SIGTERM, None)

            raise subprocess.TimeoutExpired(["uv"], timeout)

    fake_process = FakeProcess()

    def fake_signal(signum: int, handler: Callable[[int, object], None] | object):
        handlers[signum] = handler

    def fake_send_signal_to_process_tree(process: FakeProcess, signum: int) -> None:
        assert process is fake_process
        forwarded_signals.append(signum)

    def fake_kill_process_tree(process: FakeProcess) -> None:
        assert process is fake_process
        process.killed = True

    monkeypatch.setattr(
        _workspace_uv_fallback, "_open_process", lambda command: fake_process
    )
    monkeypatch.setattr(
        _workspace_uv_fallback,
        "_COMMAND_WAIT_INTERVAL_SECONDS",
        0,
    )
    monkeypatch.setattr(
        _workspace_uv_fallback,
        "_CHILD_TERMINATION_GRACE_SECONDS",
        0,
    )
    monkeypatch.setattr(
        _workspace_uv_fallback.signal,
        "getsignal",
        lambda signum: restored_handlers[signum],
    )
    monkeypatch.setattr(_workspace_uv_fallback.signal, "signal", fake_signal)
    monkeypatch.setattr(
        _workspace_uv_fallback,
        "_send_signal_to_process_tree",
        fake_send_signal_to_process_tree,
    )
    monkeypatch.setattr(
        _workspace_uv_fallback,
        "_kill_process_tree",
        fake_kill_process_tree,
    )

    result = _workspace_uv_fallback._run_command(["/opt/bin/uv", "run"])

    assert result == _workspace_uv_fallback.CommandResult(
        -signal.SIGKILL,
        received_termination_signal=True,
    )
    assert forwarded_signals == [signal.SIGTERM]
    assert handlers == restored_handlers


def test_uv_engine_marks_engine_started_before_exec(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    marker = tmp_path / "started"
    exec_calls: list[tuple[str, list[str]]] = []

    def fake_execv(executable: str, args: list[str]) -> None:
        exec_calls.append((executable, args))
        raise SystemExit(23)

    monkeypatch.setattr(os, "execv", fake_execv)

    with pytest.raises(SystemExit) as exc:
        _workspace_uv_engine.main([str(marker)])

    assert exc.value.code == 23
    assert marker.is_file()
    assert exec_calls == [(sys.executable, [sys.executable, "-m", "prefect.engine"])]

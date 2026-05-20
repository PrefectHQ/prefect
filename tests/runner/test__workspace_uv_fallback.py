from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from prefect.runner import _workspace_uv_engine, _workspace_uv_fallback


def test_uv_fallback_returns_uv_result_after_engine_starts(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[list[str]] = []

    def fake_run_command(command: list[str]) -> int:
        calls.append(command)
        Path(command[-1]).touch()
        return 7

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

    def fake_run_command(command: list[str]) -> int:
        calls.append(command)
        return 0

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

    def fake_run_command(command: list[str]) -> int:
        calls.append(command)
        if command[0] == "/opt/bin/uv":
            return 1
        return 0

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

    def fake_run_command(command: list[str]) -> int:
        calls.append(command)
        if command[0] == "/opt/bin/uv":
            raise OSError("uv unavailable")
        return 0

    monkeypatch.setattr(_workspace_uv_fallback, "_run_command", fake_run_command)

    assert (
        _workspace_uv_fallback._run_uv_with_default_engine_fallback(
            ["/opt/bin/uv", "run", "--project", "/workspace/project"]
        )
        == 0
    )

    assert calls[0][:4] == ["/opt/bin/uv", "run", "--project", "/workspace/project"]
    assert calls[1] == [sys.executable, "-m", "prefect.engine"]


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

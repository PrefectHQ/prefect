from __future__ import annotations

import importlib.metadata
from pathlib import Path
from unittest.mock import MagicMock

import anyio
import pytest

from prefect.runner import _workspace_runtime_bootstrap


def test_hook_bootstrap_dispatches_with_source_fallback_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(
        importlib.metadata,
        "version",
        lambda _package: "3.6.24+99",
    )
    run = MagicMock()
    monkeypatch.setattr(anyio, "run", run)

    paths = [tmp_path / name for name in ("manifest", "flow-run", "state")]
    assert (
        _workspace_runtime_bootstrap.main(
            ["hook", "crashed", *(str(path) for path in paths)]
        )
        == 0
    )
    run.assert_called_once_with(
        _workspace_runtime_bootstrap._execute_hook,
        "crashed",
        *paths,
    )


def test_engine_bootstrap_runs_flow_engine_with_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_workspace_runtime_bootstrap.sys, "argv", ["pytest"])
    run_module = MagicMock()
    monkeypatch.setattr(
        _workspace_runtime_bootstrap.runpy,
        "run_module",
        run_module,
    )

    assert _workspace_runtime_bootstrap.main(["engine", "flows.py:hello"]) == 0
    run_module.assert_called_once_with("prefect.flow_engine", run_name="__main__")
    assert _workspace_runtime_bootstrap.sys.argv == [
        "prefect.flow_engine",
        "flows.py:hello",
    ]

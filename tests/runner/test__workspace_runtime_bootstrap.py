from __future__ import annotations

import importlib.metadata
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock
from uuid import uuid4

import anyio
import pytest

from prefect import flow_engine
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
    flow_run_id = uuid4()
    monkeypatch.setenv("PREFECT__FLOW_RUN_ID", str(flow_run_id))
    original_argv = ["pytest"]
    monkeypatch.setattr(_workspace_runtime_bootstrap.sys, "argv", original_argv)

    def assert_modern_context(*_args: object, **_kwargs: object) -> None:
        assert _workspace_runtime_bootstrap.sys.argv == [
            "prefect.flow_engine",
            "flows.py:hello",
        ]

    run_flow = MagicMock(side_effect=assert_modern_context)
    monkeypatch.setattr(flow_engine, "_run_flow_from_runtime_entrypoint", run_flow)
    run_module = MagicMock()
    monkeypatch.setattr(
        _workspace_runtime_bootstrap.runpy,
        "run_module",
        run_module,
    )

    assert _workspace_runtime_bootstrap.main(["engine", "flows.py:hello"]) == 0
    run_flow.assert_called_once_with(flow_run_id, "flows.py:hello")
    run_module.assert_not_called()
    assert _workspace_runtime_bootstrap.sys.argv is original_argv


def test_engine_bootstrap_uses_legacy_engine_without_flow_engine_main(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(importlib, "import_module", lambda _module: object())
    monkeypatch.delenv("PREFECT__FLOW_ENTRYPOINT", raising=False)
    original_argv = ["pytest"]
    monkeypatch.setattr(_workspace_runtime_bootstrap.sys, "argv", original_argv)
    original_engine_module = ModuleType("prefect.engine")
    monkeypatch.setitem(sys.modules, "prefect.engine", original_engine_module)

    def assert_legacy_context(*_args: object, **_kwargs: object) -> None:
        assert _workspace_runtime_bootstrap.sys.argv == ["prefect.engine"]
        assert os.environ["PREFECT__FLOW_ENTRYPOINT"] == "flows.py:hello"
        assert "prefect.engine" not in sys.modules

    run_module = MagicMock(side_effect=assert_legacy_context)
    monkeypatch.setattr(
        _workspace_runtime_bootstrap.runpy,
        "run_module",
        run_module,
    )

    assert _workspace_runtime_bootstrap.main(["engine", "flows.py:hello"]) == 0
    run_module.assert_called_once_with("prefect.engine", run_name="__main__")
    assert _workspace_runtime_bootstrap.sys.argv is original_argv
    assert "PREFECT__FLOW_ENTRYPOINT" not in os.environ
    assert sys.modules["prefect.engine"] is original_engine_module


def test_engine_bootstrap_uses_legacy_engine_without_flow_engine_module(
    monkeypatch: pytest.MonkeyPatch,
):
    missing_flow_engine = ModuleNotFoundError(
        "No module named 'prefect.flow_engine'",
        name="prefect.flow_engine",
    )
    monkeypatch.setattr(
        importlib,
        "import_module",
        MagicMock(side_effect=missing_flow_engine),
    )
    monkeypatch.setenv("PREFECT__FLOW_ENTRYPOINT", "flows.py:original")
    original_argv = ["pytest"]
    monkeypatch.setattr(_workspace_runtime_bootstrap.sys, "argv", original_argv)

    def assert_legacy_context(*_args: object, **_kwargs: object) -> None:
        assert _workspace_runtime_bootstrap.sys.argv == ["prefect.engine"]
        assert os.environ["PREFECT__FLOW_ENTRYPOINT"] == "flows.py:hello"

    run_module = MagicMock(side_effect=assert_legacy_context)
    monkeypatch.setattr(
        _workspace_runtime_bootstrap.runpy,
        "run_module",
        run_module,
    )

    assert _workspace_runtime_bootstrap.main(["engine", "flows.py:hello"]) == 0
    run_module.assert_called_once_with("prefect.engine", run_name="__main__")
    assert _workspace_runtime_bootstrap.sys.argv is original_argv
    assert os.environ["PREFECT__FLOW_ENTRYPOINT"] == "flows.py:original"

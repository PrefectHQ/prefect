from __future__ import annotations

import importlib.metadata
from unittest.mock import MagicMock

import pytest

from prefect.runner import _workspace_runtime_bootstrap


@pytest.mark.parametrize("version", ["3.7.0", "3.8.4.dev1", "3.99.0"])
def test_validate_hook_runtime_accepts_supported_prefect_versions(
    monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    monkeypatch.setattr(importlib.metadata, "version", lambda _package: version)

    _workspace_runtime_bootstrap._validate_hook_runtime()


@pytest.mark.parametrize("version", ["2.20.0", "4.0.0"])
def test_validate_hook_runtime_rejects_unsupported_prefect_versions(
    monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    monkeypatch.setattr(importlib.metadata, "version", lambda _package: version)

    with pytest.raises(
        RuntimeError,
        match=(
            rf"project runtime contains Prefect {version}; "
            r"ProcessWorker workspace hooks require Prefect >=3\.7,<4"
        ),
    ):
        _workspace_runtime_bootstrap._validate_hook_runtime()


def test_engine_bootstrap_runs_flow_engine_with_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(importlib.metadata, "version", lambda _package: "3.6.0")
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

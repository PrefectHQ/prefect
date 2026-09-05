from __future__ import annotations

import os
from pathlib import Path

import pytest

from prefect.runner._workspace_runtime import (
    WorkspaceSupervisorConfig,
    write_private_model,
)


def test_write_private_model_without_fchmod(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delattr(os, "fchmod", raising=False)
    path = tmp_path / "runtime.json"

    write_private_model(
        path,
        WorkspaceSupervisorConfig(
            flow_run_id="00000000-0000-0000-0000-000000000000",
            workspace_root=tmp_path,
            manifest_path=tmp_path / "manifest.json",
        ),
    )

    assert path.is_file()

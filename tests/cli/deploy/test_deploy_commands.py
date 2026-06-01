from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import prefect.deployments
from prefect.testing.cli import invoke_and_assert


def test_deploy_init_field_value_can_contain_equals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    captured_inputs: dict[str, Any] = {}

    def initialize_project(
        name: str | None = None,
        recipe: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> list[str]:
        captured_inputs.update(inputs or {})
        return ["prefect.yaml"]

    monkeypatch.setattr(prefect.deployments, "initialize_project", initialize_project)

    invoke_and_assert(
        [
            "deploy",
            "init",
            "--recipe",
            "local",
            "--field",
            "api_key=aGVsbG8gd29ybGQ=",
        ],
        temp_dir=str(tmp_path),
        expected_code=0,
    )

    assert captured_inputs == {"api_key": "aGVsbG8gd29ybGQ="}

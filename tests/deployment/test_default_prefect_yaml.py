from pathlib import Path
from typing import Any

import pytest
import yaml

import prefect
from prefect.deployments.base import create_default_prefect_yaml


@pytest.mark.parametrize("kwargs", [{}, {"contents": None}, {"contents": {}}])
def test_create_default_prefect_yaml_uses_defaults(
    tmp_path: Path, kwargs: dict[str, Any]
):
    assert create_default_prefect_yaml(str(tmp_path), name="demo", **kwargs)

    contents = yaml.safe_load((tmp_path / "prefect.yaml").read_text())
    assert contents["name"] == "demo"
    assert contents["prefect-version"] == prefect.__version__
    assert contents["build"] is None
    assert contents["push"] is None
    assert contents["pull"] is None
    assert len(contents["deployments"]) == 1
    assert contents["deployments"][0]["entrypoint"] is None


def test_create_default_prefect_yaml_preserves_overrides(tmp_path: Path):
    overrides = {
        "build": [{"example.build": {"image": "demo"}}],
        "push": [],
        "pull": [
            {"prefect.deployments.steps.set_working_directory": {"directory": "."}}
        ],
        "deployments": [{"name": "daily", "entrypoint": "flow.py:main"}],
    }
    assert create_default_prefect_yaml(str(tmp_path), name="demo", contents=overrides)

    contents = yaml.safe_load((tmp_path / "prefect.yaml").read_text())
    for key in ("build", "push", "pull", "deployments"):
        assert contents[key] == overrides[key]


def test_create_default_prefect_yaml_does_not_overwrite_existing_file(tmp_path: Path):
    prefect_file = tmp_path / "prefect.yaml"
    original = "# Keep this configuration\nname: existing\n"
    prefect_file.write_text(original)

    assert not create_default_prefect_yaml(str(tmp_path), name="demo")
    assert prefect_file.read_text() == original

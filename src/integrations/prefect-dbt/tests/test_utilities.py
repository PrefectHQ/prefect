import os
from pathlib import Path

import pytest
import yaml
from prefect_dbt.utilities import get_profiles_dir, load_profiles_yml

SAMPLE_PROFILES = {
    "jaffle_shop": {
        "outputs": {
            "dev": {
                "type": "duckdb",
                "path": "jaffle_shop.duckdb",
                "schema": "main",
                "threads": 4,
            }
        }
    }
}


@pytest.fixture
def temp_profiles_dir(tmp_path):
    profiles_dir = tmp_path / ".dbt"
    profiles_dir.mkdir()

    profiles_path = profiles_dir / "profiles.yml"
    with open(profiles_path, "w") as f:
        yaml.dump(SAMPLE_PROFILES, f)

    return str(profiles_dir)


def test_get_profiles_dir_default():
    if "DBT_PROFILES_DIR" in os.environ:
        del os.environ["DBT_PROFILES_DIR"]

    expected = os.path.expanduser("~/.dbt")
    assert get_profiles_dir() == expected


def test_get_profiles_dir_from_env(monkeypatch):
    test_path = "/custom/path"
    monkeypatch.setenv("DBT_PROFILES_DIR", test_path)
    assert get_profiles_dir() == test_path


def test_load_profiles_yml_success(temp_profiles_dir):
    profiles = load_profiles_yml(temp_profiles_dir)
    assert profiles == SAMPLE_PROFILES


def test_load_profiles_yml_default_dir(monkeypatch, temp_profiles_dir):
    monkeypatch.setenv("DBT_PROFILES_DIR", temp_profiles_dir)
    profiles = load_profiles_yml(None)
    assert profiles == SAMPLE_PROFILES


def test_load_profiles_yml_file_not_found():
    nonexistent_dir = "/path/that/does/not/exist"
    with pytest.raises(
        ValueError,
        match=f"No profiles.yml found at {os.path.join(nonexistent_dir, 'profiles.yml')}",
    ):
        load_profiles_yml(nonexistent_dir)


def test_load_profiles_yml_invalid_yaml(temp_profiles_dir):
    profiles_path = Path(temp_profiles_dir) / "profiles.yml"
    with open(profiles_path, "w") as f:
        f.write("invalid: yaml: content:\nindentation error")

    with pytest.raises(yaml.YAMLError):
        load_profiles_yml(temp_profiles_dir)

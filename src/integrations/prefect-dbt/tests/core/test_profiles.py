import os
from pathlib import Path

import pytest
import yaml
from prefect_dbt.core.profiles import (
    aresolve_profiles_yml,
    get_profiles_dir,
    load_profiles_yml,
    replace_with_env_var_call,
    resolve_profiles_yml,
)

from prefect.client.orchestration import get_client

SAMPLE_PROFILE = {
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

VARIABLES_PROFILE = {
    "jaffle_shop_with_variable_reference": {
        "outputs": {
            "dev": {
                "type": "duckdb",
                "path": "jaffle_shop.duckdb",
                "schema": "main",
                "threads": 4,
            }
        },
        "target": "{{ prefect.variables.target }}",
    }
}

BLOCKS_PROFILE = {
    "jaffle_shop_with_blocks_reference": {
        "outputs": {
            "dev": {
                "type": "duckdb",
                "path": "jaffle_shop.duckdb",
                "schema": "main",
                "threads": 4,
                "password": "{{ prefect.blocks.secret.my-password }}",
            }
        },
        "target": "dev",
    }
}


@pytest.fixture
def temp_profiles_dir(tmp_path):
    profiles_dir = tmp_path / ".dbt"
    profiles_dir.mkdir()

    profiles_path = profiles_dir / "profiles.yml"
    with open(profiles_path, "w") as f:
        yaml.dump(SAMPLE_PROFILE, f)

    return str(profiles_dir)


@pytest.fixture
def temp_variables_profiles_dir(tmp_path):
    profiles_dir = tmp_path / ".dbt"
    profiles_dir.mkdir()

    profiles_path = profiles_dir / "profiles.yml"
    with open(profiles_path, "w") as f:
        yaml.dump(VARIABLES_PROFILE, f)

    return str(profiles_dir)


@pytest.fixture
def temp_blocks_profiles_dir(tmp_path):
    """Create a temporary profiles directory with a profile that references a block."""
    profiles_dir = tmp_path / ".dbt"
    profiles_dir.mkdir()

    profiles_path = profiles_dir / "profiles.yml"
    with open(profiles_path, "w") as f:
        yaml.dump(BLOCKS_PROFILE, f)

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
    assert profiles == SAMPLE_PROFILE


def test_load_profiles_yml_default_dir(monkeypatch, temp_profiles_dir):
    monkeypatch.setenv("DBT_PROFILES_DIR", temp_profiles_dir)
    profiles = load_profiles_yml(None)
    assert profiles == SAMPLE_PROFILE


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


async def test_aresolve_profiles_yml_success(
    temp_profiles_dir,
):
    """Test that aresolve_profiles_yml creates and cleans up temporary directory."""
    async with aresolve_profiles_yml(temp_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        # Check temporary directory exists and contains profiles.yml
        assert temp_path.exists()
        assert profiles_path.exists()

        # Verify contents match expected profiles
        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert loaded_profiles == SAMPLE_PROFILE

    # Verify cleanup happened
    assert not temp_path.exists()


def test_resolve_profiles_yml_success(temp_profiles_dir):
    """Test that resolve_profiles_yml creates and cleans up temporary directory."""
    with resolve_profiles_yml(temp_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        # Check temporary directory exists and contains profiles.yml
        assert temp_path.exists()
        assert profiles_path.exists()

        # Verify contents match expected profiles
        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert loaded_profiles == SAMPLE_PROFILE

    # Verify cleanup happened
    assert not temp_path.exists()


async def test_aresolve_profiles_yml_error_cleanup(temp_profiles_dir):
    """Test that temporary directory is cleaned up even if an error occurs."""
    temp_path = None

    with pytest.raises(ValueError):
        async with aresolve_profiles_yml(temp_profiles_dir) as temp_dir:
            temp_path = Path(temp_dir)
            assert temp_path.exists()
            raise ValueError("Test error")

    # Verify cleanup happened despite error
    assert temp_path is not None
    assert not temp_path.exists()


def test_resolve_profiles_yml_error_cleanup(temp_profiles_dir):
    """Test that temporary directory is cleaned up even if an error occurs."""
    temp_path = None

    with pytest.raises(ValueError):
        with resolve_profiles_yml(temp_profiles_dir) as temp_dir:
            temp_path = Path(temp_dir)
            assert temp_path.exists()
            raise ValueError("Test error")

    # Verify cleanup happened despite error
    assert temp_path is not None
    assert not temp_path.exists()


async def test_aresolve_profiles_yml_resolves_variables(temp_variables_profiles_dir):
    """Test that variables in profiles.yml are properly resolved."""
    # Create a variable
    async with get_client() as client:
        await client._client.post(
            "/variables/", json={"name": "target", "value": "dev"}
        )

    # Use the context manager and verify variable resolution
    async with aresolve_profiles_yml(temp_variables_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        # Verify contents have resolved variables
        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert loaded_profiles["jaffle_shop_with_variable_reference"]["target"] == "dev"


def test_resolve_profiles_yml_resolves_variables(temp_variables_profiles_dir):
    with resolve_profiles_yml(temp_variables_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert loaded_profiles["jaffle_shop_with_variable_reference"]["target"] == "dev"


async def test_aresolve_profiles_yml_resolves_blocks(temp_blocks_profiles_dir):
    from prefect.blocks.system import Secret

    secret_block = Secret(value="super-secret-password")
    await secret_block.save("my-password", overwrite=True)

    async with aresolve_profiles_yml(temp_blocks_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert (
            loaded_profiles["jaffle_shop_with_blocks_reference"]["outputs"]["dev"][
                "password"
            ]
            == "{{ env_var('PREFECT_BLOCKS_SECRET_MY_PASSWORD') }}"
        )


def test_resolve_profiles_yml_resolves_blocks(temp_blocks_profiles_dir):
    from prefect.blocks.system import Secret

    secret_block = Secret(value="super-secret-password")
    secret_block.save("my-password", overwrite=True)

    with resolve_profiles_yml(temp_blocks_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert (
            loaded_profiles["jaffle_shop_with_blocks_reference"]["outputs"]["dev"][
                "password"
            ]
            == "{{ env_var('PREFECT_BLOCKS_SECRET_MY_PASSWORD') }}"
        )


def test_replace_with_env_var_call():
    """Test that replace_with_env_var_call properly creates env vars and returns template text."""
    # Test with a simple block reference
    result = replace_with_env_var_call(
        "prefect.blocks.secret.my-password.value", "test-value"
    )
    assert result == "{{ env_var('PREFECT_BLOCKS_SECRET_MY_PASSWORD_VALUE') }}"
    assert os.environ["PREFECT_BLOCKS_SECRET_MY_PASSWORD_VALUE"] == "test-value"

    # Test with a complex block instance name
    result = replace_with_env_var_call(
        "prefect.blocks.json.complex-name!@123.value", "complex-value"
    )
    assert result == "{{ env_var('PREFECT_BLOCKS_JSON_COMPLEX_NAME_123_VALUE') }}"
    assert os.environ["PREFECT_BLOCKS_JSON_COMPLEX_NAME_123_VALUE"] == "complex-value"

    # Test with non-string value
    result = replace_with_env_var_call("prefect.blocks.json.number-config.value", 42)
    assert result == "{{ env_var('PREFECT_BLOCKS_JSON_NUMBER_CONFIG_VALUE') }}"
    assert os.environ["PREFECT_BLOCKS_JSON_NUMBER_CONFIG_VALUE"] == "42"

"""
Unit tests for PrefectDbtSettings - focusing on outcomes.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from prefect_dbt.core.settings import PrefectDbtSettings


def test_settings_provide_working_dbt_configuration(monkeypatch: pytest.MonkeyPatch):
    """Test that settings provide a working dbt configuration."""
    # Create settings with explicit profiles_dir to avoid the default_factory issue
    settings = PrefectDbtSettings(profiles_dir=Path(".dbt"))

    # Verify all required paths are set correctly
    assert isinstance(settings.project_dir, Path)
    assert isinstance(settings.profiles_dir, Path)
    assert isinstance(settings.target_path, Path)
    assert settings.target_path.name == "target"

    # Verify profiles_dir matches our explicit setting
    assert settings.profiles_dir == Path(".dbt")


def test_settings_override_defaults_correctly(monkeypatch: pytest.MonkeyPatch):
    """Test that settings properly override defaults."""
    custom_project = Path("/custom/project")
    custom_target = Path("custom_target")

    monkeypatch.setattr(
        "prefect_dbt.core.settings.find_profiles_dir",
        Mock(return_value=Path("/home/user/.dbt")),
    )

    settings = PrefectDbtSettings(project_dir=custom_project, target_path=custom_target)

    # Verify custom values are used
    assert settings.project_dir == custom_project
    assert settings.target_path == custom_target


def test_settings_load_valid_profiles_file():
    """Test that settings can load and parse a valid profiles.yml file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a valid profiles.yml
        profiles_content = {
            "my_profile": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "localhost",
                        "port": 5432,
                        "user": "test_user",
                        "pass": "test_pass",
                        "dbname": "test_db",
                    }
                }
            }
        }

        profiles_file = temp_path / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_content, f)

        settings = PrefectDbtSettings(profiles_dir=temp_path)
        loaded_profiles = settings.load_profiles_yml()

        # Verify profiles were loaded correctly
        assert "my_profile" in loaded_profiles
        assert loaded_profiles["my_profile"]["targets"]["dev"]["type"] == "postgres"
        assert loaded_profiles["my_profile"]["targets"]["dev"]["host"] == "localhost"
        assert loaded_profiles["my_profile"]["targets"]["dev"]["port"] == 5432


def test_settings_handle_missing_profiles_file():
    """Test that settings handle missing profiles.yml gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        # Ensure no profiles.yml exists

        settings = PrefectDbtSettings(profiles_dir=temp_path)

        # Should raise ValueError when trying to load non-existent file
        with pytest.raises(ValueError, match="No profiles.yml found"):
            settings.load_profiles_yml()


def test_settings_resolve_profiles_with_templating(monkeypatch: pytest.MonkeyPatch):
    """Test that settings can resolve profiles with templating."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create profiles with templating
        profiles_content = {
            "my_profile": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "{{ env_var('DB_HOST') }}",
                        "port": "{{ env_var('DB_PORT') }}",
                    }
                }
            }
        }

        profiles_file = temp_path / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_content, f)

        settings = PrefectDbtSettings(profiles_dir=temp_path)

        # Mock the resolution functions to return resolved content
        resolved_content = {
            "my_profile": {
                "targets": {
                    "dev": {"type": "postgres", "host": "localhost", "port": 5432}
                }
            }
        }

        monkeypatch.setattr(
            "prefect_dbt.core.settings.resolve_block_document_references",
            Mock(return_value=resolved_content),
        )
        monkeypatch.setattr(
            "prefect_dbt.core.settings.resolve_variables",
            Mock(return_value=resolved_content),
        )
        monkeypatch.setattr(
            "prefect_dbt.core.settings.run_coro_as_sync",
            Mock(side_effect=lambda coro: resolved_content),
        )

        with settings.resolve_profiles_yml() as temp_dir_path:
            # Verify temporary directory was created
            assert Path(temp_dir_path).exists()

            # Verify resolved profiles.yml was created
            temp_profiles_path = Path(temp_dir_path) / "profiles.yml"
            assert temp_profiles_path.exists()

            # Verify content was resolved
            with open(temp_profiles_path, "r") as f:
                content = yaml.safe_load(f)
                assert content == resolved_content

            # Verify cleanup happens
            temp_dir = Path(temp_dir_path)

        # Verify temporary directory was cleaned up
        assert not temp_dir.exists()


def test_settings_handle_resolution_failures(monkeypatch: pytest.MonkeyPatch):
    """Test that settings handle resolution failures gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        profiles_content = {"test": "content"}
        profiles_file = temp_path / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_content, f)

        settings = PrefectDbtSettings(profiles_dir=temp_path)

        monkeypatch.setattr(
            "prefect_dbt.core.settings.resolve_block_document_references",
            Mock(return_value=profiles_content),
        )
        monkeypatch.setattr(
            "prefect_dbt.core.settings.resolve_variables",
            Mock(return_value=profiles_content),
        )
        monkeypatch.setattr(
            "prefect_dbt.core.settings.run_coro_as_sync",
            Mock(side_effect=lambda coro: profiles_content),
        )

        temp_dir_path = None
        try:
            with settings.resolve_profiles_yml() as temp_dir:
                temp_dir_path = temp_dir
                # Verify temporary directory was created
                assert Path(temp_dir_path).exists()
                # Simulate a failure
                raise Exception("Resolution failed")
        except Exception:
            # Verify cleanup happened despite exception
            if temp_dir_path:
                assert not Path(temp_dir_path).exists()


def test_settings_environment_variable_loading(monkeypatch: pytest.MonkeyPatch):
    """Test that settings properly load from environment variables."""
    monkeypatch.setattr(
        "prefect_dbt.core.settings.find_profiles_dir",
        Mock(return_value=Path("/home/user/.dbt")),
    )

    monkeypatch.setenv("DBT_PROJECT_DIR", "/env/project")
    monkeypatch.setenv("DBT_TARGET_PATH", "env_target")
    monkeypatch.setenv("DBT_LOG_LEVEL", "debug")  # Use lowercase to match Enum

    settings = PrefectDbtSettings()

    # Verify environment variables were loaded
    assert settings.project_dir == Path("/env/project")
    assert settings.target_path == Path("env_target")
    # Note: log level validation depends on dbt_common.events.base_types.EventLevel


def test_settings_discover_profiles_directory_correctly(
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that settings discover the profiles directory correctly."""
    # Test when profiles.yml exists in current working directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        profiles_file = temp_path / "profiles.yml"
        profiles_file.write_text("test content")

        monkeypatch.setattr("pathlib.Path.cwd", Mock(return_value=temp_path))
        monkeypatch.setattr(
            "prefect_dbt.core.settings.find_profiles_dir",
            Mock(return_value=temp_path),
        )

        settings = PrefectDbtSettings()
        assert settings.profiles_dir == temp_path

    # Test when profiles.yml doesn't exist in current working directory
    monkeypatch.setattr(
        "pathlib.Path.cwd", Mock(return_value=Path("/some/random/path"))
    )
    monkeypatch.setattr("pathlib.Path.home", Mock(return_value=Path("/home/user")))
    monkeypatch.setattr(
        "prefect_dbt.core.settings.find_profiles_dir",
        Mock(return_value=Path("/home/user/.dbt")),
    )

    settings = PrefectDbtSettings()
    assert settings.profiles_dir == Path("/home/user/.dbt")


def test_settings_handle_complex_profiles_structure():
    """Test that settings handle complex profiles.yml structures."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create complex profiles with multiple targets and profiles
        complex_profiles = {
            "default_profile": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "dev-db.example.com",
                        "port": 5432,
                    },
                    "prod": {
                        "type": "postgres",
                        "host": "prod-db.example.com",
                        "port": 5432,
                    },
                }
            },
            "test_profile": {
                "targets": {"test": {"type": "sqlite", "path": "/tmp/test.db"}}
            },
        }

        profiles_file = temp_path / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(complex_profiles, f)

        settings = PrefectDbtSettings(profiles_dir=temp_path)
        loaded_profiles = settings.load_profiles_yml()

        # Verify complex structure was loaded correctly
        assert "default_profile" in loaded_profiles
        assert "test_profile" in loaded_profiles
        assert "dev" in loaded_profiles["default_profile"]["targets"]
        assert "prod" in loaded_profiles["default_profile"]["targets"]
        assert "test" in loaded_profiles["test_profile"]["targets"]

        # Verify specific values
        assert (
            loaded_profiles["default_profile"]["targets"]["dev"]["host"]
            == "dev-db.example.com"
        )
        assert loaded_profiles["test_profile"]["targets"]["test"]["type"] == "sqlite"


@pytest.fixture
def mock_prefect_blocks(monkeypatch: pytest.MonkeyPatch):
    """Fixture to mock Prefect blocks for testing."""

    # Mock block document references resolution
    def mock_resolve_blocks(data, value_transformer=None):
        # Simulate resolving block references
        if isinstance(data, dict):
            resolved = {}
            for key, value in data.items():
                if isinstance(value, str) and "{{ prefect.blocks.secret." in value:
                    # Extract block name and return mock value
                    block_name = value.split("prefect.blocks.secret.")[1].split(" }}")[
                        0
                    ]
                    mock_values = {
                        "db-host": "localhost",
                        "db-password": "secret_password_123",
                        "db-user": "dbt_user",
                    }
                    resolved[key] = mock_values.get(
                        block_name, f"resolved_{block_name}"
                    )
                elif isinstance(value, (dict, list)):
                    resolved[key] = mock_resolve_blocks(value, value_transformer)
                else:
                    resolved[key] = value
            return resolved
        elif isinstance(data, list):
            return [mock_resolve_blocks(item, value_transformer) for item in data]
        else:
            return data

    # Mock the async function to return resolved data directly
    async def mock_async_resolve_blocks(data, value_transformer=None):
        return mock_resolve_blocks(data, value_transformer)

    monkeypatch.setattr(
        "prefect_dbt.core.settings.resolve_block_document_references",
        Mock(side_effect=mock_async_resolve_blocks),
    )

    # Mock run_coro_as_sync to return the resolved data
    resolved_data = {
        "my_profile": {
            "targets": {
                "dev": {
                    "type": "postgres",
                    "host": "localhost",
                    "password": "secret_password_123",
                    "user": "dbt_user",
                }
            }
        }
    }
    monkeypatch.setattr(
        "prefect_dbt.core.settings.run_coro_as_sync",
        Mock(side_effect=lambda coro: resolved_data),
    )


@pytest.fixture
def mock_prefect_variables(monkeypatch: pytest.MonkeyPatch):
    """Fixture to mock Prefect variables for testing."""

    # Mock variable resolution
    def mock_resolve_vars(data):
        # Simulate resolving variable references
        if isinstance(data, dict):
            resolved = {}
            for key, value in data.items():
                if isinstance(value, str) and "{{ prefect.variables." in value:
                    # Extract variable name and return mock value
                    var_name = value.split("prefect.variables.")[1].split(" }}")[0]
                    mock_values = {
                        "DB_HOST": "prod-db.example.com",
                        "DB_PASSWORD": "prod_password_456",
                        "DB_USER": "prod_user",
                    }
                    resolved[key] = mock_values.get(var_name, f"resolved_{var_name}")
                elif isinstance(value, (dict, list)):
                    resolved[key] = mock_resolve_vars(value)
                else:
                    resolved[key] = value
            return resolved
        elif isinstance(data, list):
            return [mock_resolve_vars(item) for item in data]
        else:
            return data

    # Mock the async function to return resolved data directly
    async def mock_async_resolve_vars(data):
        return mock_resolve_vars(data)

    monkeypatch.setattr(
        "prefect_dbt.core.settings.resolve_variables",
        Mock(side_effect=mock_async_resolve_vars),
    )

    # Mock run_coro_as_sync to return the resolved data
    resolved_data = {
        "my_profile": {
            "targets": {
                "dev": {
                    "type": "postgres",
                    "host": "prod-db.example.com",
                    "password": "prod_password_456",
                    "user": "prod_user",
                }
            }
        }
    }
    monkeypatch.setattr(
        "prefect_dbt.core.settings.run_coro_as_sync",
        Mock(side_effect=lambda coro: resolved_data),
    )


def test_settings_resolve_profiles_yml_with_block_references(mock_prefect_blocks):
    """Test that resolve_profiles_yml resolves Prefect block references correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create profiles.yml with block references
        profiles_content = {
            "my_profile": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "{{ prefect.blocks.secret.db-host }}",
                        "password": "{{ prefect.blocks.secret.db-password }}",
                        "user": "{{ prefect.blocks.secret.db-user }}",
                    }
                }
            }
        }

        profiles_file = temp_path / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_content, f)

        settings = PrefectDbtSettings(profiles_dir=temp_path)

        with settings.resolve_profiles_yml() as temp_dir_path:
            temp_profiles_path = Path(temp_dir_path) / "profiles.yml"
            with open(temp_profiles_path, "r") as f:
                content = yaml.safe_load(f)

            # Verify block references were resolved
            assert content["my_profile"]["targets"]["dev"]["host"] == "localhost"
            assert (
                content["my_profile"]["targets"]["dev"]["password"]
                == "secret_password_123"
            )
            assert content["my_profile"]["targets"]["dev"]["user"] == "dbt_user"

        # Verify cleanup happens
        assert not Path(temp_dir_path).exists()


def test_settings_resolve_profiles_yml_with_variable_references(mock_prefect_variables):
    """Test that resolve_profiles_yml resolves Prefect variable references correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create profiles.yml with variable references
        profiles_content = {
            "my_profile": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "{{ prefect.variables.DB_HOST }}",
                        "password": "{{ prefect.variables.DB_PASSWORD }}",
                        "user": "{{ prefect.variables.DB_USER }}",
                    }
                }
            }
        }

        profiles_file = temp_path / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_content, f)

        settings = PrefectDbtSettings(profiles_dir=temp_path)

        with settings.resolve_profiles_yml() as temp_dir_path:
            temp_profiles_path = Path(temp_dir_path) / "profiles.yml"
            with open(temp_profiles_path, "r") as f:
                content = yaml.safe_load(f)

            # Verify variable references were resolved
            assert (
                content["my_profile"]["targets"]["dev"]["host"] == "prod-db.example.com"
            )
            assert (
                content["my_profile"]["targets"]["dev"]["password"]
                == "prod_password_456"
            )
            assert content["my_profile"]["targets"]["dev"]["user"] == "prod_user"

        # Verify cleanup happens
        assert not Path(temp_dir_path).exists()

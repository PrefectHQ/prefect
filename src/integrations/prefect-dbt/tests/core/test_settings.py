"""
Tests for PrefectDbtSettings class and related functionality.
"""

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml
from dbt_common.events.base_types import EventLevel
from prefect_dbt.core.settings import PrefectDbtSettings
from pydantic.types import SecretStr

import prefect.exceptions
from prefect.blocks.system import Secret
from prefect.variables import Variable


@pytest.fixture
def mock_find_profiles_dir(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock find_profiles_dir to return a predictable path."""
    mock_path = Path("/mock/profiles/dir")
    monkeypatch.setattr(
        "prefect_dbt.core.settings.find_profiles_dir", Mock(return_value=mock_path)
    )
    return mock_path


@pytest.fixture
def mock_get_current_settings(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock get_current_settings to return predictable logging level."""
    mock_settings = Mock()
    mock_settings.logging.level = "info"
    monkeypatch.setattr(
        "prefect_dbt.core.settings.get_current_settings",
        Mock(return_value=mock_settings),
    )
    return mock_settings


@pytest.fixture
def mock_get_current_settings_error(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock get_current_settings to return predictable logging level."""
    mock_settings = Mock()
    mock_settings.logging.level = "error"
    monkeypatch.setattr(
        "prefect_dbt.core.settings.get_current_settings",
        Mock(return_value=mock_settings),
    )
    return mock_settings


@pytest.fixture
def temp_profiles_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with a profiles.yml file."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    return profiles_dir


@pytest.fixture
def sample_profiles_yml() -> dict[str, Any]:
    """Sample profiles.yml content for testing."""
    return {
        "default": {
            "targets": {
                "dev": {
                    "type": "postgres",
                    "host": "localhost",
                    "port": 5432,
                    "user": "test_user",
                    "pass": "test_pass",
                    "dbname": "test_db",
                },
                "prod": {
                    "type": "postgres",
                    "host": "prod.example.com",
                    "port": 5432,
                    "user": "prod_user",
                    "pass": "prod_pass",
                    "dbname": "prod_db",
                },
            }
        },
        "test_profile": {
            "targets": {"test": {"type": "sqlite", "path": "/tmp/test.db"}}
        },
    }


class TestPrefectDbtSettingsInitialization:
    """Test PrefectDbtSettings initialization and default values."""

    def test_initializes_with_defaults(
        self, mock_find_profiles_dir: Path, mock_get_current_settings: Mock
    ):
        """Test that settings initialize with sensible defaults."""
        settings = PrefectDbtSettings(profiles_dir=mock_find_profiles_dir)
        assert settings.profiles_dir == mock_find_profiles_dir
        assert settings.project_dir == Path.cwd()
        assert settings.target_path == Path("target")
        assert settings.log_level == EventLevel.INFO

    def test_accepts_custom_values(self, temp_profiles_dir: Path):
        """Test that settings accept and use custom values."""
        custom_project = Path("/custom/project")
        custom_target = Path("custom_target")
        custom_log_level = EventLevel.DEBUG

        settings = PrefectDbtSettings(
            profiles_dir=temp_profiles_dir,
            project_dir=custom_project,
            target_path=custom_target,
            log_level=custom_log_level,
        )

        assert settings.profiles_dir == temp_profiles_dir
        assert settings.project_dir == custom_project
        assert settings.target_path == custom_target
        assert settings.log_level == custom_log_level

    def test_uses_prefect_logging_level_when_not_set(
        self, mock_get_current_settings_error: Mock
    ):
        """Test that settings use Prefect's logging level when not explicitly set."""
        settings = PrefectDbtSettings()
        assert settings.log_level == EventLevel.ERROR

    def test_environment_variable_loading(self, monkeypatch: pytest.MonkeyPatch):
        """Test that settings load from environment variables."""
        monkeypatch.setenv("DBT_PROJECT_DIR", "/env/project")
        monkeypatch.setenv("DBT_TARGET_PATH", "env_target")
        monkeypatch.setenv("DBT_LOG_LEVEL", "debug")

        settings = PrefectDbtSettings()

        assert settings.project_dir == Path("/env/project")
        assert settings.target_path == Path("env_target")
        assert settings.log_level == EventLevel.DEBUG

    def test_environment_variables_override_defaults(
        self, monkeypatch: pytest.MonkeyPatch, temp_profiles_dir: Path
    ):
        """Test that environment variables override default values."""
        monkeypatch.setenv("DBT_PROFILES_DIR", str(temp_profiles_dir))
        monkeypatch.setenv("DBT_PROJECT_DIR", "/env/override")

        settings = PrefectDbtSettings()

        assert settings.profiles_dir == temp_profiles_dir
        assert settings.project_dir == Path("/env/override")

    def test_invalid_log_level_raises_error(self, monkeypatch: pytest.MonkeyPatch):
        """Test that invalid log level raises validation error."""
        monkeypatch.setenv("DBT_LOG_LEVEL", "invalid_level")

        with pytest.raises(
            ValueError,
            match="Input should be 'debug', 'test', 'info', 'warn' or 'error'",
        ):
            PrefectDbtSettings()


class TestPrefectDbtSettingsProfilesLoading:
    """Test profiles.yml loading functionality."""

    def test_load_profiles_yml_success(
        self, temp_profiles_dir: Path, sample_profiles_yml: dict[str, Any]
    ):
        """Test successful loading of profiles.yml file."""
        profiles_file = temp_profiles_dir / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(sample_profiles_yml, f)

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)
        loaded_profiles = settings.load_profiles_yml()

        assert loaded_profiles == sample_profiles_yml
        assert "default" in loaded_profiles
        assert "test_profile" in loaded_profiles
        assert loaded_profiles["default"]["targets"]["dev"]["type"] == "postgres"
        assert loaded_profiles["test_profile"]["targets"]["test"]["type"] == "sqlite"

    def test_load_profiles_yml_missing_file(self, temp_profiles_dir: Path):
        """Test that missing profiles.yml raises appropriate error."""
        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)

        with pytest.raises(ValueError, match="No profiles.yml found"):
            settings.load_profiles_yml()

    def test_load_profiles_yml_invalid_yaml(self, temp_profiles_dir: Path):
        """Test that invalid YAML raises appropriate error."""
        profiles_file = temp_profiles_dir / "profiles.yml"
        profiles_file.write_text("invalid: yaml: content: [")

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)

        with pytest.raises(yaml.YAMLError):
            settings.load_profiles_yml()

    def test_load_profiles_yml_empty_file(self, temp_profiles_dir: Path):
        """Test loading empty profiles.yml file."""
        profiles_file = temp_profiles_dir / "profiles.yml"
        profiles_file.write_text("")

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)
        loaded_profiles = settings.load_profiles_yml()

        assert loaded_profiles is None


class TestPrefectDbtSettingsProfilesResolution:
    """Test profiles.yml resolution with templating."""

    def test_resolve_profiles_yml_creates_temp_directory(
        self, temp_profiles_dir: Path, sample_profiles_yml: dict[str, Any]
    ):
        """Test that resolve_profiles_yml creates a temporary directory."""
        profiles_file = temp_profiles_dir / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(sample_profiles_yml, f)

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)

        with settings.resolve_profiles_yml() as temp_dir:
            temp_dir_path = Path(temp_dir)
            assert temp_dir_path.exists()
            assert temp_dir_path.is_dir()

            # Verify profiles.yml was created in temp directory
            temp_profiles_file = temp_dir_path / "profiles.yml"
            assert temp_profiles_file.exists()

            # Verify content was copied
            with open(temp_profiles_file, "r") as f:
                content = yaml.safe_load(f)
                assert content == sample_profiles_yml

        # Verify cleanup
        assert not temp_dir_path.exists()

    async def test_resolve_profiles_yml_with_block_references(
        self, temp_profiles_dir: Path
    ):
        """Test that resolve_profiles_yml resolves Prefect Secret block references for all fields."""
        # Create actual Prefect Secret blocks
        secret_block = Secret(value=SecretStr("secret_password"))
        await secret_block.save("db-password")

        host_secret = Secret(value=SecretStr("localhost"))
        await host_secret.save("db-host")

        user_secret = Secret(value=SecretStr("dbt_user"))
        await user_secret.save("db-user")

        dbname_secret = Secret(value=SecretStr("dbt_db"))
        await dbname_secret.save("db-dbname")

        port_secret = Secret(value=SecretStr("5432"))
        await port_secret.save("db-port")

        profiles_with_blocks = {
            "default": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "{{ prefect.blocks.secret.db-host }}",
                        "password": "{{ prefect.blocks.secret.db-password }}",
                        "user": "{{ prefect.blocks.secret.db-user }}",
                        "dbname": "{{ prefect.blocks.secret.db-dbname }}",
                        "port": "{{ prefect.blocks.secret.db-port }}",
                    }
                }
            }
        }

        profiles_file = temp_profiles_dir / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_with_blocks, f)

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)

        with settings.resolve_profiles_yml() as temp_dir:
            resolved_profiles_file = Path(temp_dir) / "profiles.yml"
            assert resolved_profiles_file.exists()

            with open(resolved_profiles_file, "r") as f:
                resolved_profiles = yaml.safe_load(f)

            # Check that all secret block references were resolved to environment variable calls
            assert (
                resolved_profiles["default"]["targets"]["dev"]["host"]
                == "{{ env_var('PREFECT_BLOCKS_SECRET_DB_HOST') }}"
            )
            assert (
                resolved_profiles["default"]["targets"]["dev"]["password"]
                == "{{ env_var('PREFECT_BLOCKS_SECRET_DB_PASSWORD') }}"
            )
            assert (
                resolved_profiles["default"]["targets"]["dev"]["user"]
                == "{{ env_var('PREFECT_BLOCKS_SECRET_DB_USER') }}"
            )
            assert (
                resolved_profiles["default"]["targets"]["dev"]["dbname"]
                == "{{ env_var('PREFECT_BLOCKS_SECRET_DB_DBNAME') }}"
            )
            assert (
                resolved_profiles["default"]["targets"]["dev"]["port"]
                == "{{ env_var('PREFECT_BLOCKS_SECRET_DB_PORT') }}"
            )

    async def test_resolve_profiles_yml_with_variable_references(
        self, temp_profiles_dir: Path
    ):
        """Test that resolve_profiles_yml resolves Prefect variable references."""
        # Create actual Prefect variables
        await Variable.aset(name="db_host", value="prod.example.com")
        await Variable.aset(name="db_password", value="prod_password")
        await Variable.aset(name="db_user", value="prod_user")

        profiles_with_vars = {
            "default": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "{{ prefect.variables.db_host }}",
                        "password": "{{ prefect.variables.db_password }}",
                        "user": "{{ prefect.variables.db_user }}",
                        "dbname": "prod_db",
                        "port": 5432,
                    }
                }
            }
        }

        profiles_file = temp_profiles_dir / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_with_vars, f)

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)

        with settings.resolve_profiles_yml() as temp_dir:
            temp_profiles_file = Path(temp_dir) / "profiles.yml"
            with open(temp_profiles_file, "r") as f:
                content = yaml.safe_load(f)

            # Verify variable references were resolved
            assert content["default"]["targets"]["dev"]["host"] == "prod.example.com"
            assert content["default"]["targets"]["dev"]["password"] == "prod_password"
            assert content["default"]["targets"]["dev"]["user"] == "prod_user"
            assert content["default"]["targets"]["dev"]["dbname"] == "prod_db"
            assert content["default"]["targets"]["dev"]["port"] == 5432

    async def test_resolve_profiles_yml_with_mixed_references(
        self, temp_profiles_dir: Path
    ):
        """Test that resolve_profiles_yml resolves both block and variable references."""
        # Create actual Prefect Secret block
        mixed_secret = Secret(value=SecretStr("mixed_secret"))
        await mixed_secret.save("mixed-secret")

        # Create actual Prefect variables
        await Variable.aset(name="mixed_host", value="mixed.example.com")
        await Variable.aset(name="mixed_user", value="mixed_user")

        profiles_with_mixed = {
            "default": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "{{ prefect.variables.mixed_host }}",
                        "password": "{{ prefect.blocks.secret.mixed-secret }}",
                        "user": "{{ prefect.variables.mixed_user }}",
                        "dbname": "mixed_db",
                        "port": 5432,
                    }
                }
            }
        }

        profiles_file = temp_profiles_dir / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_with_mixed, f)

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)

        with settings.resolve_profiles_yml() as temp_dir:
            resolved_profiles_file = Path(temp_dir) / "profiles.yml"
            assert resolved_profiles_file.exists()

            with open(resolved_profiles_file, "r") as f:
                resolved_profiles = yaml.safe_load(f)

            # Check that both block and variable references were resolved
            assert (
                resolved_profiles["default"]["targets"]["dev"]["host"]
                == "mixed.example.com"
            )
            assert (
                resolved_profiles["default"]["targets"]["dev"]["password"]
                == "{{ env_var('PREFECT_BLOCKS_SECRET_MIXED_SECRET') }}"
            )
            assert (
                resolved_profiles["default"]["targets"]["dev"]["user"] == "mixed_user"
            )
            assert (
                resolved_profiles["default"]["targets"]["dev"]["dbname"] == "mixed_db"
            )
            assert resolved_profiles["default"]["targets"]["dev"]["port"] == 5432

    def test_resolve_profiles_yml_cleanup_on_exception(
        self, temp_profiles_dir: Path, sample_profiles_yml: dict[str, Any]
    ):
        """Test that resolve_profiles_yml cleans up on exception."""
        profiles_file = temp_profiles_dir / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(sample_profiles_yml, f)

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)

        temp_dir_path = None
        try:
            with settings.resolve_profiles_yml() as temp_dir:
                temp_dir_path = Path(temp_dir)
                assert temp_dir_path.exists()
                # Simulate an exception
                raise Exception("Test exception")
        except Exception:
            # Verify cleanup happened despite exception
            if temp_dir_path:
                assert not temp_dir_path.exists()

    async def test_resolve_profiles_yml_handles_missing_blocks(
        self, temp_profiles_dir: Path
    ):
        """Test that resolve_profiles_yml handles missing block references gracefully."""
        profiles_with_missing_blocks = {
            "default": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "{{ prefect.blocks.secret.nonexistent-block }}",
                        "password": "{{ prefect.blocks.secret.another-missing }}",
                    }
                }
            }
        }

        profiles_file = temp_profiles_dir / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_with_missing_blocks, f)

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)

        # Should raise an error when blocks don't exist
        try:
            with settings.resolve_profiles_yml():
                pass
        except Exception as exc:
            print(f"Exception type: {type(exc)}, message: {exc}")
            assert isinstance(exc, prefect.exceptions.ObjectNotFound)
        else:
            assert False, "Exception not raised for missing blocks"

    async def test_resolve_profiles_yml_handles_missing_variables(
        self, temp_profiles_dir: Path
    ):
        """Test that resolve_profiles_yml handles missing variable references gracefully."""
        profiles_with_missing_vars = {
            "default": {
                "targets": {
                    "dev": {
                        "type": "postgres",
                        "host": "{{ prefect.variables.NONEXISTENT_VAR }}",
                        "password": "{{ prefect.variables.ANOTHER_MISSING }}",
                    }
                }
            }
        }

        profiles_file = temp_profiles_dir / "profiles.yml"
        with open(profiles_file, "w") as f:
            yaml.dump(profiles_with_missing_vars, f)

        settings = PrefectDbtSettings(profiles_dir=temp_profiles_dir)

        # Test that missing variables are handled gracefully (may return None or empty string)
        with settings.resolve_profiles_yml() as temp_dir:
            temp_profiles_file = Path(temp_dir) / "profiles.yml"
            with open(temp_profiles_file, "r") as f:
                content = yaml.safe_load(f)

            # Verify that missing variables are handled (either None, empty string, or the original template string)
            host_value = content["default"]["targets"]["dev"]["host"]
            password_value = content["default"]["targets"]["dev"]["password"]

            # The behavior depends on how Prefect handles missing variables
            # It could be None, empty string, or the original template string
            assert host_value in [None, "", "{{ prefect.variables.NONEXISTENT_VAR }}"]
            assert password_value in [
                None,
                "",
                "{{ prefect.variables.ANOTHER_MISSING }}",
            ]

"""
Unit tests for prefect-dbt settings
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from dbt_common.events.base_types import EventLevel
from prefect_dbt.core.settings import PrefectDbtSettings


class TestPrefectDbtSettings:
    """Test cases for PrefectDbtSettings class"""

    def test_default_initialization(self) -> None:
        """Test default initialization of settings"""
        settings = PrefectDbtSettings()

        assert settings.project_dir == Path.cwd()
        assert settings.target_path == Path("target")
        assert isinstance(settings.log_level, EventLevel)

    def test_custom_initialization(self) -> None:
        """Test initialization with custom values"""
        custom_project_dir = Path("/custom/project")
        custom_target_path = Path("custom_target")

        settings = PrefectDbtSettings(
            project_dir=custom_project_dir, target_path=custom_target_path
        )

        assert settings.project_dir == custom_project_dir
        assert settings.target_path == custom_target_path

    def test_load_profiles_yml_success(self) -> None:
        """Test successful loading of profiles.yml"""
        # Create a temporary profiles.yml file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            profiles_content = {
                "my_profile": {
                    "targets": {
                        "dev": {"type": "postgres", "host": "localhost", "port": 5432}
                    }
                }
            }

            profiles_file = temp_path / "profiles.yml"
            with open(profiles_file, "w") as f:
                yaml.dump(profiles_content, f)

            settings = PrefectDbtSettings(profiles_dir=temp_path)
            result = settings.load_profiles_yml()

            assert result == profiles_content

    def test_load_profiles_yml_not_found(self) -> None:
        """Test loading profiles.yml when file doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = PrefectDbtSettings(profiles_dir=temp_path)

            with pytest.raises(ValueError, match="No profiles.yml found"):
                settings.load_profiles_yml()

    @patch("prefect_dbt.core.settings.run_coro_as_sync")
    @patch("prefect_dbt.core.settings.resolve_block_document_references")
    @patch("prefect_dbt.core.settings.resolve_variables")
    def test_resolve_profiles_yml(
        self,
        mock_resolve_variables: Mock,
        mock_resolve_block_document_references: Mock,
        mock_run_coro_as_sync: Mock,
    ) -> None:
        """Test resolve_profiles_yml context manager"""
        # Mock the async functions
        mock_run_coro_as_sync.side_effect = lambda x: x

        # Create a temporary profiles.yml file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            original_profiles = {
                "my_profile": {
                    "targets": {
                        "dev": {"type": "postgres", "host": "{{ env_var('DB_HOST') }}"}
                    }
                }
            }

            resolved_profiles = {
                "my_profile": {
                    "targets": {"dev": {"type": "postgres", "host": "localhost"}}
                }
            }

            profiles_file = temp_path / "profiles.yml"
            with open(profiles_file, "w") as f:
                yaml.dump(original_profiles, f)

            # Mock the resolution functions
            mock_resolve_block_document_references.return_value = resolved_profiles
            mock_resolve_variables.return_value = resolved_profiles

            settings = PrefectDbtSettings(profiles_dir=temp_path)

            with settings.resolve_profiles_yml() as resolved_temp_dir:
                resolved_temp_path = Path(resolved_temp_dir)
                resolved_profiles_file = resolved_temp_path / "profiles.yml"

                assert resolved_profiles_file.exists()

                with open(resolved_profiles_file, "r") as f:
                    loaded_profiles = yaml.safe_load(f)

                assert loaded_profiles == resolved_profiles

    def test_resolve_profiles_yml_cleanup(self) -> None:
        """Test that temporary directory is cleaned up after context exit"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            profiles_content = {"test": "content"}

            profiles_file = temp_path / "profiles.yml"
            with open(profiles_file, "w") as f:
                yaml.dump(profiles_content, f)

            settings = PrefectDbtSettings(profiles_dir=temp_path)

            with patch("prefect_dbt.core.settings.run_coro_as_sync") as mock_run_coro:
                mock_run_coro.side_effect = lambda x: x

                with patch(
                    "prefect_dbt.core.settings.resolve_block_document_references"
                ) as mock_resolve_refs:
                    mock_resolve_refs.return_value = profiles_content

                    with patch(
                        "prefect_dbt.core.settings.resolve_variables"
                    ) as mock_resolve_vars:
                        mock_resolve_vars.return_value = profiles_content

                        with settings.resolve_profiles_yml() as resolved_temp_dir:
                            resolved_temp_path = Path(resolved_temp_dir)
                            # Verify the directory exists during context
                            assert resolved_temp_path.exists()

                        # Verify the directory is cleaned up after context exit
                        assert not resolved_temp_path.exists()

    def test_log_level_from_prefect_settings(self) -> None:
        """Test that log level is derived from Prefect settings"""
        with patch(
            "prefect_dbt.core.settings.get_current_settings"
        ) as mock_get_settings:
            mock_settings = Mock()
            mock_settings.logging.level = "INFO"
            mock_get_settings.return_value = mock_settings

            settings = PrefectDbtSettings()
            assert settings.log_level == EventLevel.INFO

    def test_custom_log_level(self) -> None:
        """Test setting custom log level"""
        settings = PrefectDbtSettings(log_level=EventLevel.DEBUG)
        assert settings.log_level == EventLevel.DEBUG

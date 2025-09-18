"""
Unit tests for prefect-dbt utilities.
"""

import os
from pathlib import Path
from unittest.mock import patch

from prefect_dbt.utilities import (
    find_profiles_dir,
    format_resource_id,
    kwargs_to_args,
    replace_with_env_var_call,
)

from prefect.types.names import MAX_ASSET_KEY_LENGTH


class TestFindProfilesDir:
    """Test cases for find_profiles_dir function."""

    def test_find_profiles_dir_with_profiles_in_cwd(self, tmp_path: Path) -> None:
        """Test when profiles.yml exists in current working directory."""
        # Create a profiles.yml file in the temp directory
        profiles_file: Path = tmp_path / "profiles.yml"
        profiles_file.write_text("test content")

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = find_profiles_dir()
            assert result == tmp_path

    def test_find_profiles_dir_without_profiles_in_cwd(self) -> None:
        """Test when profiles.yml doesn't exist in current working directory."""
        with (
            patch("pathlib.Path.cwd") as mock_cwd,
            patch("pathlib.Path.home") as mock_home,
        ):
            # Mock current working directory without profiles.yml
            mock_cwd.return_value = Path("/some/random/path")

            # Mock home directory
            mock_home_dir = Path("/home/user")
            mock_home.return_value = mock_home_dir

            result = find_profiles_dir()
            assert result == mock_home_dir / ".dbt"

    def test_find_profiles_dir_with_symlink(self, tmp_path: Path) -> None:
        """Test when profiles.yml is a symlink."""
        # Create a profiles.yml file in the temp directory
        profiles_file: Path = tmp_path / "profiles.yml"
        profiles_file.write_text("test content")

        # Create a symlink to the profiles.yml
        symlink_dir = tmp_path / "symlink_dir"
        symlink_dir.mkdir()
        symlink_file = symlink_dir / "profiles.yml"
        symlink_file.symlink_to(profiles_file)

        with patch("pathlib.Path.cwd", return_value=symlink_dir):
            result = find_profiles_dir()
            assert result == symlink_dir


class TestReplaceWithEnvVarCall:
    """Test cases for replace_with_env_var_call function."""

    def test_replace_with_env_var_call_with_string_value(self) -> None:
        """Test with string value."""
        placeholder = "database_host"
        value = "localhost"

        result = replace_with_env_var_call(placeholder, value)

        expected_env_var = "DATABASE_HOST"
        expected_template = "{{ env_var('DATABASE_HOST') }}"

        assert result == expected_template
        assert os.environ[expected_env_var] == value

        # Clean up
        del os.environ[expected_env_var]

    def test_replace_with_env_var_call_with_non_string_value(self) -> None:
        """Test with non-string value (should be converted to string)."""
        placeholder = "port_number"
        value = 5432

        result = replace_with_env_var_call(placeholder, value)

        expected_env_var = "PORT_NUMBER"
        expected_template = "{{ env_var('PORT_NUMBER') }}"

        assert result == expected_template
        assert os.environ[expected_env_var] == "5432"

        # Clean up
        del os.environ[expected_env_var]

    def test_replace_with_env_var_call_with_complex_placeholder(self) -> None:
        """Test with complex placeholder containing various characters."""
        placeholder = "my-project@v1.0.0:database/schema"
        value = "complex_value"

        result = replace_with_env_var_call(placeholder, value)

        expected_env_var = "MY_PROJECT_V1_0_0_DATABASE_SCHEMA"
        expected_template = "{{ env_var('MY_PROJECT_V1_0_0_DATABASE_SCHEMA') }}"

        assert result == expected_template
        assert os.environ[expected_env_var] == value

        # Clean up
        del os.environ[expected_env_var]

    def test_replace_with_env_var_call_with_none_value(self) -> None:
        """Test with None value."""
        placeholder = "none_value"
        value = None

        result = replace_with_env_var_call(placeholder, value)

        expected_env_var = "NONE_VALUE"
        expected_template = "{{ env_var('NONE_VALUE') }}"

        assert result == expected_template
        assert os.environ[expected_env_var] == "None"

        # Clean up
        del os.environ[expected_env_var]

    def test_replace_with_env_var_call_with_boolean_value(self) -> None:
        """Test with boolean value."""
        placeholder = "boolean_flag"
        value = True

        result = replace_with_env_var_call(placeholder, value)

        expected_env_var = "BOOLEAN_FLAG"
        expected_template = "{{ env_var('BOOLEAN_FLAG') }}"

        assert result == expected_template
        assert os.environ[expected_env_var] == "True"

        # Clean up
        del os.environ[expected_env_var]

    def test_replace_with_env_var_call_overwrites_existing(self) -> None:
        """Test that function overwrites existing environment variable."""
        placeholder = "existing_var"
        original_value = "original_value"
        new_value = "new_value"

        # Set original value
        os.environ["EXISTING_VAR"] = original_value

        result = replace_with_env_var_call(placeholder, new_value)

        expected_template = "{{ env_var('EXISTING_VAR') }}"

        assert result == expected_template
        assert os.environ["EXISTING_VAR"] == new_value

        # Clean up
        del os.environ["EXISTING_VAR"]


class TestFormatResourceId:
    """Test cases for format_resource_id function."""

    def test_format_resource_id_with_simple_relation(self) -> None:
        """Test with simple relation name."""
        adapter_type = "postgres"
        relation_name = "my_table"

        result = format_resource_id(adapter_type, relation_name)
        expected = "postgres://my_table"

        assert result == expected

    def test_format_resource_id_with_mixed_quotes_and_dots(self) -> None:
        """Test with mixed quotes and dots."""
        adapter_type = "duckdb"
        relation_name = '"my_catalog"."my_schema"."my.table"'

        result = format_resource_id(adapter_type, relation_name)
        expected = "duckdb://my_catalog/my_schema/my/table"

        assert result == expected

    def test_format_resource_id_with_restricted_characters(self) -> None:
        """Test with restricted characters."""
        adapter_type = "duckdb"
        relation_name = "`my_table`"

        result = format_resource_id(adapter_type, relation_name)
        expected = "duckdb://my_table"

        assert result == expected

    def test_format_resource_id_over_max_length(self) -> None:
        """Test with over max length."""
        adapter_type = "duckdb"
        relation_name = "a" * MAX_ASSET_KEY_LENGTH

        result = len(format_resource_id(adapter_type, relation_name))
        expected = MAX_ASSET_KEY_LENGTH

        assert result == expected


class TestKwargsToArgs:
    """Test cases for kwargs_to_args function."""

    def test_kwargs_to_args_with_simple_kwargs(self) -> None:
        """Test with simple kwargs."""
        kwargs = {"a": 1, "b": 2, "c": 3}

        result = kwargs_to_args(kwargs)
        expected = ["--a", "1", "--b", "2", "--c", "3"]

        assert result == expected

    def test_kwargs_to_args_with_boolean_kwargs(self) -> None:
        """Test with boolean kwargs."""
        kwargs = {"a": True, "b": False, "c": True}

        result = kwargs_to_args(kwargs)
        expected = ["--a", "--no-b", "--c"]

        assert result == expected

    def test_kwargs_to_args_with_list_kwargs(self) -> None:
        """Test with list kwargs."""
        kwargs = {"a": [1, 2, 3], "b": [4, 5, 6]}

        result = kwargs_to_args(kwargs)
        expected = ["--a", "1", "2", "3", "--b", "4", "5", "6"]

        assert result == expected

    def test_kwargs_to_args_with_existing_args(self) -> None:
        """Test with existing args that don't conflict with kwargs."""
        kwargs = {"a": 1, "b": 2}
        args = ["--c", "3", "--d", "4"]

        result = kwargs_to_args(kwargs, args)
        expected = ["--c", "3", "--d", "4", "--a", "1", "--b", "2"]

        assert result == expected

    def test_kwargs_to_args_args_priority_over_kwargs(self) -> None:
        """Test that args take priority over kwargs when conflicts exist."""
        kwargs = {"a": 1, "b": 2, "c": 3}
        args = ["--a", "10", "--d", "4"]

        result = kwargs_to_args(kwargs, args)
        expected = ["--a", "10", "--d", "4", "--b", "2", "--c", "3"]

        assert result == expected

    def test_kwargs_to_args_boolean_conflict(self) -> None:
        """Test boolean flag conflicts between args and kwargs."""
        kwargs = {"a": True, "b": False}
        args = ["--a", "--no-b"]

        result = kwargs_to_args(kwargs, args)
        expected = ["--a", "--no-b"]

        assert result == expected

    def test_kwargs_to_args_list_conflict(self) -> None:
        """Test list flag conflicts between args and kwargs."""
        kwargs = {"a": [1, 2, 3], "b": [4, 5]}
        args = ["--a", "10", "20"]

        result = kwargs_to_args(kwargs, args)
        expected = ["--a", "10", "20", "--b", "4", "5"]

        assert result == expected

    def test_kwargs_to_args_no_args_provided(self) -> None:
        """Test behavior when no args are provided (backward compatibility)."""
        kwargs = {"a": 1, "b": 2}

        result = kwargs_to_args(kwargs)
        expected = ["--a", "1", "--b", "2"]

        assert result == expected

    def test_kwargs_to_args_preserves_positional_args(self) -> None:
        """Test that positional arguments (like dbt commands) are preserved.

        This test verifies the fix for issue #18980 where the dbt command
        was being dropped from the args list.
        """
        # This is the exact case from issue #18980
        kwargs = {
            "profiles_dir": "/path/to/profiles",
            "project_dir": "/path/to/project",
            "target_path": "target",
        }
        args = ["debug", "--target", "prod"]

        result = kwargs_to_args(kwargs, args)

        # The command "debug" should be preserved at the beginning
        assert result[0] == "debug"
        # The user's --target flag should be preserved
        assert "--target" in result
        assert "prod" in result
        # The kwargs should be added
        assert "--profiles-dir" in result
        assert "/path/to/profiles" in result

        # Specifically test the order: positional args first, then flags
        assert result[:3] == ["debug", "--target", "prod"]

    def test_kwargs_to_args_multiple_positional_args(self) -> None:
        """Test that multiple positional arguments are preserved."""
        kwargs = {"some_flag": "value"}
        args = ["command", "subcommand", "--option", "val"]

        result = kwargs_to_args(kwargs, args)

        # Both positional args should be preserved
        assert result[:2] == ["command", "subcommand"]
        assert "--option" in result
        assert "val" in result
        assert "--some-flag" in result
        assert "value" in result

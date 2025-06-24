"""
Unit tests for prefect-dbt utilities
"""

import os
from pathlib import Path
from unittest.mock import patch

from prefect_dbt.utilities import (
    find_profiles_dir,
    format_resource_id,
    replace_with_env_var_call,
)


def test_find_profiles_dir_with_profiles_in_cwd(tmp_path: Path) -> None:
    """Test when profiles.yml exists in current working directory"""
    # Create a profiles.yml file in the temp directory
    profiles_file: Path = tmp_path / "profiles.yml"
    profiles_file.write_text("test content")

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = find_profiles_dir()
        assert result == tmp_path


def test_find_profiles_dir_without_profiles_in_cwd() -> None:
    """Test when profiles.yml doesn't exist in current working directory"""
    with patch("pathlib.Path.cwd") as mock_cwd, patch("pathlib.Path.home") as mock_home:
        # Mock current working directory without profiles.yml
        mock_cwd.return_value = Path("/some/random/path")

        # Mock home directory
        mock_home_dir = Path("/home/user")
        mock_home.return_value = mock_home_dir

        result = find_profiles_dir()
        assert result == mock_home_dir / ".dbt"


def test_replace_with_env_var_call_with_non_string_value() -> None:
    """Test with non-string value (should be converted to string)"""
    placeholder = "port_number"
    value = 5432

    result = replace_with_env_var_call(placeholder, value)

    expected_env_var = "PORT_NUMBER"
    expected_template = "{{ env_var('PORT_NUMBER') }}"

    assert result == expected_template
    assert os.environ[expected_env_var] == "5432"

    del os.environ[expected_env_var]


def test_replace_with_env_var_call() -> None:
    """Test with complex placeholder containing various characters"""
    placeholder = "my-project@v1.0.0:database/schema"
    value = "complex_value"

    result = replace_with_env_var_call(placeholder, value)

    expected_env_var = "MY_PROJECT_V1_0_0_DATABASE_SCHEMA"
    expected_template = "{{ env_var('MY_PROJECT_V1_0_0_DATABASE_SCHEMA') }}"

    assert result == expected_template
    assert os.environ[expected_env_var] == value

    del os.environ[expected_env_var]


def test_format_resource_id() -> None:
    """Test with complex relation name"""
    adapter_type = "oracle"
    relation_name = '"SCHEMA_NAME"."TABLE_NAME"'

    result = format_resource_id(adapter_type, relation_name)
    expected = "oracle://SCHEMA_NAME/TABLE_NAME"

    assert result == expected

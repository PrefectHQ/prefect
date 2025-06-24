"""
Unit tests for prefect-dbt utilities.
"""

import os
from pathlib import Path
from unittest.mock import patch

from prefect_dbt.utilities import (
    find_profiles_dir,
    format_resource_id,
    replace_with_env_var_call,
)


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

    def test_find_profiles_dir_with_different_case(self, tmp_path: Path) -> None:
        """Test when profiles.yml exists with different case."""
        # Create a profiles.yml file with different case
        profiles_file: Path = tmp_path / "PROFILES.YML"
        profiles_file.write_text("test content")

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = find_profiles_dir()
            # Should still find the file regardless of case on case-insensitive systems
            if os.name == "nt":  # Windows
                assert result == tmp_path
            else:  # Unix-like systems
                # On case-sensitive systems, it should fall back to home directory
                with patch("pathlib.Path.home") as mock_home:
                    mock_home_dir = Path("/home/user")
                    mock_home.return_value = mock_home_dir
                    result = find_profiles_dir()
                    assert result == mock_home_dir / ".dbt"


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

    def test_replace_with_env_var_call_with_special_characters(self) -> None:
        """Test with placeholder containing special characters."""
        placeholder = "my-database!@#$%^&*()_+{}|:<>?[]\\;'\",./"
        value = "special_value"

        result = replace_with_env_var_call(placeholder, value)

        expected_env_var = "MY_DATABASE_____________________________"
        expected_template = "{{ env_var('MY_DATABASE_____________________________') }}"

        assert result == expected_template
        assert os.environ[expected_env_var] == value

        # Clean up
        del os.environ[expected_env_var]

    def test_replace_with_env_var_call_with_unicode(self) -> None:
        """Test with placeholder containing unicode characters."""
        placeholder = "my-database-éñ-中文"
        value = "unicode_value"

        result = replace_with_env_var_call(placeholder, value)

        expected_env_var = "MY_DATABASE_ÉÑ_中文"
        expected_template = "{{ env_var('MY_DATABASE_ÉÑ_中文') }}"

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

    def test_format_resource_id_with_quoted_relation(self) -> None:
        """Test with quoted relation name."""
        adapter_type = "oracle"
        relation_name = '"SCHEMA_NAME"."TABLE_NAME"'

        result = format_resource_id(adapter_type, relation_name)
        expected = "oracle://SCHEMA_NAME/TABLE_NAME"

        assert result == expected

    def test_format_resource_id_with_dots(self) -> None:
        """Test with relation name containing dots."""
        adapter_type = "snowflake"
        relation_name = "database.schema.table"

        result = format_resource_id(adapter_type, relation_name)
        expected = "snowflake://database/schema/table"

        assert result == expected

    def test_format_resource_id_with_mixed_quotes(self) -> None:
        """Test with relation name containing mixed quotes."""
        adapter_type = "bigquery"
        relation_name = '"project"."dataset"."table"'

        result = format_resource_id(adapter_type, relation_name)
        expected = "bigquery://project/dataset/table"

        assert result == expected

    def test_format_resource_id_with_special_characters(self) -> None:
        """Test with relation name containing special characters."""
        adapter_type = "redshift"
        relation_name = "my-table_with_underscores"

        result = format_resource_id(adapter_type, relation_name)
        expected = "redshift://my-table_with_underscores"

        assert result == expected

    def test_format_resource_id_with_empty_string(self) -> None:
        """Test with empty relation name."""
        adapter_type = "sqlite"
        relation_name = ""

        result = format_resource_id(adapter_type, relation_name)
        expected = "sqlite://"

        assert result == expected

    def test_format_resource_id_with_unicode(self) -> None:
        """Test with relation name containing unicode characters."""
        adapter_type = "mysql"
        relation_name = "tabelle_mit_umlauten"

        result = format_resource_id(adapter_type, relation_name)
        expected = "mysql://tabelle_mit_umlauten"

        assert result == expected

    def test_format_resource_id_with_complex_schema(self) -> None:
        """Test with complex schema structure."""
        adapter_type = "postgres"
        relation_name = '"public"."my_schema"."my_table"'

        result = format_resource_id(adapter_type, relation_name)
        expected = "postgres://public/my_schema/my_table"

        assert result == expected

    def test_format_resource_id_with_numeric_names(self) -> None:
        """Test with numeric relation names."""
        adapter_type = "sqlserver"
        relation_name = "123_table_456"

        result = format_resource_id(adapter_type, relation_name)
        expected = "sqlserver://123_table_456"

        assert result == expected

    def test_format_resource_id_with_case_sensitivity(self) -> None:
        """Test case sensitivity handling."""
        adapter_type = "PostgreSQL"
        relation_name = "MyTable"

        result = format_resource_id(adapter_type, relation_name)
        expected = "PostgreSQL://MyTable"

        assert result == expected

    def test_format_resource_id_with_multiple_dots(self) -> None:
        """Test with multiple dots in relation name."""
        adapter_type = "databricks"
        relation_name = "catalog.schema.table.column"

        result = format_resource_id(adapter_type, relation_name)
        expected = "databricks://catalog/schema/table/column"

        assert result == expected

    def test_format_resource_id_with_mixed_quotes_and_dots(self) -> None:
        """Test with mixed quotes and dots."""
        adapter_type = "duckdb"
        relation_name = '"my_catalog"."my_schema"."my.table"'

        result = format_resource_id(adapter_type, relation_name)
        expected = "duckdb://my_catalog/my_schema/my/table"

        assert result == expected

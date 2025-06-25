from pathlib import Path
from unittest.mock import patch

import pytest
from prefect_dbt.cli.configs.base import GlobalConfigs, TargetConfigs

SAMPLE_PROFILES = {
    "jaffle_shop": {
        "outputs": {
            "dev": {
                "type": "duckdb",
                "path": "jaffle_shop.duckdb",
                "schema": "main",
                "threads": 4,
            },
            "prod": {
                "type": "duckdb",
                "path": "/data/prod/jaffle_shop.duckdb",
                "schema": "main",
                "threads": 8,
            },
        },
        "target": "prod",
    },
    "other_project": {
        "outputs": {
            "dev": {
                "type": "duckdb",
                "path": "other_project.duckdb",
                "schema": "analytics",
                "threads": 4,
            }
        },
        "target": "dev",
    },
    "config": {"partial_parse": True},
}


@pytest.fixture
def mock_load_profiles():
    with patch(
        "prefect_dbt.core.settings.PrefectDbtSettings.load_profiles_yml"
    ) as mock:
        mock.return_value = SAMPLE_PROFILES
        yield mock


def test_target_configs_get_configs():
    target_configs = TargetConfigs(
        type="snowflake",
        schema="schema_input",
        threads=5,
        extras={
            "extra_input": 1,
            "null_input": None,
            "key_path": Path("path/to/key"),
        },
    )
    assert hasattr(target_configs, "_is_anonymous")
    # get_configs ignore private attrs
    assert target_configs.get_configs() == dict(
        type="snowflake",
        schema="schema_input",
        threads=5,
        extra_input=1,
        key_path=str(Path("path/to/key")),
    )


def test_target_configs_get_configs_duplicate_keys():
    with pytest.raises(ValueError, match="The keyword, schema"):
        target_configs = TargetConfigs(
            type="snowflake",
            schema="schema_input",
            threads=5,
            extras={"extra_input": 1, "schema": "something else"},
        )
        target_configs.get_configs()


def test_global_configs():
    global_configs = GlobalConfigs(log_format="json", send_anonymous_usage_stats=False)
    assert global_configs.log_format == "json"
    assert global_configs.send_anonymous_usage_stats is False


def test_from_profiles_yml_default_profile_target(mock_load_profiles):
    target_configs = TargetConfigs.from_profiles_yml()

    assert target_configs.type == "duckdb"
    assert target_configs.schema_ == "main"
    assert target_configs.threads == 8
    assert target_configs.extras == {"path": "/data/prod/jaffle_shop.duckdb"}


def test_from_profiles_yml_explicit_profile_target(mock_load_profiles):
    target_configs = TargetConfigs.from_profiles_yml(
        profile_name="other_project", target_name="dev"
    )

    assert target_configs.type == "duckdb"
    assert target_configs.schema_ == "analytics"
    assert target_configs.threads == 4
    assert target_configs.extras == {"path": "other_project.duckdb"}


def test_from_profiles_yml_invalid_profile(mock_load_profiles):
    with pytest.raises(ValueError, match="Profile invalid_profile not found"):
        TargetConfigs.from_profiles_yml(profile_name="invalid_profile")


def test_from_profiles_yml_invalid_target(mock_load_profiles):
    with pytest.raises(ValueError, match="Target invalid_target not found"):
        TargetConfigs.from_profiles_yml(
            profile_name="jaffle_shop", target_name="invalid_target"
        )


def test_from_profiles_yml_no_outputs(mock_load_profiles):
    mock_load_profiles.return_value = {"broken": {"some_other_key": {}}}
    with pytest.raises(ValueError, match="No outputs found in profile broken"):
        TargetConfigs.from_profiles_yml(profile_name="broken")


def test_from_profiles_yml_no_schema(mock_load_profiles):
    mock_load_profiles.return_value = {
        "test": {
            "outputs": {
                "dev": {
                    "type": "postgres",
                    "threads": 4,
                    # Missing schema field
                    "host": "localhost",
                }
            },
            "target": "dev",
        }
    }
    with pytest.raises(ValueError, match="No schema found"):
        TargetConfigs.from_profiles_yml(profile_name="test")


def test_from_profiles_yml_alternative_schema_keys(mock_load_profiles):
    mock_profiles = {
        "test": {
            "outputs": {
                "dev": {
                    "type": "bigquery",
                    "threads": 4,
                    "dataset": "my_dataset",  # Alternative to schema
                    "project": "my_project",
                }
            },
            "target": "dev",
        }
    }
    mock_load_profiles.return_value = mock_profiles

    target_configs = TargetConfigs.from_profiles_yml(profile_name="test")
    assert target_configs.schema_ == "my_dataset"

from pathlib import Path

import pytest
from prefect_dbt.cli.configs.base import GlobalConfigs, TargetConfigs


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

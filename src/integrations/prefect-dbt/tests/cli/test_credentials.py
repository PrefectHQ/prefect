import pytest
from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1.error_wrappers import ValidationError
else:
    from pydantic.error_wrappers import ValidationError

from prefect_dbt.cli.credentials import DbtCliProfile, GlobalConfigs, TargetConfigs


@pytest.mark.parametrize("configs_type", ["dict", "model"])
def test_dbt_cli_profile_init(configs_type):
    target_configs = dict(type="snowflake", schema="schema")
    global_configs = dict(use_colors=False)
    if configs_type == "model":
        target_configs = TargetConfigs.parse_obj(target_configs)
        global_configs = GlobalConfigs.parse_obj(global_configs)

    dbt_cli_profile = DbtCliProfile(
        name="test_name",
        target="dev",
        target_configs=target_configs,
        global_configs=global_configs,
    )
    assert isinstance(dbt_cli_profile.target_configs, TargetConfigs)
    assert dbt_cli_profile.name == "test_name"
    assert dbt_cli_profile.target == "dev"


def test_dbt_cli_profile_init_validation_failed():
    # 6 instead of 2 now because it tries to validate each of the Union types
    with pytest.raises(ValidationError, match="6 validation errors for DbtCliProfile"):
        DbtCliProfile(
            name="test_name", target="dev", target_configs={"extras": {"field": "abc"}}
        )


def test_dbt_cli_profile_get_profile():
    target_configs = dict(type="snowflake", schema="analysis")
    global_configs = dict(use_colors=False)
    dbt_cli_profile = DbtCliProfile(
        name="test_name",
        target="dev",
        target_configs=target_configs,
        global_configs=global_configs,
    )
    actual = dbt_cli_profile.get_profile()
    expected_target_configs = target_configs.copy()
    expected_target_configs["threads"] = 4
    expected = {
        "config": global_configs,
        "test_name": {
            "target": "dev",
            "outputs": {"dev": expected_target_configs},
        },
    }
    assert actual == expected


@pytest.mark.parametrize(
    "target_configs_request",
    [
        "snowflake_target_configs",
        "dict_target_configs",
        "class_target_configs",
    ],
)
def test_dbt_cli_profile_save_load_roundtrip(target_configs_request, request):
    target_configs = request.getfixturevalue(target_configs_request)
    dbt_cli_profile = DbtCliProfile(
        name="my_name",
        target="dev",
        target_configs=target_configs,
    )
    block_name = target_configs_request.replace("_", "-")
    dbt_cli_profile.save(block_name)
    dbt_cli_profile_loaded = DbtCliProfile.load(block_name)
    assert dbt_cli_profile_loaded.get_profile()

import pytest
from prefect_dbt.cli.credentials import DbtCliProfile, GlobalConfigs, TargetConfigs
from pydantic import ValidationError
from typing_extensions import Literal


@pytest.mark.parametrize("configs_type", ["dict", "model"])
def test_dbt_cli_profile_init(configs_type: Literal["dict", "model"]):
    target_configs = dict(type="snowflake", schema="schema")
    global_configs = dict(use_colors=False)
    if configs_type == "model":
        target_configs = TargetConfigs.model_validate(target_configs)
        global_configs = GlobalConfigs.model_validate(global_configs)

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
    with pytest.raises(ValidationError):
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
async def test_dbt_cli_profile_save_load_roundtrip(
    target_configs_request: str, request: pytest.FixtureRequest
):
    target_configs = request.getfixturevalue(target_configs_request)
    dbt_cli_profile = DbtCliProfile(
        name="my_name",
        target="dev",
        target_configs=target_configs,
    )
    block_name = target_configs_request.replace("_", "-")
    await dbt_cli_profile.save(block_name)
    dbt_cli_profile_loaded = await DbtCliProfile.load(block_name)
    assert dbt_cli_profile_loaded.get_profile()

from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import Secret as PydanticSecret
from pydantic import SecretStr

from prefect.blocks.system import DateTime, Secret
from prefect.types._datetime import DateTime as PydanticDateTime


@pytest.mark.usefixtures("ignore_prefect_deprecation_warnings")
def test_datetime():
    DateTime(value=PydanticDateTime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))).save(
        name="test"
    )
    api_block = DateTime.load("test")
    assert api_block.value == PydanticDateTime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))


@pytest.mark.parametrize(
    "value",
    ["test", {"key": "value"}, ["test"]],
    ids=["string", "dict", "list"],
)
def test_secret_block(value: Any):
    Secret(value=value).save(name="test")
    api_block = Secret.load("test")
    assert isinstance(api_block.value, PydanticSecret)

    assert api_block.get() == value


@pytest.mark.parametrize(
    "value",
    [
        SecretStr("test"),
        PydanticSecret[dict[str, str]]({"key": "value"}),
        PydanticSecret[list[str]](["test"]),
    ],
    ids=["secret_string", "secret_dict", "secret_list"],
)
def test_secret_block_with_pydantic_secret(value: Any):
    Secret(value=value).save(name="test")
    api_block = Secret.load("test")
    assert isinstance(api_block.value, PydanticSecret)

    assert api_block.get() == value.get_secret_value()

import pendulum
import pytest
from pydantic import Secret as PydanticSecret
from pydantic import SecretStr
from pydantic_extra_types.pendulum_dt import DateTime as PydanticDateTime

from prefect.blocks.system import DateTime, Secret


def test_datetime(ignore_prefect_deprecation_warnings):
    DateTime(value=PydanticDateTime(2022, 1, 1)).save(name="test")
    api_block = DateTime.load("test")
    assert api_block.value == pendulum.datetime(2022, 1, 1)


@pytest.mark.parametrize(
    "value",
    ["test", {"key": "value"}, ["test"]],
    ids=["string", "dict", "list"],
)
def test_secret_block(value):
    Secret(value=value).save(name="test")
    api_block = Secret.load("test")
    assert isinstance(api_block.value, PydanticSecret)

    assert api_block.get() == value


@pytest.mark.parametrize(
    "value",
    [
        SecretStr("test"),
        PydanticSecret[dict]({"key": "value"}),
        PydanticSecret[list](["test"]),
    ],
    ids=["secret_string", "secret_dict", "secret_list"],
)
def test_secret_block_with_pydantic_secret(value):
    Secret(value=value).save(name="test")
    api_block = Secret.load("test")
    assert isinstance(api_block.value, PydanticSecret)

    assert api_block.get() == value.get_secret_value()

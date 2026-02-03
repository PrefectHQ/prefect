import uuid
from typing import Any

import pytest
from pydantic import Secret as PydanticSecret
from pydantic import SecretStr

from prefect.blocks.system import Secret


@pytest.mark.parametrize(
    "value",
    ["test", {"key": "value"}, ["test"]],
    ids=["string", "dict", "list"],
)
def test_secret_block(value: Any):
    block_name = f"test-{uuid.uuid4()}"
    Secret(value=value).save(name=block_name)
    api_block = Secret.load(block_name)
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
    block_name = f"test-{uuid.uuid4()}"
    Secret(value=value).save(name=block_name)
    api_block = Secret.load(block_name)
    assert isinstance(api_block.value, PydanticSecret)

    assert api_block.get() == value.get_secret_value()

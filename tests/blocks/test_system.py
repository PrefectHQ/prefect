from datetime import date
from uuid import UUID

import pendulum
import pytest
from pydantic import Secret as PydanticSecret
from pydantic import SecretStr
from pydantic_extra_types.pendulum_dt import DateTime as PydanticDateTime

from prefect.blocks.system import DateTime, Secret, SecretMap


def test_datetime():
    DateTime(value=PydanticDateTime(2022, 1, 1)).save(name="test")
    api_block = DateTime.load("test")
    assert api_block.value == pendulum.datetime(2022, 1, 1)


@pytest.mark.parametrize(
    "value",
    ["test", SecretStr("test")],
    ids=["string", "secret_str"],
)
def test_secret_block(value):
    Secret(value=value).save(name="test")
    api_block = Secret.load("test")
    assert isinstance(api_block.value, SecretStr)

    assert api_block.get() == "test"


class TestSecretMap:
    @pytest.mark.parametrize(
        "key, value",
        [
            # (1, "int_secret"),
            (3.14, "float_secret"),
            ("string_key", "string_secret"),
            ((1, "tuple"), "tuple_secret"),
        ],
    )
    def test_secret_map_with_various_hashable_types(self, key, value):
        secret_map = SecretMap(value={key: value})

        secret_map.save(name="test")

        assert secret_map.get()[key] == value

        assert isinstance(secret_map.value[key], PydanticSecret)

        assert secret_map.value[key].get_secret_value() == value

        breakpoint()

        assert SecretMap.load("test") == secret_map, secret_map.value

    def test_secret_map_with_multiple_pairs(self):
        secret_map = SecretMap(
            value={
                "string_key": "string_secret",
                42: "int_secret",
                (1, "tuple"): "tuple_secret",
                date(2023, 8, 14): "date_secret",
                UUID("12345678-1234-5678-1234-567812345678"): "uuid_secret",
            }
        )

        assert secret_map.get() == {
            "string_key": "string_secret",
            42: "int_secret",
            (1, "tuple"): "tuple_secret",
            date(2023, 8, 14): "date_secret",
            UUID("12345678-1234-5678-1234-567812345678"): "uuid_secret",
        }

        for key, value in secret_map.value.items():
            assert isinstance(value, PydanticSecret)
            assert value.get_secret_value() == secret_map.get()[key]

    def test_secret_map_with_invalid_input(self):
        with pytest.raises(ValueError, match="`value`|must be a mapping"):
            SecretMap(value="not a mapping")

    def test_secret_map_with_non_hashable_key(self):
        with pytest.raises(TypeError, match="unhashable"):
            SecretMap(value={[1, 2, 3]: "value"})

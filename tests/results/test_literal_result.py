import json

import pytest

from prefect.results import BaseResult, LiteralResult

LITERAL_VALUES = [True, False, None]


@pytest.mark.parametrize("value", LITERAL_VALUES)
async def test_result_literal_create_and_get(value):
    result = await LiteralResult.create(value)
    assert await result.get() == value


@pytest.mark.parametrize("value", LITERAL_VALUES)
def test_result_literal_create_and_get_sync(value):
    result = LiteralResult.create(value)
    assert result.get() == value


@pytest.mark.parametrize("value", LITERAL_VALUES)
async def test_result_literal_json_roundtrip(value):
    result = await LiteralResult.create(value)
    serialized = result.json()
    deserialized = LiteralResult.parse_raw(serialized)
    assert await deserialized.get() == value


@pytest.mark.parametrize("value", LITERAL_VALUES)
async def test_result_literal_json_roundtrip(value):
    result = await LiteralResult.create(value)
    serialized = result.json()
    deserialized = BaseResult.parse_raw(serialized)
    assert await deserialized.get() == value


async def test_result_literal_does_not_allow_unsupported_types():
    with pytest.raises(TypeError, match="Unsupported type 'dict' for result literal"):
        await LiteralResult.create({"foo": "bar"})


async def test_result_literal_null_is_distinguishable_from_none():
    """
    This is important for separating cases where _no result_ is stored in the database
    because the user disabled persistence (for example) from cases where the result
    is stored but is a null value.
    """
    result = await LiteralResult.create(None)
    assert result is not None
    serialized = result.json()
    assert serialized is not None
    assert serialized != "null"
    assert json.loads(serialized) is not None

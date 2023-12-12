import json

import pytest

from prefect.results import BaseResult, PlaceholderResult

INVALID_VALUES = [True, False, "hey"]


@pytest.mark.parametrize("value", INVALID_VALUES)
async def test_placeholder_result_invalid_values(value):
    with pytest.raises(TypeError, match="Unsupported type"):
        await PlaceholderResult.create(value)


def test_placeholder_result_create_and_get_sync():
    result = PlaceholderResult.create()
    assert result.get() is None


async def test_placeholder_result_create_and_get_async():
    result = await PlaceholderResult.create()
    assert await result.get() is None


def test_placeholder_result_create_and_get_with_explicit_value():
    result = PlaceholderResult.create(obj=None)
    assert result.get() is None


async def test_result_placeholder_json_roundtrip():
    result = await PlaceholderResult.create()
    serialized = result.json()
    deserialized = PlaceholderResult.parse_raw(serialized)
    assert await deserialized.get() is None


async def test_placeholder_result_json_roundtrip_base_result_parser():
    result = await PlaceholderResult.create()
    serialized = result.json()
    deserialized = BaseResult.parse_raw(serialized)
    assert await deserialized.get() is None


async def test_placeholder_result_populates_default_artifact_metadata():
    result = await PlaceholderResult.create()
    assert result.artifact_type == "result"
    assert result.artifact_description == "Placeholder result persisted to Prefect."


async def test_placeholder_result_null_is_distinguishable_from_none():
    """
    This is important for separating cases where _no result_ is stored in the database
    because the user disabled persistence (for example) from cases where the result
    is stored but is a null value.
    """
    result = await PlaceholderResult.create(None)
    assert result is not None
    serialized = result.json()
    assert serialized is not None
    assert serialized != "null"
    assert json.loads(serialized) is not None

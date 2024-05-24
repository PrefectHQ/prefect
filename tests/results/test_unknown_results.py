import json

import pytest

from prefect import flow
from prefect.results import BaseResult, UnknownResult

INVALID_VALUES = [True, False, "hey"]


@pytest.mark.parametrize("value", INVALID_VALUES)
async def test_unknown_result_invalid_values(value):
    with pytest.raises(TypeError, match="Unsupported type"):
        await UnknownResult.create(value)


def test_unknown_result_create_and_get_sync():
    @flow
    def sync():
        result = UnknownResult.create()
        return result.get()

    assert sync() is None


async def test_unknown_result_create_and_get_async():
    result = await UnknownResult.create()
    assert await result.get() is None


def test_unknown_result_create_and_get_with_explicit_value():
    @flow
    def sync():
        result = UnknownResult.create(obj=None)
        return result.get()

    assert sync() is None


async def test_result_unknown_json_roundtrip():
    result = await UnknownResult.create()
    serialized = result.model_dump_json()
    deserialized = UnknownResult.model_validate_json(serialized)
    assert await deserialized.get() is None


async def test_unknown_result_json_roundtrip_base_result_parser():
    result = await UnknownResult.create()
    serialized = result.model_dump_json()
    deserialized = BaseResult.model_validate_json(serialized)
    assert await deserialized.get() is None


async def test_unknown_result_populates_default_artifact_metadata():
    result = await UnknownResult.create()
    assert result.artifact_type == "result"
    assert result.artifact_description == "Unknown result persisted to Prefect."


async def test_unknown_result_null_is_distinguishable_from_none():
    """
    This is important for separating cases where _no result_ is stored in the database
    because the user disabled persistence (for example) from cases where the result
    is stored but is a null value.
    """
    result = await UnknownResult.create(None)
    assert result is not None
    serialized = result.model_dump_json()
    assert serialized is not None
    assert serialized != "null"
    assert json.loads(serialized) is not None

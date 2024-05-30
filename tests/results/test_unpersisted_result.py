from dataclasses import dataclass

import pytest

from prefect import flow
from prefect.results import MissingResult, UnpersistedResult


@dataclass
class MyDataClass:
    x: int


TEST_VALUES = [None, "test", MyDataClass(x=1)]


@pytest.mark.parametrize("value", TEST_VALUES)
async def test_unpersisted_result_create_and_get(value):
    result = await UnpersistedResult.create(value)
    assert await result.get() == value


@pytest.mark.parametrize("value", TEST_VALUES)
def test_unpersisted_result_create_and_get_sync(value):
    @flow
    def sync():
        result = UnpersistedResult.create(value)
        return result.get()

    output = sync()
    assert output == value


@pytest.mark.parametrize("value", TEST_VALUES)
async def test_unpersisted_result_create_and_get_no_cache(value):
    result = await UnpersistedResult.create(value, cache_object=False)
    with pytest.raises(MissingResult):
        await result.get()


@pytest.mark.parametrize("value", TEST_VALUES)
async def test_unpersisted_result_missing_after_json_roundtrip(value):
    result = await UnpersistedResult.create(value)
    serialized = result.model_dump_json()
    deserialized = UnpersistedResult.model_validate_json(serialized)
    with pytest.raises(MissingResult):
        await deserialized.get()


@pytest.mark.parametrize("value", TEST_VALUES)
async def test_unpersisted_result_populates_default_artifact_metadata(value):
    result = await UnpersistedResult.create(value)
    assert result.artifact_type == "result"
    assert (
        result.artifact_description
        == f"Unpersisted result of type `{type(value).__name__}`"
    )

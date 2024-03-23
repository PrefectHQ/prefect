import pytest

from prefect._internal.pydantic import BaseModel
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS,
    temporary_settings,
)


@pytest.fixture(autouse=True)
def enable_v2():
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: True}):
        yield


class TestCompatBaseModel:
    class TestCompatModelDump:
        def test_model_dump(self):
            class Foo(BaseModel):
                x: int
                y: str

            assert Foo(x=1, y="2").model_dump() == {"x": 1, "y": "2"}

        def test_model_dump_with_flag_disabled(self):
            with temporary_settings(
                {PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: False}
            ):

                class Foo(BaseModel):
                    x: int
                    y: str

                Foo(x=1, y="2").model_dump() == {"x": 1, "y": "2"}

    class TestCompatModelJsonSchema:
        def test_model_json_schema(self):
            class Foo(BaseModel):
                x: int
                y: str

            assert Foo.model_json_schema() == {
                "title": "Foo",
                "type": "object",
                "properties": {
                    "x": {"title": "X", "type": "integer"},
                    "y": {"title": "Y", "type": "string"},
                },
                "required": ["x", "y"],
            }

        def test_model_json_schema_with_flag_disabled(self):
            with temporary_settings(
                {PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: False}
            ):

                class Foo(BaseModel):
                    x: int
                    y: str

                assert Foo.model_json_schema() == {
                    "title": "Foo",
                    "type": "object",
                    "properties": {
                        "x": {"title": "X", "type": "integer"},
                        "y": {"title": "Y", "type": "string"},
                    },
                    "required": ["x", "y"],
                }

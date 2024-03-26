from pydantic import BaseModel

from prefect._internal.pydantic import model_json_schema


def test_model_json_schema():
    class TestModel(BaseModel):
        a: int
        b: str

    schema = model_json_schema(TestModel)

    assert "properties" in schema
    assert "type" in schema and schema["type"] == "object"

    assert "a" in schema["properties"]
    assert "b" in schema["properties"]


def test_model_json_schema_with_flag_disabled():
    class TestModel(BaseModel):
        a: int
        b: str

    schema = model_json_schema(TestModel)

    assert "properties" in schema
    assert "type" in schema and schema["type"] == "object"

    assert "a" in schema["properties"]
    assert "b" in schema["properties"]

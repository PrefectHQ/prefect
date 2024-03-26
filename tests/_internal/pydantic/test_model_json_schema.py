import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import model_json_schema
from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="Valid when pydantic compatibility layer is enabled or when v1 is installed",
)
def test_model_json_schema():
    class TestModel(BaseModel):
        a: int
        b: str

    schema = model_json_schema(TestModel)

    assert "properties" in schema
    assert "type" in schema and schema["type"] == "object"

    assert "a" in schema["properties"]
    assert "b" in schema["properties"]


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="Only valid when compatibility layer is disabled and v2 is installed",
)
def test_model_json_schema_with_flag_disabled():
    from pydantic import PydanticDeprecatedSince20

    class TestModel(BaseModel):
        a: int
        b: str

    with pytest.warns(PydanticDeprecatedSince20):
        schema = model_json_schema(TestModel)

    assert "properties" in schema
    assert "type" in schema and schema["type"] == "object"

    assert "a" in schema["properties"]
    assert "b" in schema["properties"]

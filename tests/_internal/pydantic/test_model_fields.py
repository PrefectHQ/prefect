import pytest

from prefect._internal.pydantic._flags import USE_V2_MODELS


@pytest.mark.skipif(
    USE_V2_MODELS,
    reason="We only need to backport functionality when using Pydantic v1",
)
def test_model_fields():
    """
    with either:
        - v2 installed and compatibility layer disabled
        - or v1 installed

    everything should work without deprecation warnings
    """
    from prefect.pydantic import BaseModel, Field

    class TestModel(BaseModel):
        a: int = Field(banana=True)  # type: ignore
        b: str

    model = TestModel(a=1, b="2")

    if a := model.model_fields.get("a"):
        assert a.annotation == int
        assert a.json_schema_extra == {"banana": True}
    if b := model.model_fields.get("b"):
        assert b.annotation == str
        assert b.json_schema_extra == {}

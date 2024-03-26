import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import model_dump
from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="Valid when pydantic compatibility layer is enabled or when v1 is installed",
)
def test_model_dump():
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    assert model_dump(model) == {"a": 1, "b": "2"}


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="Only valid when compatibility layer is disabled and v2 is installed",
)
def test_model_dump_with_flag_disabled():
    from pydantic import PydanticDeprecatedSince20

    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    with pytest.warns(PydanticDeprecatedSince20):
        assert model_dump(model) == {"a": 1, "b": "2"}


def test_model_dump_with_non_basemodel_raises():
    with pytest.raises(TypeError, match="Expected a Pydantic model"):
        model_dump("not a model")  # type: ignore

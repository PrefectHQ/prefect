import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import model_copy
from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="Valid when pydantic compatibility layer is enabled or when v1 is installed",
)
def test_model_copy():
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")
    updated_model = model_copy(model, update={"a": 3}, deep=True)

    assert isinstance(updated_model, TestModel)
    assert updated_model.a == 3
    assert updated_model.b == "2"
    assert model.a == 1  # Original model should remain unchanged


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="Only valid when compatibility layer is disabled and v2 is installed",
)
def test_model_copy_with_flag_disabled():
    from pydantic import PydanticDeprecatedSince20

    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    with pytest.warns(PydanticDeprecatedSince20):
        updated_model = model_copy(model, update={"a": 3}, deep=True)

    assert isinstance(updated_model, TestModel)
    assert updated_model.a == 3
    assert updated_model.b == "2"
    assert model.a == 1  # Original model should remain unchanged


def test_model_copy_with_non_basemodel_raises():
    with pytest.raises(TypeError, match="Expected a Pydantic model"):
        model_copy("not a model")  # type: ignore

import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import model_validate_json
from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS


class Model(BaseModel):
    a: int
    b: str


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="Valid when pydantic compatibility layer is enabled or when v1 is installed",
)
def test_model_validate_json():
    model_instance = model_validate_json(Model, '{"a": 1, "b": "test"}')

    assert isinstance(model_instance, Model)

    assert model_instance.a == 1

    assert model_instance.b == "test"


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="Only valid when compatibility layer is disabled and v2 is installed",
)
def test_model_validate_json_with_flag_disabled():
    from pydantic import PydanticDeprecatedSince20

    with pytest.warns(PydanticDeprecatedSince20):
        model_instance = model_validate_json(Model, '{"a": 1, "b": "test"}')

    assert isinstance(model_instance, Model)

    assert model_instance.a == 1

    assert model_instance.b == "test"

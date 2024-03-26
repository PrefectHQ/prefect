import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import model_validate_json
from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS


class Model(BaseModel):
    a: int
    b: str


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when pydantic compatibility layer is enabled or when v1 is installed",
)
def test_model_validate_json():
    """
    with either:
        - v2 installed and compatibility layer enabled
        - or v1 installed

    everything should work without deprecation warnings
    """
    model_instance = model_validate_json(Model, '{"a": 1, "b": "test"}')

    assert isinstance(model_instance, Model)

    assert model_instance.a == 1

    assert model_instance.b == "test"


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when compatibility layer is disabled and v2 is installed",
)
def test_model_validate_json_with_flag_disabled():
    """with v2 installed and compatibility layer disabled, we should see deprecation warnings"""
    from pydantic import PydanticDeprecatedSince20

    with pytest.warns(PydanticDeprecatedSince20):
        model_instance = model_validate_json(Model, '{"a": 1, "b": "test"}')

    assert isinstance(model_instance, Model)

    assert model_instance.a == 1

    assert model_instance.b == "test"

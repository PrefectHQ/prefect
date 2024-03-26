from typing import cast

from pydantic import BaseModel, ValidationError

from prefect._internal.pydantic._compat import model_validate


class Model(BaseModel):
    a: int
    b: str


def test_model_validate():
    model_instance = model_validate(Model, {"a": 1, "b": "test"})

    assert isinstance(model_instance, Model)

    assert cast(Model, model_instance).a == 1

    assert cast(Model, model_instance).b == "test"


def test_model_validate_with_flag_disabled():
    model_instance = model_validate(Model, {"a": 1, "b": "test"})

    assert cast(Model, model_instance).a == 1

    assert cast(Model, model_instance).b == "test"


def test_model_validate_with_invalid_model():
    try:
        model_validate(Model, {"a": "not an int", "b": "test"})
    except ValidationError as e:
        errors = e.errors()

        assert len(errors) == 1

        error = errors[0]

        assert error["loc"] == ("a",)
        assert "valid integer" in error["msg"]

from pydantic import BaseModel

from prefect._internal.pydantic import model_validate_json


class Model(BaseModel):
    a: int
    b: str


def test_model_validate_json():
    model_instance = model_validate_json(Model, '{"a": 1, "b": "test"}')

    assert isinstance(model_instance, Model)

    assert model_instance.a == 1

    assert model_instance.b == "test"


def test_model_validate_json_with_flag_disabled():
    model_instance = model_validate_json(Model, '{"a": 1, "b": "test"}')

    assert isinstance(model_instance, Model)

    assert model_instance.a == 1

    assert model_instance.b == "test"

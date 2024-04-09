import pytest

from prefect.pydantic import BaseModel, ConfigDict, Field, ValidationError


def test_allow_population_by_field_name():
    class User(BaseModel):
        name: str = Field(alias="full_name")
        age: int
        model_config = ConfigDict(populate_by_name=True)

    assert User(full_name="John", age=42).name == "John"


def test_anystr_lower():
    class User(BaseModel):
        name: str
        model_config = ConfigDict(str_to_lower=True)

    assert User(name="John").name == "john"


def test_anystr_strip_whitespace():
    class User(BaseModel):
        name: str
        model_config = ConfigDict(str_strip_whitespace=True)

    assert User(name="  John  ").name == "John"


def test_anystr_upper():
    class User(BaseModel):
        name: str
        model_config = ConfigDict(str_to_upper=True)

    assert User(name="john").name == "JOHN"


def test_max_anystr_length():
    class User(BaseModel):
        name: str
        model_config = ConfigDict(str_max_length=3)

    with pytest.raises(ValidationError):
        User(name="John")


def test_min_anystr_length():
    class User(BaseModel):
        name: str
        model_config = ConfigDict(str_min_length=3)

    with pytest.raises(ValidationError):
        User(name="J")

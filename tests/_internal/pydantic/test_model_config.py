import typing

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


def test_copy_on_model_validation_none():
    class Child(BaseModel):
        model_config = ConfigDict(revalidate_instances="never")

    class Parent(BaseModel):
        child: Child

    child = Child()
    parent = Parent(child=child)
    assert parent.child is child


def test_copy_on_model_validation_always():
    class Child(BaseModel):
        model_config = ConfigDict(revalidate_instances="always")

    class Parent(BaseModel):
        child: Child

    child = Child()
    parent = Parent(child=child)
    with pytest.raises(AssertionError):
        assert parent.child is child


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


def test_orm_mode():
    class User(BaseModel):
        name: str
        age: int
        model_config = ConfigDict(from_attributes=True)

    assert User.model_validate(User(name="John", age=42)).name == "John"
    assert User.model_validate(User(name="John", age=42)).age == 42


def test_schema_extra():
    def pop_age(s: typing.Dict[str, typing.Any]) -> None:
        s["properties"].pop("age")

    class User(BaseModel):
        name: str
        age: int
        model_config = ConfigDict(json_schema_extra=pop_age)

    assert "age" not in User.model_json_schema()["properties"]


def test_validate_all():
    class User(BaseModel):
        name: str
        age: int = Field(default="banana")
        model_config = ConfigDict(validate_default=True)

    with pytest.raises(ValidationError):
        User(name="John")

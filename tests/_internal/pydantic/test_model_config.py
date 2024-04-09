from prefect.pydantic import BaseModel, ConfigDict, Field


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

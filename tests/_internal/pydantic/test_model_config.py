from prefect.pydantic import BaseModel, ConfigDict, Field


def test_allow_population_by_field_name():
    class User(BaseModel):
        name: str = Field(alias="full_name")
        age: int
        model_config = ConfigDict(populate_by_name=True)

    assert User(full_name="John", age=42).name == "John"

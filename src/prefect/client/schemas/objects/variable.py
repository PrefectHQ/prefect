from typing import (
    List,
)

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect.types import (
    MAX_VARIABLE_NAME_LENGTH,
    StrictVariableValue,
)


class Variable(ObjectBaseModel):
    name: str = Field(
        default=...,
        description="The name of the variable",
        examples=["my_variable"],
        max_length=MAX_VARIABLE_NAME_LENGTH,
    )
    value: StrictVariableValue = Field(
        default=...,
        description="The value of the variable",
        examples=["my_value"],
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of variable tags",
        examples=[["tag-1", "tag-2"]],
    )

from typing import List, Optional

from pydantic import Field, field_validator

from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.validators import (
    validate_variable_name,
)
from prefect.types import (
    MAX_VARIABLE_NAME_LENGTH,
    StrictVariableValue,
)


class VariableUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a Variable."""

    name: Optional[str] = Field(
        default=None,
        description="The name of the variable",
        examples=["my_variable"],
        max_length=MAX_VARIABLE_NAME_LENGTH,
    )
    value: StrictVariableValue = Field(
        default=None,
        description="The value of the variable",
        examples=["my-value"],
    )
    tags: Optional[List[str]] = Field(default=None)

    # validators
    _validate_name_format = field_validator("name")(validate_variable_name)
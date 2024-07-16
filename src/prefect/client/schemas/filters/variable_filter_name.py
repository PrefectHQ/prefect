from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class VariableFilterName(PrefectBaseModel):
    """Filter by `Variable.name`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of variables names to include"
    )
    like_: Optional[str] = Field(
        default=None,
        description=(
            "A string to match variable names against. This can include "
            "SQL wildcard characters like `%` and `_`."
        ),
        examples=["my_variable_%"],
    )
from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowFilterName(PrefectBaseModel):
    """Filter by `Flow.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of flow names to include",
        examples=[["my-flow-1", "my-flow-2"]],
    )

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        examples=["marvin"],
    )
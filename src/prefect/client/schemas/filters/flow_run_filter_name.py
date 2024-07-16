from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowRunFilterName(PrefectBaseModel):
    """Filter by `FlowRun.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of flow run names to include",
        examples=[["my-flow-run-1", "my-flow-run-2"]],
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
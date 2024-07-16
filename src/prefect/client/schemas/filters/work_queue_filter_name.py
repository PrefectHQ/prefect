from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class WorkQueueFilterName(PrefectBaseModel):
    """Filter by `WorkQueue.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of work queue names to include",
        examples=[["wq-1", "wq-2"]],
    )

    startswith_: Optional[List[str]] = Field(
        default=None,
        description=(
            "A list of case-insensitive starts-with matches. For example, "
            " passing 'marvin' will match "
            "'marvin', and 'Marvin-robot', but not 'sad-marvin'."
        ),
        examples=[["marvin", "Marvin-robot"]],
    )
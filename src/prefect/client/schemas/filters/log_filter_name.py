from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class LogFilterName(PrefectBaseModel):
    """Filter by `Log.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of log names to include",
        examples=[["prefect.logger.flow_runs", "prefect.logger.task_runs"]],
    )

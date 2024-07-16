from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class TaskRunFilterSubFlowRuns(PrefectBaseModel):
    """Filter by `TaskRun.subflow_run`."""

    exists_: Optional[bool] = Field(
        default=None,
        description=(
            "If true, only include task runs that are subflow run parents; if false,"
            " exclude parent task runs"
        ),
    )

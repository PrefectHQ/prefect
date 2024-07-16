from typing import Optional

from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel


class LogFilterTimestamp(PrefectBaseModel):
    """Filter by `Log.timestamp`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include logs with a timestamp at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include logs with a timestamp at or after this time",
    )

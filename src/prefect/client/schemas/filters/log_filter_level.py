from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class LogFilterLevel(PrefectBaseModel):
    """Filter by `Log.level`."""

    ge_: Optional[int] = Field(
        default=None,
        description="Include logs with a level greater than or equal to this level",
        examples=[20],
    )

    le_: Optional[int] = Field(
        default=None,
        description="Include logs with a level less than or equal to this level",
        examples=[50],
    )

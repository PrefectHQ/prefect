from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class WorkPoolFilterType(PrefectBaseModel):
    """Filter by `WorkPool.type`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of work pool types to include"
    )
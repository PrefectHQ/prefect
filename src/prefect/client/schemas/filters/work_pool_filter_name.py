from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class WorkPoolFilterName(PrefectBaseModel):
    """Filter by `WorkPool.name`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of work pool names to include"
    )
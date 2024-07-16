from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowRunFilterIdempotencyKey(PrefectBaseModel):
    """Filter by FlowRun.idempotency_key."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run idempotency keys to include"
    )
    not_any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run idempotency keys to exclude"
    )
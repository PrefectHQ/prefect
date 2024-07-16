from typing import Any, Dict, Optional

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.types import (
    NonEmptyishName,
    NonNegativeInteger,
)


class WorkPoolCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work pool."""

    name: NonEmptyishName = Field(
        description="The name of the work pool.",
    )
    description: Optional[str] = Field(None)
    type: str = Field(
        description="The work pool type.", default="prefect-agent"
    )  # TODO: change default
    base_job_template: Dict[str, Any] = Field(
        default_factory=dict,
        description="The base job template for the work pool.",
    )
    is_paused: bool = Field(
        default=False,
        description="Whether the work pool is paused.",
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(
        default=None, description="A concurrency limit for the work pool."
    )

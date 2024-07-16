from typing import (
    Any,
    Dict,
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
    field_validator,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect._internal.schemas.validators import (
    validate_default_queue_id_not_none,
)
from prefect.types import (
    Name,
    NonNegativeInteger,
)

from .work_pool_status import WorkPoolStatus


class WorkPool(ObjectBaseModel):
    """An ORM representation of a work pool"""

    name: Name = Field(
        description="The name of the work pool.",
    )
    description: Optional[str] = Field(
        default=None, description="A description of the work pool."
    )
    type: str = Field(description="The work pool type.")
    base_job_template: Dict[str, Any] = Field(
        default_factory=dict, description="The work pool's base job template."
    )
    is_paused: bool = Field(
        default=False,
        description="Pausing the work pool stops the delivery of all work.",
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(
        default=None, description="A concurrency limit for the work pool."
    )
    status: Optional[WorkPoolStatus] = Field(
        default=None, description="The current status of the work pool."
    )

    # this required field has a default of None so that the custom validator
    # below will be called and produce a more helpful error message
    default_queue_id: UUID = Field(
        None, description="The id of the pool's default queue."
    )

    @property
    def is_push_pool(self) -> bool:
        return self.type.endswith(":push")

    @property
    def is_managed_pool(self) -> bool:
        return self.type.endswith(":managed")

    @field_validator("default_queue_id")
    @classmethod
    def helpful_error_for_missing_default_queue_id(cls, v):
        return validate_default_queue_id_not_none(v)
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.client.schemas.objects import (
    StateDetails,
    StateType,
)

if TYPE_CHECKING:
    from prefect.results import BaseResult

R = TypeVar("R")


class StateCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a new state."""

    type: StateType
    name: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None, examples=["Run started"])
    state_details: StateDetails = Field(default_factory=StateDetails)
    data: Union["BaseResult[R]", Any] = Field(
        default=None,
    )

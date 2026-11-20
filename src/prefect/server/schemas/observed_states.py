"""Discovery of state types and exact names in retained run history."""

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.types._datetime import DateTime
from prefect.utilities.collections import AutoEnum


class ObservedStateSort(AutoEnum):
    """Supported ordering for observed state discovery."""

    NAME_ASC = AutoEnum.auto()
    LAST_SEEN_DESC = AutoEnum.auto()


class ObservedState(PrefectBaseModel):
    """An exact state type/name pair and the bounds of its retained transitions."""

    state_type: str = Field(description="The state type.")
    state_name: str = Field(description="The exact state name.")
    first_seen: DateTime = Field(description="Earliest retained transition timestamp.")
    last_seen: DateTime = Field(description="Latest retained transition timestamp.")

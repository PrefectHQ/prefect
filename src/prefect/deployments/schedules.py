from typing import TYPE_CHECKING, Any, List, Optional, Sequence, Union

from prefect.client.schemas.actions import (
    DeploymentScheduleCreate,
    DeploymentScheduleUpdate,
)
from prefect.client.schemas.schedules import is_schedule_type
from prefect.schedules import Schedule

if TYPE_CHECKING:
    from prefect.client.schemas.schedules import SCHEDULE_TYPES

FlexibleScheduleList = Sequence[
    Union[DeploymentScheduleCreate, dict[str, Any], "SCHEDULE_TYPES"]
]


def create_deployment_schedule_create(
    schedule: Union["SCHEDULE_TYPES", "Schedule"],
    active: Optional[bool] = None,
) -> DeploymentScheduleCreate:
    """Create a DeploymentScheduleCreate object from common schedule parameters."""

    if isinstance(schedule, Schedule):
        return DeploymentScheduleCreate.from_schedule(schedule)
    # Leave `active` unset when not provided so an update payload built with
    # `exclude_unset=True` doesn't force a paused schedule back to active.
    if active is None:
        return DeploymentScheduleCreate(schedule=schedule)
    return DeploymentScheduleCreate(schedule=schedule, active=active)


def normalize_to_deployment_schedule(
    schedules: Optional["FlexibleScheduleList"],
) -> List[Union[DeploymentScheduleCreate, DeploymentScheduleUpdate]]:
    normalized: list[Union[DeploymentScheduleCreate, DeploymentScheduleUpdate]] = []
    if schedules is not None:
        for obj in schedules:
            if is_schedule_type(obj):
                normalized.append(create_deployment_schedule_create(obj))
            elif isinstance(obj, Schedule):
                normalized.append(create_deployment_schedule_create(obj))
            elif isinstance(obj, dict):
                normalized.append(create_deployment_schedule_create(**obj))
            elif isinstance(obj, DeploymentScheduleCreate):
                normalized.append(obj)
            elif isinstance(obj, DeploymentScheduleUpdate):
                normalized.append(obj)
            elif _is_server_schema(obj):
                raise ValueError(
                    "Server schema schedules are not supported. Please use "
                    "the schedule objects from `prefect.client.schemas.schedules`"
                )
            else:
                raise ValueError(
                    "Invalid schedule provided. Must be a schedule object, a dict,"
                    "or a `DeploymentScheduleCreate` object"
                )

    return normalized


def _is_server_schema(obj: Any):
    return obj.__class__.__module__.startswith("prefect.server.schemas")

from typing import TYPE_CHECKING, Any, List, Optional, Sequence, Union, get_args

from prefect.client.schemas.actions import DeploymentScheduleCreate

if TYPE_CHECKING:
    from prefect.client.schemas.schedules import SCHEDULE_TYPES

FlexibleScheduleList = Sequence[Union[DeploymentScheduleCreate, dict, "SCHEDULE_TYPES"]]


def create_deployment_schedule_create(
    schedule: "SCHEDULE_TYPES",
    active: Optional[bool] = True,
    max_active_runs: Optional[int] = None,
    catchup: bool = False,
) -> DeploymentScheduleCreate:
    """Create a DeploymentScheduleCreate object from common schedule parameters."""
    return DeploymentScheduleCreate(
        schedule=schedule,
        active=active if active is not None else True,
        max_active_runs=max_active_runs,
        catchup=catchup,
    )


def normalize_to_deployment_schedule_create(
    schedules: Optional["FlexibleScheduleList"],
) -> List[DeploymentScheduleCreate]:
    from prefect.client.schemas.schedules import SCHEDULE_TYPES

    normalized = []
    if schedules is not None:
        for obj in schedules:
            if isinstance(obj, get_args(SCHEDULE_TYPES)):
                normalized.append(create_deployment_schedule_create(obj))
            elif isinstance(obj, dict):
                normalized.append(create_deployment_schedule_create(**obj))
            elif isinstance(obj, DeploymentScheduleCreate):
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

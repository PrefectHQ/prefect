from typing import List, Optional, Sequence, Union, get_args

from prefect.client.schemas.objects import MinimalDeploymentSchedule
from prefect.client.schemas.schedules import SCHEDULE_TYPES

try:
    from prefect.server.schemas.schedules import SCHEDULE_TYPES as SERVER_SCHEDULE_TYPES

    SERVER_SCHEDULE_TYPES = get_args(SERVER_SCHEDULE_TYPES)
except ImportError:
    # `prefect-client` does not have access to the server schemas.
    SERVER_SCHEDULE_TYPES = ()

FlexibleScheduleList = Sequence[Union[MinimalDeploymentSchedule, dict, SCHEDULE_TYPES]]


def create_minimal_deployment_schedule(
    schedule: SCHEDULE_TYPES,
    active: Optional[bool] = True,
) -> MinimalDeploymentSchedule:
    return MinimalDeploymentSchedule(
        schedule=schedule,
        active=active if active is not None else True,
    )


def normalize_to_minimal_deployment_schedules(
    schedules: Optional[FlexibleScheduleList],
) -> List[MinimalDeploymentSchedule]:
    normalized = []
    if schedules is not None:
        for obj in schedules:
            if isinstance(obj, get_args(SCHEDULE_TYPES)):
                normalized.append(create_minimal_deployment_schedule(obj))
            elif isinstance(obj, dict):
                normalized.append(create_minimal_deployment_schedule(**obj))
            elif isinstance(obj, MinimalDeploymentSchedule):
                normalized.append(obj)
            elif isinstance(obj, SERVER_SCHEDULE_TYPES):
                raise ValueError(
                    "Server schema schedules are not supported. Please use "
                    "the schedule objects from `prefect.client.schemas.schedules`"
                )
            else:
                raise ValueError(
                    "Invalid schedule provided. Must be a schedule object, a dict,"
                    " or a MinimalDeploymentSchedule."
                )

    return normalized

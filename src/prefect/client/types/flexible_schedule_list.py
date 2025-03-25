from typing import TYPE_CHECKING, Any, Sequence, Union

from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from prefect.client.schemas.actions import DeploymentScheduleCreate
    from prefect.client.schemas.schedules import SCHEDULE_TYPES
    from prefect.schedules import Schedule

FlexibleScheduleList: TypeAlias = Sequence[
    Union["DeploymentScheduleCreate", dict[str, Any], "SCHEDULE_TYPES", "Schedule"]
]

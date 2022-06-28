from typing import Any, Dict, List

from pydantic import BaseModel, Field

from prefect.flows import Flow
from prefect.orion.schemas.schedules import SCHEDULE_TYPES


class Deployment(BaseModel):
    name: str = None
    flow: Flow = None
    flow_name: str = None
    flow_location: str = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    schedule: SCHEDULE_TYPES = None
    tags: List[str] = Field(default_factory=list)
    flow_runner: Union[FlowRunner, FlowRunnerSettings] = None
    flow_storage: Optional[Union[StorageBlock, UUID]] = None

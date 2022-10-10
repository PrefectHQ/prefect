from typing import Optional, TypeVar

from pydantic import Field

from prefect.orion import schemas
from prefect.states import State

R = TypeVar("R")


class FlowRun(schemas.core.FlowRun.subclass()):
    state: Optional[State] = Field(default=None)


class TaskRun(schemas.core.TaskRun.subclass()):
    state: Optional[State] = Field(default=None)


class OrchestrationResult(schemas.responses.OrchestrationResult.subclass()):
    state: Optional[State]

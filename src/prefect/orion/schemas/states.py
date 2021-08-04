from prefect.orion.schemas.core import APIBaseModel
import datetime
from enum import auto
from typing import Any
from uuid import UUID

import pendulum
from pydantic import Field, validator

from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.utilities.schemas import PrefectBaseModel


class StateType(AutoEnum):
    SCHEDULED = auto()
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class StateDetails(PrefectBaseModel):
    flow_run_id: UUID = None
    task_run_id: UUID = None
    scheduled_time: datetime.datetime = None


class RunDetails(PrefectBaseModel):
    previous_state_id: UUID = None
    run_count: int = 0
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    total_run_time_seconds: float = 0.0
    total_time_seconds: float = 0.0
    last_run_time: float = 0.0


class State(APIBaseModel):
    type: StateType
    name: str = None
    timestamp: datetime.datetime = Field(default_factory=pendulum.now, repr=False)
    message: str = Field(None, example="Run started")
    data: Any = Field(None, repr=False)
    state_details: StateDetails = Field(default_factory=StateDetails, repr=False)
    run_details: RunDetails = Field(default_factory=RunDetails, repr=False)

    @validator("name", pre=True, always=True)
    def default_name_from_type(cls, v, *, values, **kwargs):
        """If a name is not provided, use the type"""
        if v is None:
            v = values.get("type").value.capitalize()
        return v

    def is_scheduled(self):
        return self.type == StateType.SCHEDULED

    def is_pending(self):
        return self.type == StateType.PENDING

    def is_running(self):
        return self.type == StateType.RUNNING

    def is_completed(self):
        return self.type == StateType.COMPLETED

    def is_failed(self):
        return self.type == StateType.FAILED

    def is_cancelled(self):
        return self.type == StateType.CANCELLED


def Completed(**kwargs) -> State:
    """Convenience function for creating `Completed` states.

    Returns:
        State: a Completed state
    """
    return State(type=StateType.COMPLETED, **kwargs)


def AwaitingRetry(scheduled_time: datetime, **kwargs) -> State:
    """Convenience function for creating `AwaitingRetry` states.

    Returns:
        State: a AwaitingRetry state
    """
    return State(
        type=StateType.SCHEDULED,
        name="AwaitingRetry",
        state_details=StateDetails(scheduled_time=scheduled_time),
        **kwargs
    )


def Retrying(**kwargs) -> State:
    """Convenience function for creating `Retrying` states.

    Returns:
        State: a Retrying state
    """
    return State(type=StateType.RUNNING, name="Retrying", **kwargs)

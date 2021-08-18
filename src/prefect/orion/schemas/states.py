from prefect.orion.schemas.core import ORMBaseModel
import datetime
from enum import auto
from typing import Any, Optional
from uuid import UUID

import pendulum
from pydantic import Field, validator

from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.utilities.schemas import PrefectBaseModel, IDBaseModel


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
    cache_key: str = None
    cache_expiration: datetime.datetime = None


class RunDetails(PrefectBaseModel):
    previous_state_id: UUID = None
    run_count: int = 0
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    total_run_time_seconds: float = 0.0
    total_time_seconds: float = 0.0
    last_run_time: datetime.datetime = None


class State(IDBaseModel):
    type: StateType
    name: str = None
    timestamp: datetime.datetime = Field(
        default_factory=lambda: pendulum.now("UTC"), repr=False
    )
    message: str = Field(None, example="Run started")
    data: Any = Field(None, repr=False)
    state_details: StateDetails = Field(default_factory=StateDetails, repr=False)
    run_details: RunDetails = Field(default_factory=RunDetails, repr=False)

    @validator("name", always=True)
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

    def is_final(self):
        return self.is_cancelled() or self.is_completed() or self.is_failed()

    def copy(self, *, update: dict = None, **kwargs):
        """
        Copying API models should return an object that could be inserted into the
        database again. The 'timestamp' is reset using the default factory.
        """
        update = update or {}
        update.setdefault("timestamp", self.__fields__["timestamp"].get_default())
        return super().copy(update=update, **kwargs)


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
        name="Awaiting Retry",
        state_details=StateDetails(scheduled_time=scheduled_time),
        **kwargs
    )


def Retrying(**kwargs) -> State:
    """Convenience function for creating `Retrying` states.

    Returns:
        State: a Retrying state
    """
    return State(type=StateType.RUNNING, name="Retrying", **kwargs)


def update_run_details(from_state: Optional[State], to_state: State) -> RunDetails:
    """Given two states, generates a run details object using information
    from both states. Returns the new run details object.

    Args:
        from_state (Optional[State]): The current state (if any)
        to_state (State): The new state

    Returns:
        RunDetails
    """

    if from_state:
        run_details = from_state.run_details.copy()
        duration = (to_state.timestamp - from_state.timestamp).total_seconds()
        run_details.previous_state_id = from_state.id
        run_details.total_time_seconds += duration
    else:
        run_details = RunDetails()
        duration = 0

    # if exiting a running state...
    if from_state and from_state.is_running():
        run_details.total_run_time_seconds += duration
        if to_state.type in [
            StateType.COMPLETED,
            StateType.FAILED,
            StateType.CANCELLED,
        ]:
            run_details.end_time = to_state.timestamp

    # if entering a running state...
    if to_state.is_running():
        run_details.run_count += 1
        run_details.last_run_time = to_state.timestamp
        if run_details.start_time is None:
            run_details.start_time = to_state.timestamp

    # return the new run details
    return run_details

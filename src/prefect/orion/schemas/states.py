import datetime
from typing import Optional, Generic, TypeVar
from uuid import UUID

import pendulum
from pydantic import Field, validator, root_validator

from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.schemas.data import DataDocument
from prefect.orion.utilities.schemas import IDBaseModel, PrefectBaseModel

R = TypeVar("R")


class StateType(AutoEnum):
    SCHEDULED = AutoEnum.auto()
    PENDING = AutoEnum.auto()
    RUNNING = AutoEnum.auto()
    COMPLETED = AutoEnum.auto()
    FAILED = AutoEnum.auto()
    CANCELLED = AutoEnum.auto()


TERMINAL_STATES = {
    StateType.COMPLETED,
    StateType.CANCELLED,
    StateType.FAILED,
}


class StateDetails(PrefectBaseModel):
    flow_run_id: UUID = None
    task_run_id: UUID = None
    scheduled_time: datetime.datetime = None
    cache_key: str = None
    cache_expiration: datetime.datetime = None


class State(IDBaseModel, Generic[R]):
    class Config:
        orm_mode = True

    type: StateType
    name: str = None
    timestamp: datetime.datetime = Field(
        default_factory=lambda: pendulum.now("UTC"), repr=False
    )
    message: str = Field(None, example="Run started")
    data: DataDocument[R] = Field(None, repr=False)
    state_details: StateDetails = Field(default_factory=StateDetails, repr=False)

    @validator("name", always=True)
    def default_name_from_type(cls, v, *, values, **kwargs):
        """If a name is not provided, use the type"""

        # if `type` is not in `values` it means the `type` didn't pass its own
        # validation check and an error will be raised after this function is called
        if v is None and "type" in values:
            v = " ".join([v.capitalize() for v in values.get("type").value.split("_")])
        return v

    @root_validator
    def default_scheduled_start_time(cls, values):
        """
        TODO: This should throw an error instead of setting a default but is out of
              scope for https://github.com/PrefectHQ/orion/pull/174/ and can be rolled
              into work refactoring state initialization
        """
        if values.get("type") == StateType.SCHEDULED:
            state_details = values.setdefault(
                "state_details", cls.__fields__["state_details"].get_default()
            )
            if not state_details.scheduled_time:
                state_details.scheduled_time = pendulum.now("utc")
        return values

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
        return self.type in TERMINAL_STATES

    def copy(self, *, update: dict = None, reset_fields: bool = False, **kwargs):
        """
        Copying API models should return an object that could be inserted into the
        database again. The 'timestamp' is reset using the default factory.
        """
        update = update or {}
        update.setdefault("timestamp", self.__fields__["timestamp"].get_default())
        return super().copy(reset_fields=reset_fields, update=update, **kwargs)


def Scheduled(scheduled_time: datetime.datetime = None, **kwargs) -> State:
    """Convenience function for creating `Scheduled` states.

    Returns:
        State: a Scheduled state
    """
    state_details = StateDetails.parse_obj(kwargs.pop("state_details", {}))
    if scheduled_time is None:
        scheduled_time = pendulum.now("UTC")
    elif state_details.scheduled_time:
        raise ValueError("An extra scheduled_time was provided in state_details")
    state_details.scheduled_time = scheduled_time

    return State(type=StateType.SCHEDULED, state_details=state_details, **kwargs)


def Completed(**kwargs) -> State:
    """Convenience function for creating `Completed` states.

    Returns:
        State: a Completed state
    """
    return State(type=StateType.COMPLETED, **kwargs)


def Running(**kwargs) -> State:
    """Convenience function for creating `Running` states.

    Returns:
        State: a Running state
    """
    return State(type=StateType.RUNNING, **kwargs)


def Failed(**kwargs) -> State:
    """Convenience function for creating `Failed` states.

    Returns:
        State: a Failed state
    """
    return State(type=StateType.FAILED, **kwargs)


def Pending(**kwargs) -> State:
    """Convenience function for creating `Pending` states.

    Returns:
        State: a Pending state
    """
    return State(type=StateType.PENDING, **kwargs)


def AwaitingRetry(scheduled_time: datetime.datetime = None, **kwargs) -> State:
    """Convenience function for creating `AwaitingRetry` states.

    Returns:
        State: a AwaitingRetry state
    """
    return Scheduled(scheduled_time=scheduled_time, name="Awaiting Retry")


def Retrying(**kwargs) -> State:
    """Convenience function for creating `Retrying` states.

    Returns:
        State: a Retrying state
    """
    return State(type=StateType.RUNNING, name="Retrying", **kwargs)


def Late(scheduled_time: datetime.datetime = None, **kwargs) -> State:
    """Convenience function for creating `Late` states.

    Returns:
        State: a Late state
    """
    return Scheduled(scheduled_time=scheduled_time, name="Late")

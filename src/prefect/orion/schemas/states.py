import datetime
from typing import Any, Optional
from uuid import UUID

import pendulum
from pydantic import Field, validator, root_validator

from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.schemas.data import DataDocument
from prefect.orion.utilities.schemas import ORMBaseModel, PrefectBaseModel


class StateType(AutoEnum):
    SCHEDULED = AutoEnum.auto()
    PENDING = AutoEnum.auto()
    RUNNING = AutoEnum.auto()
    COMPLETED = AutoEnum.auto()
    FAILED = AutoEnum.auto()
    CANCELLED = AutoEnum.auto()


class StateDetails(PrefectBaseModel):
    flow_run_id: UUID = None
    task_run_id: UUID = None
    scheduled_time: datetime.datetime = None
    cache_key: str = None
    cache_expiration: datetime.datetime = None


class State(ORMBaseModel):
    type: StateType
    name: str = None
    timestamp: datetime.datetime = Field(
        default_factory=lambda: pendulum.now("UTC"), repr=False
    )
    message: str = Field(None, example="Run started")
    data: DataDocument = Field(None, repr=False)
    state_details: StateDetails = Field(default_factory=StateDetails, repr=False)

    @validator("name", always=True)
    def default_name_from_type(cls, v, *, values, **kwargs):
        """If a name is not provided, use the type"""

        # if type is not in values it means it didn't pass its own
        # validation check and an error will be raised
        if v is None and "type" in values:
            v = values.get("type").value.capitalize()
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
        return self.is_cancelled() or self.is_completed() or self.is_failed()

    def copy(self, *, update: dict = None, reset_fields: bool = False, **kwargs):
        """
        Copying API models should return an object that could be inserted into the
        database again. The 'timestamp' is reset using the default factory.
        """
        update = update or {}
        update.setdefault("timestamp", self.__fields__["timestamp"].get_default())
        return super().copy(reset_fields=reset_fields, update=update, **kwargs)


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

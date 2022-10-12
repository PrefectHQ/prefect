"""
State schemas.
"""

import datetime
import warnings
from typing import Any, Generic, Optional, Type, TypeVar
from uuid import UUID

import pendulum
from pydantic import Field, root_validator, validator

from prefect.orion.utilities.schemas import DateTimeTZ, IDBaseModel, PrefectBaseModel
from prefect.utilities.collections import AutoEnum

R = TypeVar("R")


class StateType(AutoEnum):
    """Enumeration of state types."""

    SCHEDULED = AutoEnum.auto()
    PENDING = AutoEnum.auto()
    RUNNING = AutoEnum.auto()
    COMPLETED = AutoEnum.auto()
    FAILED = AutoEnum.auto()
    CANCELLED = AutoEnum.auto()
    CRASHED = AutoEnum.auto()


TERMINAL_STATES = {
    StateType.COMPLETED,
    StateType.CANCELLED,
    StateType.FAILED,
    StateType.CRASHED,
}


class StateDetails(PrefectBaseModel):
    flow_run_id: UUID = None
    task_run_id: UUID = None
    # for task runs that represent subflows, the subflow's run ID
    child_flow_run_id: UUID = None
    scheduled_time: DateTimeTZ = None
    cache_key: str = None
    cache_expiration: DateTimeTZ = None
    untrackable_result: bool = False


class State(IDBaseModel, Generic[R]):
    """Represents the state of a run."""

    class Config:
        orm_mode = True

    type: StateType
    name: Optional[str] = Field(default=None)
    timestamp: DateTimeTZ = Field(default_factory=lambda: pendulum.now("UTC"))
    message: Optional[str] = Field(default=None, example="Run started")
    data: Optional[Any] = Field(
        default=None,
        description=(
            "Data associated with the state, e.g. a result. "
            "Content must be storable as JSON."
        ),
    )
    state_details: StateDetails = Field(default_factory=StateDetails)

    @validator("name", always=True)
    def default_name_from_type(cls, v, *, values, **kwargs):
        """If a name is not provided, use the type"""

        # if `type` is not in `values` it means the `type` didn't pass its own
        # validation check and an error will be raised after this function is called
        if v is None and values.get("type"):
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

    def is_scheduled(self) -> bool:
        return self.type == StateType.SCHEDULED

    def is_pending(self) -> bool:
        return self.type == StateType.PENDING

    def is_running(self) -> bool:
        return self.type == StateType.RUNNING

    def is_completed(self) -> bool:
        return self.type == StateType.COMPLETED

    def is_failed(self) -> bool:
        return self.type == StateType.FAILED

    def is_crashed(self) -> bool:
        return self.type == StateType.CRASHED

    def is_cancelled(self) -> bool:
        return self.type == StateType.CANCELLED

    def is_final(self) -> bool:
        return self.type in TERMINAL_STATES

    def copy(self, *, update: dict = None, reset_fields: bool = False, **kwargs):
        """
        Copying API models should return an object that could be inserted into the
        database again. The 'timestamp' is reset using the default factory.
        """
        update = update or {}
        update.setdefault("timestamp", self.__fields__["timestamp"].get_default())
        return super().copy(reset_fields=reset_fields, update=update, **kwargs)

    def result(self, raise_on_failure: bool = True, fetch: Optional[bool] = None):
        # Backwards compatible `result` handling on the server-side schema
        from prefect.states import State

        warnings.warn(
            "`result` is no longer supported by `prefect.orion.schemas.states.State` "
            "and will be removed in a future release. When result retrieval is needed, "
            "use `prefect.states.State`.",
            DeprecationWarning,
            stacklevel=2,
        )

        state = State.parse_obj(self)
        return state.result(raise_on_failure=raise_on_failure, fetch=fetch)

    def to_state_create(self):
        # Backwards compatibility for `to_state_create`
        from prefect.orion.schemas import State

        warnings.warn(
            "`to_state_create` is not supported by `prefect.orion.schemas.states.State` "
            "and will be removed in a future release. When working with states, use "
            "`prefect.states.State` instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        state = State.parse_obj(self)
        return state.to_state_create()

    def __repr__(self) -> str:
        """
        Generates a complete state representation appropriate for introspection
        and debugging, including the result:

        `MyCompletedState(message="my message", type=COMPLETED, result=...)`
        """
        from prefect.deprecated.data_documents import DataDocument

        if isinstance(self.data, DataDocument):
            result = self.data.decode()
        else:
            result = self.data

        display = dict(
            message=repr(self.message),
            type=self.type,
            result=repr(result),
        )

        return f"{self.name}({', '.join(f'{k}={v}' for k, v in display.items())})"

    def __str__(self) -> str:
        """
        Generates a simple state representation appropriate for logging:

        `MyCompletedState("my message", type=COMPLETED)`
        """

        display_message = f"{self.message!r}" if self.message else ""

        display_type = (
            f", type={self.type}"
            if self.type.value.lower() != self.name.lower()
            else ""
        )

        return f"{self.name}({display_message}{display_type})"

    def __hash__(self) -> int:
        return hash(
            (
                getattr(self.state_details, "flow_run_id", None),
                getattr(self.state_details, "task_run_id", None),
                self.timestamp,
                self.type,
            )
        )


def Scheduled(
    scheduled_time: datetime.datetime = None, cls: Type[State] = State, **kwargs
) -> State:
    """Convenience function for creating `Scheduled` states.

    Returns:
        State: a Scheduled state
    """
    # NOTE: `scheduled_time` must come first for backwards compatibility

    state_details = StateDetails.parse_obj(kwargs.pop("state_details", {}))
    if scheduled_time is None:
        scheduled_time = pendulum.now("UTC")
    elif state_details.scheduled_time:
        raise ValueError("An extra scheduled_time was provided in state_details")
    state_details.scheduled_time = scheduled_time

    return cls(type=StateType.SCHEDULED, state_details=state_details, **kwargs)


def Completed(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Completed` states.

    Returns:
        State: a Completed state
    """
    return cls(type=StateType.COMPLETED, **kwargs)


def Running(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Running` states.

    Returns:
        State: a Running state
    """
    return cls(type=StateType.RUNNING, **kwargs)


def Failed(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Failed` states.

    Returns:
        State: a Failed state
    """
    return cls(type=StateType.FAILED, **kwargs)


def Crashed(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Crashed` states.

    Returns:
        State: a Crashed state
    """
    return cls(type=StateType.CRASHED, **kwargs)


def Cancelled(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Cancelled` states.

    Returns:
        State: a Cancelled state
    """
    return cls(type=StateType.CANCELLED, **kwargs)


def Pending(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Pending` states.

    Returns:
        State: a Pending state
    """
    return cls(type=StateType.PENDING, **kwargs)


def AwaitingRetry(
    scheduled_time: datetime.datetime = None, cls: Type[State] = State, **kwargs
) -> State:
    """Convenience function for creating `AwaitingRetry` states.

    Returns:
        State: a AwaitingRetry state
    """
    return Scheduled(
        cls=cls, scheduled_time=scheduled_time, name="AwaitingRetry", **kwargs
    )


def Retrying(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Retrying` states.

    Returns:
        State: a Retrying state
    """
    return cls(type=StateType.RUNNING, name="Retrying", **kwargs)


def Late(
    scheduled_time: datetime.datetime = None, cls: Type[State] = State, **kwargs
) -> State:
    """Convenience function for creating `Late` states.

    Returns:
        State: a Late state
    """
    return Scheduled(cls=cls, scheduled_time=scheduled_time, name="Late", **kwargs)

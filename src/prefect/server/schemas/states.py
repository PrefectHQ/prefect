"""
State schemas.
"""

import datetime
import warnings
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, TypeVar, Union
from uuid import UUID, uuid4

import pendulum
from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import Self

from prefect.server.utilities.schemas.bases import (
    IDBaseModel,
    PrefectBaseModel,
)
from prefect.utilities.collections import AutoEnum

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMFlowRunState, ORMTaskRunState
    from prefect.server.schemas.actions import StateCreate

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
    PAUSED = AutoEnum.auto()
    CANCELLING = AutoEnum.auto()


class CountByState(PrefectBaseModel):
    COMPLETED: int = Field(default=0)
    PENDING: int = Field(default=0)
    RUNNING: int = Field(default=0)
    FAILED: int = Field(default=0)
    CANCELLED: int = Field(default=0)
    CRASHED: int = Field(default=0)
    PAUSED: int = Field(default=0)
    CANCELLING: int = Field(default=0)
    SCHEDULED: int = Field(default=0)

    # TODO[pydantic]: We couldn't refactor the `validator`, please replace it by `field_validator` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-validators for more information.
    @field_validator("*")
    @classmethod
    def check_key(cls, value, info):
        if info.name not in StateType.__members__:
            raise ValueError(f"{info.name} is not a valid StateType")
        return value


TERMINAL_STATES = {
    StateType.COMPLETED,
    StateType.CANCELLED,
    StateType.FAILED,
    StateType.CRASHED,
}


class StateDetails(PrefectBaseModel):
    flow_run_id: Optional[UUID] = None
    task_run_id: Optional[UUID] = None
    # for task runs that represent subflows, the subflow's run ID
    child_flow_run_id: Optional[UUID] = None
    scheduled_time: Optional[DateTime] = None
    cache_key: Optional[str] = None
    cache_expiration: Optional[DateTime] = None
    deferred: Optional[bool] = False
    untrackable_result: bool = False
    pause_timeout: Optional[DateTime] = None
    pause_reschedule: bool = False
    pause_key: Optional[str] = None
    run_input_keyset: Optional[Dict[str, str]] = None
    refresh_cache: Optional[bool] = None
    retriable: Optional[bool] = None
    transition_id: Optional[UUID] = None
    task_parameters_id: Optional[UUID] = None


class StateBaseModel(IDBaseModel):
    def orm_dict(self, *args, **kwargs) -> dict:
        """
        This method is used as a convenience method for constructing fixtues by first
        building a `State` schema object and converting it into an ORM-compatible
        format. Because the `data` field is not writable on ORM states, this method
        omits the `data` field entirely for the purposes of constructing an ORM model.
        If state data is required, an artifact must be created separately.
        """

        schema_dict = self.model_dump(*args, **kwargs)
        # remove the data field in order to construct a state ORM model
        schema_dict.pop("data", None)
        return schema_dict


class State(StateBaseModel):
    """Represents the state of a run."""

    model_config = ConfigDict(from_attributes=True)

    type: StateType
    name: Optional[str] = Field(default=None)
    timestamp: DateTime = Field(default_factory=lambda: pendulum.now("UTC"))
    message: Optional[str] = Field(default=None, examples=["Run started"])
    data: Optional[Any] = Field(
        default=None,
        description=(
            "Data associated with the state, e.g. a result. "
            "Content must be storable as JSON."
        ),
    )
    state_details: StateDetails = Field(default_factory=StateDetails)

    @classmethod
    def from_orm_without_result(
        cls,
        orm_state: Union["ORMFlowRunState", "ORMTaskRunState"],
        with_data: Optional[Any] = None,
    ):
        """
        During orchestration, ORM states can be instantiated prior to inserting results
        into the artifact table and the `data` field will not be eagerly loaded. In
        these cases, sqlalchemy will attempt to lazily load the the relationship, which
        will fail when called within a synchronous pydantic method.

        This method will construct a `State` object from an ORM model without a loaded
        artifact and attach data passed using the `with_data` argument to the `data`
        field.
        """

        field_keys = cls.model_json_schema()["properties"].keys()
        state_data = {
            field: getattr(orm_state, field, None)
            for field in field_keys
            if field != "data"
        }
        state_data["data"] = with_data
        return cls(**state_data)

    @model_validator(mode="after")
    def default_name_from_type(self):
        """If a name is not provided, use the type"""
        # if `type` is not in `values` it means the `type` didn't pass its own
        # validation check and an error will be raised after this function is called
        name = self.name
        if name is None and self.type:
            self.name = " ".join([v.capitalize() for v in self.type.value.split("_")])
        return self

    @model_validator(mode="after")
    def default_scheduled_start_time(self):
        from prefect.server.schemas.states import StateType

        if self.type == StateType.SCHEDULED:
            if not self.state_details.scheduled_time:
                self.state_details.scheduled_time = pendulum.now("utc")

        return self

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

    def is_cancelling(self) -> bool:
        return self.type == StateType.CANCELLING

    def is_final(self) -> bool:
        return self.type in TERMINAL_STATES

    def is_paused(self) -> bool:
        return self.type == StateType.PAUSED

    def fresh_copy(self, **kwargs) -> Self:
        """
        Return a fresh copy of the state with a new ID.
        """
        return self.model_copy(
            update={
                "id": uuid4(),
                "created": pendulum.now("utc"),
                "updated": pendulum.now("utc"),
                "timestamp": pendulum.now("utc"),
            },
            deep=True,
            **kwargs,
        )

    def result(self, raise_on_failure: bool = True, fetch: Optional[bool] = None):
        # Backwards compatible `result` handling on the server-side schema
        from prefect.states import State

        warnings.warn(
            (
                "`result` is no longer supported by"
                " `prefect.server.schemas.states.State` and will be removed in a future"
                " release. When result retrieval is needed, use `prefect.states.State`."
            ),
            DeprecationWarning,
            stacklevel=2,
        )

        state = State.model_validate(self)
        return state.result(raise_on_failure=raise_on_failure, fetch=fetch)

    def to_state_create(self) -> "StateCreate":
        from prefect.server.schemas.actions import StateCreate

        return StateCreate(
            type=self.type,
            name=self.name,
            message=self.message,
            data=self.data,
            state_details=self.state_details,
        )

    def __repr__(self) -> str:
        """
        Generates a complete state representation appropriate for introspection
        and debugging, including the result:

        `MyCompletedState(message="my message", type=COMPLETED, result=...)`
        """
        result = self.data

        display = dict(
            message=repr(self.message),
            type=str(self.type.value),
            result=repr(result),
        )

        return f"{self.name}({', '.join(f'{k}={v}' for k, v in display.items())})"

    def __str__(self) -> str:
        """
        Generates a simple state representation appropriate for logging:

        `MyCompletedState("my message", type=COMPLETED)`
        """

        display = []

        if self.message:
            display.append(repr(self.message))

        if self.type.value.lower() != self.name.lower():
            display.append(f"type={self.type.value}")

        return f"{self.name}({', '.join(display)})"

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
    scheduled_time: Optional[datetime.datetime] = None,
    cls: Type[State] = State,
    **kwargs,
) -> State:
    """Convenience function for creating `Scheduled` states.

    Returns:
        State: a Scheduled state
    """
    # NOTE: `scheduled_time` must come first for backwards compatibility

    state_details = StateDetails.model_validate(kwargs.pop("state_details", {}))
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


def Cancelling(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Cancelling` states.

    Returns:
        State: a Cancelling state
    """
    return cls(type=StateType.CANCELLING, **kwargs)


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


def Paused(
    cls: Type[State] = State,
    timeout_seconds: Optional[int] = None,
    pause_expiration_time: Optional[datetime.datetime] = None,
    reschedule: Optional[bool] = False,
    pause_key: Optional[str] = None,
    **kwargs,
) -> State:
    """Convenience function for creating `Paused` states.

    Returns:
        State: a Paused state
    """
    state_details = StateDetails.model_validate(kwargs.pop("state_details", {}))

    if state_details.pause_timeout:
        raise ValueError("An extra pause timeout was provided in state_details")

    if pause_expiration_time is not None and timeout_seconds is not None:
        raise ValueError(
            "Cannot supply both a pause_expiration_time and timeout_seconds"
        )

    if pause_expiration_time is None and timeout_seconds is None:
        pass
    else:
        state_details.pause_timeout = pause_expiration_time or (
            pendulum.now("UTC") + pendulum.Duration(seconds=timeout_seconds)
        )

    state_details.pause_reschedule = reschedule
    state_details.pause_key = pause_key

    return cls(type=StateType.PAUSED, state_details=state_details, **kwargs)


def Suspended(
    cls: Type[State] = State,
    timeout_seconds: Optional[int] = None,
    pause_expiration_time: Optional[datetime.datetime] = None,
    pause_key: Optional[str] = None,
    **kwargs,
):
    """Convenience function for creating `Suspended` states.

    Returns:
        State: a Suspended state
    """
    return Paused(
        cls=cls,
        name="Suspended",
        reschedule=True,
        timeout_seconds=timeout_seconds,
        pause_expiration_time=pause_expiration_time,
        pause_key=pause_key,
        **kwargs,
    )


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

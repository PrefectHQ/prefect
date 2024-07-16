from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    Optional,
    TypeVar,
    Union,
    overload,
)
from uuid import uuid4

import pendulum
from pydantic import (
    Field,
    model_validator,
)
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import Self

from prefect._internal.schemas.bases import ObjectBaseModel

from .state_details import StateDetails
from .state_type import StateType

if TYPE_CHECKING:
    from prefect.results import BaseResult

R = TypeVar("R")


TERMINAL_STATES = {
    StateType.COMPLETED,
    StateType.CANCELLED,
    StateType.FAILED,
    StateType.CRASHED,
}


class State(ObjectBaseModel, Generic[R]):
    """
    The state of a run.
    """

    type: StateType
    name: Optional[str] = Field(default=None)
    timestamp: DateTime = Field(default_factory=lambda: pendulum.now("UTC"))
    message: Optional[str] = Field(default=None, examples=["Run started"])
    state_details: StateDetails = Field(default_factory=StateDetails)
    data: Union["BaseResult[R]", Any] = Field(
        default=None,
    )

    @overload
    def result(self: "State[R]", raise_on_failure: bool = True) -> R: ...

    @overload
    def result(
        self: "State[R]", raise_on_failure: bool = False
    ) -> Union[R, Exception]: ...

    def result(
        self,
        raise_on_failure: bool = True,
        fetch: Optional[bool] = None,
        retry_result_failure: bool = True,
    ) -> Union[R, Exception]:
        """
        Retrieve the result attached to this state.

        Args:
            raise_on_failure: a boolean specifying whether to raise an exception
                if the state is of type `FAILED` and the underlying data is an exception
            fetch: a boolean specifying whether to resolve references to persisted
                results into data. For synchronous users, this defaults to `True`.
                For asynchronous users, this defaults to `False` for backwards
                compatibility.
            retry_result_failure: a boolean specifying whether to retry on failures to
                load the result from result storage

        Raises:
            TypeError: If the state is failed but the result is not an exception.

        Returns:
            The result of the run

        Examples:
            >>> from prefect import flow, task
            >>> @task
            >>> def my_task(x):
            >>>     return x

            Get the result from a task future in a flow

            >>> @flow
            >>> def my_flow():
            >>>     future = my_task("hello")
            >>>     state = future.wait()
            >>>     result = state.result()
            >>>     print(result)
            >>> my_flow()
            hello

            Get the result from a flow state

            >>> @flow
            >>> def my_flow():
            >>>     return "hello"
            >>> my_flow(return_state=True).result()
            hello

            Get the result from a failed state

            >>> @flow
            >>> def my_flow():
            >>>     raise ValueError("oh no!")
            >>> state = my_flow(return_state=True)  # Error is wrapped in FAILED state
            >>> state.result()  # Raises `ValueError`

            Get the result from a failed state without erroring

            >>> @flow
            >>> def my_flow():
            >>>     raise ValueError("oh no!")
            >>> state = my_flow(return_state=True)
            >>> result = state.result(raise_on_failure=False)
            >>> print(result)
            ValueError("oh no!")


            Get the result from a flow state in an async context

            >>> @flow
            >>> async def my_flow():
            >>>     return "hello"
            >>> state = await my_flow(return_state=True)
            >>> await state.result()
            hello
        """
        from prefect.states import get_state_result

        return get_state_result(
            self,
            raise_on_failure=raise_on_failure,
            fetch=fetch,
            retry_result_failure=retry_result_failure,
        )

    def to_state_create(self):
        """
        Convert this state to a `StateCreate` type which can be used to set the state of
        a run in the API.

        This method will drop this state's `data` if it is not a result type. Only
        results should be sent to the API. Other data is only available locally.
        """
        from prefect.client.schemas.actions import StateCreate
        from prefect.results import BaseResult

        return StateCreate(
            type=self.type,
            name=self.name,
            message=self.message,
            data=self.data if isinstance(self.data, BaseResult) else None,
            state_details=self.state_details,
        )

    @model_validator(mode="after")
    def default_name_from_type(self) -> Self:
        """If a name is not provided, use the type"""
        # if `type` is not in `values` it means the `type` didn't pass its own
        # validation check and an error will be raised after this function is called
        name = self.name
        if name is None and self.type:
            self.name = " ".join([v.capitalize() for v in self.type.value.split("_")])
        return self

    @model_validator(mode="after")
    def default_scheduled_start_time(self) -> Self:
        if self.type == StateType.SCHEDULED:
            if not self.state_details.scheduled_time:
                self.state_details.scheduled_time = DateTime.now("utc")
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

    def model_copy(
        self, *, update: Optional[Dict[str, Any]] = None, deep: bool = False
    ):
        """
        Copying API models should return an object that could be inserted into the
        database again. The 'timestamp' is reset using the default factory.
        """
        update = update or {}
        update.setdefault("timestamp", self.model_fields["timestamp"].get_default())
        return super().model_copy(update=update, deep=deep)

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
            **kwargs,
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

import datetime
import warnings
from typing import TYPE_CHECKING, Any, Generic, Optional, Type, TypeVar, Union, overload

from pydantic import Field

from prefect.orion import schemas
from prefect.settings import PREFECT_ASYNC_FETCH_STATE_RESULT
from prefect.utilities.asyncutils import in_async_main_thread

if TYPE_CHECKING:
    from prefect.deprecated.data_documents import DataDocument
    from prefect.results import BaseResult

R = TypeVar("R")


class State(schemas.states.State.subclass(exclude_fields=["data"]), Generic[R]):
    """
    The state of a run.

    This client-side extension adds a `result` interface.
    """

    data: Union["BaseResult[R]", "DataDocument[R]", Any] = Field(
        default=None,
    )

    @overload
    def result(self: "State[R]", raise_on_failure: bool = True) -> R:
        ...

    @overload
    def result(self: "State[R]", raise_on_failure: bool = False) -> Union[R, Exception]:
        ...

    def result(self, raise_on_failure: bool = True, fetch: Optional[bool] = None):
        """
        Retrieve the result

        Args:
            raise_on_failure: a boolean specifying whether to raise an exception
                if the state is of type `FAILED` and the underlying data is an exception
            fetch: a boolean specifying whether to resolve references to persisted
                results into data. For synchronous users, this defaults to `True`.
                For asynchronous users, this defaults to `False` for backwards
                compatibility.

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

        if fetch is None and (
            PREFECT_ASYNC_FETCH_STATE_RESULT or not in_async_main_thread()
        ):
            # Fetch defaults to `True` for sync users or async users who have opted in
            fetch = True

        if not fetch:
            from prefect.deprecated.data_documents import (
                DataDocument,
                result_from_state_with_data_document,
            )

            if fetch is None and in_async_main_thread():
                warnings.warn(
                    "State.result() was called from an async context but not awaited. "
                    "This method will be updated to return a coroutine by default in "
                    "the future. Pass `fetch=True` and `await` the call to get rid of "
                    "this warning.",
                    DeprecationWarning,
                    stacklevel=2,
                )
            # Backwards compatibility
            if isinstance(self.data, DataDocument):
                return result_from_state_with_data_document(
                    self, raise_on_failure=raise_on_failure
                )
            else:
                return self.data
        else:
            from prefect.states import get_state_result

            return get_state_result(self, raise_on_failure=raise_on_failure)

    def to_state_create(self) -> schemas.actions.StateCreate:
        from prefect.results import BaseResult

        return schemas.actions.StateCreate(
            type=self.type,
            name=self.name,
            message=self.message,
            data=self.data if isinstance(self.data, BaseResult) else None,
            state_details=self.state_details,
        )


def Scheduled(
    cls: Type[State] = State, scheduled_time: datetime.datetime = None, **kwargs
) -> State:
    """Convenience function for creating `Scheduled` states.

    Returns:
        State: a Scheduled state
    """
    return schemas.states.Scheduled(cls=cls, scheduled_time=scheduled_time, **kwargs)


def Completed(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Completed` states.

    Returns:
        State: a Completed state
    """
    return schemas.states.Completed(cls=cls, **kwargs)


def Running(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Running` states.

    Returns:
        State: a Running state
    """
    return schemas.states.Running(cls=cls, **kwargs)


def Failed(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Failed` states.

    Returns:
        State: a Failed state
    """
    return schemas.states.Failed(cls=cls, **kwargs)


def Crashed(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Crashed` states.

    Returns:
        State: a Crashed state
    """
    return schemas.states.Crashed(cls=cls, **kwargs)


def Cancelled(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Cancelled` states.

    Returns:
        State: a Cancelled state
    """
    return schemas.states.Cancelled(cls=cls, **kwargs)


def Pending(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Pending` states.

    Returns:
        State: a Pending state
    """
    return schemas.states.Pending(cls=cls, **kwargs)


def AwaitingRetry(
    cls: Type[State] = State, scheduled_time: datetime.datetime = None, **kwargs
) -> State:
    """Convenience function for creating `AwaitingRetry` states.

    Returns:
        State: a AwaitingRetry state
    """
    return schemas.states.AwaitingRetry(
        cls=cls, scheduled_time=scheduled_time, **kwargs
    )


def Retrying(cls: Type[State] = State, **kwargs) -> State:
    """Convenience function for creating `Retrying` states.

    Returns:
        State: a Retrying state
    """
    return schemas.states.Retrying(cls=cls, **kwargs)


def Late(
    cls: Type[State] = State, scheduled_time: datetime.datetime = None, **kwargs
) -> State:
    """Convenience function for creating `Late` states.

    Returns:
        State: a Late state
    """
    return schemas.states.Late(cls=cls, scheduled_time=scheduled_time, **kwargs)


class FlowRun(schemas.core.FlowRun.subclass()):
    state: Optional[State] = Field(default=None)


class TaskRun(schemas.core.TaskRun.subclass()):
    state: Optional[State] = Field(default=None)


class OrchestrationResult(schemas.responses.OrchestrationResult.subclass()):
    state: Optional[State]

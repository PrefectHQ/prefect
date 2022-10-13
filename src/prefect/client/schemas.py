from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar, Union, overload

from pydantic import Field

from prefect.orion import schemas

if TYPE_CHECKING:
    from prefect.deprecated.data_documents import DataDocument
    from prefect.results import BaseResult

R = TypeVar("R")


class State(schemas.states.State.subclass(exclude_fields=["data"]), Generic[R]):
    """
    The state of a run.
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
        Retrieve the result attached to this state.

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
        from prefect.states import get_state_result

        return get_state_result(self, raise_on_failure=raise_on_failure, fetch=fetch)

    def to_state_create(self) -> schemas.actions.StateCreate:
        """
        Convert this state to a `StateCreate` type which can be used to set the state of
        a run in the API.

        This method will drop this state's `data` if it is not a result type. Only
        results should be sent to the API. Other data is only available locally.
        """
        from prefect.results import BaseResult

        return schemas.actions.StateCreate(
            type=self.type,
            name=self.name,
            message=self.message,
            data=self.data if isinstance(self.data, BaseResult) else None,
            state_details=self.state_details,
        )


class FlowRun(schemas.core.FlowRun.subclass()):
    state: Optional[State] = Field(default=None)


class TaskRun(schemas.core.TaskRun.subclass()):
    state: Optional[State] = Field(default=None)


class OrchestrationResult(schemas.responses.OrchestrationResult.subclass()):
    state: Optional[State]

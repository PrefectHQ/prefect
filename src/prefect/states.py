import datetime
import sys
import traceback
import warnings
from collections import Counter
from types import TracebackType
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Type, TypeVar

import anyio
import httpx
from typing_extensions import TypeGuard

from prefect.client.schemas import State
from prefect.deprecated.data_documents import (
    DataDocument,
    result_from_state_with_data_document,
)
from prefect.exceptions import CrashedRun, FailedRun, MissingResult
from prefect.orion import schemas
from prefect.orion.schemas.states import StateType
from prefect.results import BaseResult, R, ResultFactory
from prefect.settings import PREFECT_ASYNC_FETCH_STATE_RESULT
from prefect.utilities.asyncutils import in_async_main_thread, sync_compatible
from prefect.utilities.collections import ensure_iterable

if TYPE_CHECKING:
    from prefect.deprecated.data_documents import DataDocument
    from prefect.results import BaseResult

R = TypeVar("R")


def get_state_result(
    state: State[R], raise_on_failure: bool = True, fetch: Optional[bool] = None
) -> R:
    """
    Get the result from a state.

    See `State.result()`
    """
    if fetch is None and (
        PREFECT_ASYNC_FETCH_STATE_RESULT or not in_async_main_thread()
    ):
        # Fetch defaults to `True` for sync users or async users who have opted in
        fetch = True

    if not fetch:
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
        if isinstance(state.data, DataDocument):
            return result_from_state_with_data_document(
                state, raise_on_failure=raise_on_failure
            )
        else:
            return state.data
    else:
        return _get_state_result(state, raise_on_failure=raise_on_failure)


@sync_compatible
async def _get_state_result(state: State[R], raise_on_failure: bool) -> R:
    """
    Internal implementation for `get_state_result` without async backwards compatibility
    """
    if raise_on_failure and (state.is_crashed() or state.is_failed()):
        raise await get_state_exception(state)

    if isinstance(state.data, DataDocument):
        result = result_from_state_with_data_document(
            state, raise_on_failure=raise_on_failure
        )
    elif isinstance(state.data, BaseResult):
        result = await state.data.get()
    elif state.data is None:
        if state.is_failed() or state.is_crashed():
            return await get_state_exception(state)
        else:
            raise MissingResult(
                "State data is missing. "
                "Typically, this occurs when result persistence is disabled and the "
                "state has been retrieved from the API."
            )

    else:
        # The result is attached directly
        result = state.data

    return result


def format_exception(exc: BaseException, tb: TracebackType = None) -> str:
    exc_type = type(exc)
    formatted = "".join(list(traceback.format_exception(exc_type, exc, tb=tb)))

    # Trim `prefect` module paths from our exception types
    if exc_type.__module__.startswith("prefect."):
        formatted = formatted.replace(
            f"{exc_type.__module__}.{exc_type.__name__}", exc_type.__name__
        )

    return formatted


async def exception_to_crashed_state(
    exc: BaseException,
    result_factory: Optional[ResultFactory] = None,
) -> State:
    """
    Takes an exception that occurs _outside_ of user code and converts it to a
    'Crash' exception with a 'Crashed' state.
    """
    state_message = None

    if isinstance(exc, anyio.get_cancelled_exc_class()):
        state_message = "Execution was cancelled by the runtime environment."

    elif isinstance(exc, KeyboardInterrupt):
        state_message = "Execution was aborted by an interrupt signal."

    elif isinstance(exc, SystemExit):
        state_message = "Execution was aborted by Python system exit call."

    elif isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        try:
            request: httpx.Request = exc.request
        except RuntimeError:
            # The request property is not set
            state_message = f"Request failed while attempting to contact the server: {format_exception(exc)}"
        else:
            # TODO: We can check if this is actually our API url
            state_message = f"Request to {request.url} failed: {format_exception(exc)}."

    else:
        state_message = f"Execution was interrupted by an unexpected exception: {format_exception(exc)}"

    if result_factory:
        data = await result_factory.create_result(exc)
    else:
        # Attach the exception for local usage, will not be available when retrieved
        # from the API
        data = exc

    return Crashed(message=state_message, data=data)


async def exception_to_failed_state(
    exc: Optional[BaseException] = None,
    result_factory: Optional[ResultFactory] = None,
    **kwargs,
) -> State:
    """
    Convenience function for creating `Failed` states from exceptions
    """
    if not exc:
        _, exc, exc_tb = sys.exc_info()
        if exc is None:
            raise ValueError(
                "Exception was not passed and no active exception could be found."
            )
    else:
        exc_tb = exc.__traceback__

    if result_factory:
        data = await result_factory.create_result(exc)
    else:
        # Attach the exception for local usage, will not be available when retrieved
        # from the API
        data = exc

    existing_message = kwargs.pop("message", "")
    if existing_message and not existing_message.endswith(" "):
        existing_message += " "

    # TODO: Consider if we want to include traceback information, it is intentionally
    #       excluded from messages for now
    message = existing_message + format_exception(exc)

    return Failed(data=data, message=message, **kwargs)


async def return_value_to_state(retval: R, result_factory: ResultFactory) -> State[R]:
    """
    Given a return value from a user's function, create a `State` the run should
    be placed in.

    - If data is returned, we create a 'COMPLETED' state with the data
    - If a single, manually created state is returned, we use that state as given
        (manual creation is determined by the lack of ids)
    - If an upstream state or iterable of upstream states is returned, we apply the
        aggregate rule

    The aggregate rule says that given multiple states we will determine the final state
    such that:

    - If any states are not COMPLETED the final state is FAILED
    - If all of the states are COMPLETED the final state is COMPLETED
    - The states will be placed in the final state `data` attribute

    Callers should resolve all futures into states before passing return values to this
    function.
    """

    if (
        is_state(retval)
        # Check for manual creation
        and not retval.state_details.flow_run_id
        and not retval.state_details.task_run_id
    ):
        return retval

    # Determine a new state from the aggregate of contained states
    if is_state(retval) or is_state_iterable(retval):
        states = StateGroup(ensure_iterable(retval))

        # Determine the new state type
        new_state_type = (
            StateType.COMPLETED if states.all_completed() else StateType.FAILED
        )

        # Generate a nice message for the aggregate
        if states.all_completed():
            message = "All states completed."
        elif states.any_failed():
            message = f"{states.fail_count}/{states.total_count} states failed."
        elif not states.all_final():
            message = (
                f"{states.not_final_count}/{states.total_count} states are not final."
            )
        else:
            message = "Given states: " + states.counts_message()

        # TODO: We may actually want to set the data to a `StateGroup` object and just
        #       allow it to be unpacked into a tuple and such so users can interact with
        #       it
        return State(
            type=new_state_type,
            message=message,
            data=await result_factory.create_result(retval),
        )

    # Otherwise, they just gave data and this is a completed retval
    return Completed(data=await result_factory.create_result(retval))


@sync_compatible
async def get_state_exception(state: State) -> BaseException:
    """
    If not given a FAILED or CRASHED state, this raise a value error.

    If the state result is a state, its exception will be returned.

    If the state result is an iterable of states, the exception of the first failure
    will be returned.

    If the state result is a string, a wrapper exception will be returned with the
    string as the message.

    If the state result is null, a wrapper exception will be returned with the state
    message attached.

    If the state result is not of a known type, a `TypeError` will be returned.

    When a wrapper exception is returned, the type will be `FailedRun` if the state type
    is FAILED or a `CrashedRun` if the state type is CRASHED.
    """

    if state.is_failed():
        wrapper = FailedRun
    elif state.is_crashed():
        wrapper = CrashedRun
    else:
        raise ValueError(f"Expected failed or crashed state got {state!r}.")

    if isinstance(state.data, BaseResult):
        result = await state.data.get()
    elif state.data is None:
        result = None
    else:
        result = state.data

    if result is None:
        return wrapper(state.message)

    if isinstance(result, Exception):
        return result

    elif isinstance(result, BaseException):
        return result

    elif isinstance(result, str):
        return wrapper(result)

    elif isinstance(result, State):
        # Return the exception from the inner state
        return await get_state_exception(result)

    elif is_state_iterable(result):
        # Return the first failure
        for state in result:
            if state.is_failed() or state.is_crashed():
                return await get_state_exception(state)

        raise ValueError(
            "Failed state result was an iterable of states but none were failed."
        )

    else:
        raise TypeError(
            f"Unexpected result for failed state: {result!r} —— "
            f"{type(result).__name__} cannot be resolved into an exception"
        )


@sync_compatible
async def raise_state_exception(state: State) -> None:
    """
    Given a FAILED or CRASHED state, raise the contained exception.
    """
    if not (state.is_failed() or state.is_crashed()):
        return None

    raise await get_state_exception(state)


def is_state(obj: Any) -> TypeGuard[State]:
    """
    Check if the given object is a state type
    """
    return isinstance(obj, State)


def is_state_iterable(obj: Any) -> TypeGuard[Iterable[State]]:
    """
    Check if a the given object is an iterable of states types

    Supported iterables are:
    - set
    - list
    - tuple

    Other iterables will return `False` even if they contain states.
    """
    # We do not check for arbitary iterables because this is not intended to be used
    # for things like dictionaries, dataframes, or pydantic models

    if isinstance(obj, (list, set, tuple)) and obj:
        return all([is_state(o) for o in obj])
    else:
        return False


class StateGroup:
    def __init__(self, states: Iterable[State]) -> None:
        self.states = states
        self.type_counts = self._get_type_counts(states)
        self.total_count = len(states)
        self.not_final_count = self._get_not_final_count(states)

    @property
    def fail_count(self):
        return self.type_counts[StateType.FAILED] + self.type_counts[StateType.CRASHED]

    def all_completed(self) -> bool:
        return self.type_counts[StateType.COMPLETED] == self.total_count

    def any_failed(self) -> bool:
        return (
            self.type_counts[StateType.FAILED] > 0
            or self.type_counts[StateType.CRASHED] > 0
        )

    def all_final(self) -> bool:
        return self.not_final_count == self.total_count

    def counts_message(self) -> str:
        count_messages = [f"total={self.total_count}"]
        if self.not_final_count:
            count_messages.append(f"not_final={self.not_final_count}")
        for state_type, count in self.type_counts.items():
            if count:
                count_messages.append(f"{state_type.value!r}={count}")
        return ", ".join(count_messages)

    @staticmethod
    def _get_type_counts(states: Iterable[State]) -> Dict[StateType, int]:
        return Counter(state.type for state in states)

    @staticmethod
    def _get_not_final_count(states: Iterable[State]) -> int:
        return len(states) - sum(state.is_final() for state in states)

    def __repr__(self) -> str:
        return f"StateGroup<{self.counts_message()}>"


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

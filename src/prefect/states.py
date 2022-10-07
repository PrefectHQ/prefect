import sys
import traceback
import warnings
from collections import Counter
from types import TracebackType
from typing import Any, Dict, Iterable, Optional

import anyio
import httpx
from typing_extensions import TypeGuard

from prefect.client.schemas import Completed, Crashed, Failed, State
from prefect.deprecated.data_documents import (
    DataDocument,
    result_from_state_with_data_document,
)
from prefect.exceptions import CrashedRun, FailedRun
from prefect.futures import resolve_futures_to_states
from prefect.orion.schemas.states import StateType
from prefect.results import BaseResult, R, ResultFactory
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.collections import ensure_iterable


def format_exception(exc: BaseException, tb: TracebackType = None) -> str:
    return "".join(list(traceback.format_exception(type(exc), exc, tb=tb)))


def exception_to_crashed_state(exc: BaseException) -> Crashed:
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

    return Crashed(message=state_message)


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
    message = existing_message + format_exception(exc, exc_tb)

    return Failed(data=data, message=message, **kwargs)


async def return_value_to_state(result: R, result_factory: ResultFactory) -> State[R]:
    """
    Given a return value from a user's function, create a `State` the run should
    be placed in.

    - If data is returned, we create a 'COMPLETED' state with the data
    - If a single, manually created state is returned, we use that state as given
        (manual creation is determined by the lack of ids)
    - If an upstream state or iterable of upstream states is returned, we apply the aggregate rule
    - If a future or iterable of futures is returned, we resolve it into states then
        apply the aggregate rule

    The aggregate rule says that given multiple states we will determine the final state
    such that:

    - If any states are not COMPLETED the final state is FAILED
    - If all of the states are COMPLETED the final state is COMPLETED
    - The states will be placed in the final state `data` attribute

    The aggregate rule is applied to _single_ futures to distinguish from returning a
    _single_ state. This prevents a flow from assuming the state of a single returned
    task future.
    """

    if (
        is_state(result)
        # Check for manual creation
        and not result.state_details.flow_run_id
        and not result.state_details.task_run_id
    ):
        return result

    # Ensure any futures are resolved
    result = await resolve_futures_to_states(result)

    # If we resolved a task future or futures into states, we will determine a new state
    # from their aggregate
    if is_state(result) or is_state_iterable(result):
        states = StateGroup(ensure_iterable(result))

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
            data=await result_factory.create_result(result),
        )

    # Otherwise, they just gave data and this is a completed result
    return Completed(data=await result_factory.create_result(result))


@sync_compatible
async def get_state_result(state, raise_on_failure: bool = True) -> Any:
    """
    Get the result from a state.
    """
    if raise_on_failure and (state.is_failed() or state.is_crashed()):
        return await raise_state_exception(state)

    if isinstance(state.data, DataDocument):
        return result_from_state_with_data_document(
            state, raise_on_failure=raise_on_failure
        )
    elif isinstance(state.data, BaseResult):
        return await state.data.get()
    elif state.data is None:
        raise ValueError(
            "State data is missing. "
            "Typically, this occurs when result persistence is disabled and the "
            "state has been retrieved from the API."
        )
    else:
        # The result is attached directly
        return state.data


@sync_compatible
async def raise_state_exception(state: State) -> None:
    """
    Given a FAILED or CRASHED state, raise the contained exception.

    If not given a FAILED or CRASHED state, this function will return immediately.

    If the state contains a result of multiple states, the first failure will be raised.

    If the state result is a string, a wrapper exception will be raised with the
    string as the message.

    If the state result is a `BaseException`, a wrapper exception will be raised
    instead to prevent a base exception from crashing the runtime.

    If the state result is null, a wrapper exception will be raised with the state
    message attached.

    If the state result is not of a known type, a `TypeError` will be raised.

    When a wrapper exception is raised, the type will be `FailedRun` if the state type is
    FAILED or a `CrashedRun` if the state type is CRASHED.
    """
    if state.is_failed():
        wrapper = FailedRun
    elif state.is_crashed():
        wrapper = CrashedRun
    else:
        return None

    result = (
        await state.result(raise_on_failure=False, fetch=True)
        if state.data is not None
        else None
    )

    if result is None:
        raise wrapper(state.message)

    elif isinstance(result, Exception):
        raise result

    elif isinstance(result, BaseException):
        warnings.warn(
            f"State result is a {type(result).__name__!r} type and is not safe "
            f"to re-raise, it will be raised as a `{wrapper.__name__}` instead."
        )
        raise wrapper(str(result)) from result

    elif isinstance(result, State):
        # Raise the failure in the inner state
        await raise_state_exception(result)

        # Should not be reached, but if it is we must raise an error
        raise ValueError("Failed state result was a state that was not failed.")

    elif isinstance(result, str):
        raise wrapper(result)

    elif is_state_iterable(result):
        # Raise the first failure
        for state in result:
            await raise_state_exception(state)

        # Should not be reached, but if it is we must raise an error
        raise ValueError(
            "Failed state result contained multiple states but none were failed."
        )

    else:
        raise TypeError(
            f"Unexpected result for failed state: {result!r} —— "
            f"{type(result).__name__} cannot be resolved into an exception"
        )


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

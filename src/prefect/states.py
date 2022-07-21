from collections import Counter
from typing import Any, Dict, Iterable

import anyio
import httpx
from typing_extensions import TypeGuard

from prefect.client import OrionClient, inject_client
from prefect.futures import resolve_futures_to_states
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import Completed, Failed, StateType
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.collections import ensure_iterable

# Expose the state schema from Orion
from .orion.schemas.states import State


def exception_to_crashed_state(exc: BaseException) -> State:
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

    elif isinstance(exc, httpx.TimeoutException):
        try:
            request: httpx.Request = exc.request
        except RuntimeError:
            # The request property is not set
            state_message = "Request timed out while attempting to contact the server."
        else:
            # TODO: We can check if this is actually our API url
            state_message = f"Request to {request.url} timed out."

    else:
        state_message = "Execution was interrupted by an unexpected exception."

    return Failed(
        name="Crashed",
        message=state_message,
        data=safe_encode_exception(exc),
    )


def safe_encode_exception(exception: BaseException) -> DataDocument:
    try:
        document = DataDocument.encode("cloudpickle", exception)
    except Exception as exc:
        document = DataDocument.encode("cloudpickle", exc)
    return document


async def return_value_to_state(result: Any, serializer: str = "cloudpickle") -> State:
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
            data=DataDocument.encode(serializer, result),
        )

    # Otherwise, they just gave data and this is a completed result
    return Completed(data=DataDocument.encode(serializer, result))


@sync_compatible
@inject_client
async def raise_failed_state(state: State, client: "OrionClient") -> None:
    """
    Given a FAILED state, raise the contained exception.

    If not given a FAILED state, this function will return immediately.

    If the state contains a result of multiple states, the first FAILED state will be
    raised.

    If the state is FAILED but does not contain an exception type result, a `TypeError`
    will be raised.
    """
    if not state.is_failed():
        return

    result = await client.resolve_datadoc(state.data)

    if isinstance(result, BaseException):
        raise result

    elif isinstance(result, State):
        # Raise the failure in the inner state
        await raise_failed_state(result)

    elif is_state_iterable(result):
        # Raise the first failure
        for state in result:
            await raise_failed_state(state)

    else:
        raise TypeError(
            f"Unexpected result for failure state: {result!r} —— "
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
        return self.type_counts[StateType.FAILED]

    def all_completed(self) -> bool:
        return self.type_counts[StateType.COMPLETED] == self.total_count

    def any_failed(self) -> bool:
        return self.type_counts[StateType.FAILED] > 0

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

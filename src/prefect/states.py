"""
Contains methods for working with `State` objects defined by the Orion schema at
`prefect.orion.schemas.states`
"""
from typing import Iterable, Dict, Any
from collections.abc import Iterable as IterableABC
from collections import Counter

from prefect.orion.schemas.states import State, StateType
from prefect.utilities.collections import ensure_iterable
from prefect.futures import resolve_futures, future_to_state


def return_val_to_state(result: Any) -> State:
    """
    Given a return value from a user-function, create a `State` the run should
    be placed in.

    - If data is returned, we create a 'COMPLETED' state with the data
    - If a single state is returned and is not wrapped in a future, we use that state
    - If an iterable of states are returned, we apply the aggregate rule
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
    # States returned directly are respected without applying a rule
    if is_state(result):
        return result

    # Ensure any futures are resolved
    result = resolve_futures(result, resolve_fn=future_to_state)

    # If we resolved a task future or futures into states, we will determine a new state
    # from their aggregate
    if is_state(result) or is_state_iterable(result):
        states = StateSet(ensure_iterable(result))

        # Determine the new state type
        new_state_type = (
            StateType.COMPLETED if states.all_completed() else StateType.FAILED
        )

        # Generate a nice message for the aggregate
        if states.all_completed():
            message = "All states completed."
        elif states.any_failed():
            message = f"{states.fail_count}/{states.total_count} states failed."
        elif states.any_not_final():
            message = (
                f"{states.not_final_count}/{states.total_count} states were unfinished."
            )
        else:
            message = "Given states: " + states.counts_message()

        # TODO: We may actually want to set the data to a `StateSet` object and just allow
        #       it to be unpacked into a tuple and such so users can interact with it
        return State(data=result, type=new_state_type, message=message)

    # Otherwise, they just gave data and this is a completed result
    return State(type=StateType.COMPLETED, data=result)


def is_state(obj: Any) -> bool:
    return isinstance(obj, State)


def is_state_iterable(obj: Any):
    if isinstance(obj, IterableABC) and obj:
        return all([is_state(o) for o in obj])
    else:
        return False


class StateSet:
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

    def any_not_final(self) -> bool:
        return self.not_final_count > 0

    def counts_message(self) -> str:
        count_messages = [f"total={self.total_count}"]
        if self.not_final_count:
            count_messages.append(f"final={self.not_final_count}")
        for state_type, count in self.type_counts:
            if count:
                count_messages.append(f"{state_type.value!r}={count}")
        return ", ".join(count_messages)

    @staticmethod
    def _get_type_counts(states: Iterable[State]) -> Dict[StateType, int]:
        return Counter(state.type for state in states)

    @staticmethod
    def _get_not_final_count(states: Iterable[State]) -> int:
        return int(sum(state.is_final() for state in states))

    def __repr__(self) -> str:
        return f"StateSet<{self.counts_message()}>"

"""
Contains methods for working with `State` objects defined by the Orion schema at
`prefect.orion.schemas.states`
"""
from typing import Union, Iterable, Dict, Any, Callable
from collections.abc import Iterable as IterableABC

from prefect.orion.schemas.states import State, StateType
from prefect.utilities.collections import ensure_iterable
from prefect.futures import resolve_futures, future_to_state


def all_completed(states: Union[State, Iterable[State]]) -> State:
    """
    If all of the given states are COMPLETED return a new COMPLETED state; otherwise,
    return a FAILED state.

    The input states will be placed in the `data` attribute. The new state will be given
    a message summarizing the input states.
    """
    input_states = states
    states = StateSet(ensure_iterable(states))

    # Determine the new state type
    new_state_type = (
        StateType.COMPLETED if states.all_are_completed() else StateType.FAILED
    )

    # TODO: We may actually want to set the data to a `StateSet` object and just allow
    #       it to be unpacked into a tuple and such so users can interact with it
    return State(data=input_states, type=new_state_type, message=states.short_message())


def result_to_state(
    result: Any, state_rule: Callable[[Iterable[State]], State] = all_completed
) -> State:
    # States returned directly are respected without applying a rule
    if is_state(result):
        return result

    # Ensure any futures are resolved
    result = resolve_futures(result, resolve_fn=future_to_state)

    # If we still have states, apply the rule to get a result
    if is_state(result) or is_state_iterable(result):
        return state_rule(result)

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
        self.unfinished_count = self._get_unfinished_count(states)

    @property
    def fail_count(self):
        return self.type_counts[StateType.FAILED]

    def all_are_completed(self) -> bool:
        return self.type_counts[StateType.COMPLETED] == self.total_count

    def any_are_failed(self) -> bool:
        return self.type_counts[StateType.FAILED] > 0

    def any_are_unfinished(self) -> bool:
        return self.unfinished_count > 0

    def short_message(self) -> str:
        if self.all_are_completed():
            return "All states completed."
        elif self.any_are_failed():
            return f"{self.fail_count}/{self.total_count} states failed."
        elif self.any_are_unfinished():
            return f"{self.unfinished_count}/{self.total_count} states were unfinished."
        else:
            # Short message is not implemented for this case so return the long message
            return self.summary_message()

    def summary_message(self) -> str:
        message = f"Of a total of {self.total_count} states,"
        count_messages = []
        for state_type, count in self.type_counts:
            if not count:
                continue
            count_messages.append(f"{count} states were {state_type.value!r}")
        message += ", ".join(count_messages)
        return message + "."

    @staticmethod
    def _get_type_counts(states: Iterable[State]) -> Dict[StateType, int]:
        type_counts = {state_type: 0 for state_type in StateType.__members__.values()}

        for state in states:
            type_counts[state.type] += 1

        return type_counts

    @staticmethod
    def _get_unfinished_count(states: Iterable[State]) -> int:
        return int(sum(map(lambda state: state.is_finished(), states)))

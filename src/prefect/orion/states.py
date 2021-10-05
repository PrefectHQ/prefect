"""
Contains methods for working with `State` objects defined by the Orion schema at
`prefect.orion.schemas.states`
"""
from collections import Counter
from collections.abc import Iterable as IterableABC
from typing import Any, Dict, Iterable

from prefect.orion.schemas.states import State, StateType


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
        return f"StateSet<{self.counts_message()}>"

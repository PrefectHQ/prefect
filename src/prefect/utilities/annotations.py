from typing import Any


class unmapped:
    """A container that acts as an infinite array where all items are the same
    value. Used for Task.map where there is a need to map over a single
    value"""

    def __init__(self, value: Any):
        self.value = value

    def __getitem__(self, _) -> Any:
        return self.value

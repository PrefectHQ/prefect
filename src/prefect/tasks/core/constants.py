"""
The tasks in this module can be used to represent constant values.

In general, users will not instantiate these tasks by hand; they will automatically be
applied when users create dependencies between a task and a constant value.
"""

from typing import Any

import prefect


class Constant(prefect.Task):
    """
    The Constant class represents a single value in the flow graph.

    Args:
        - value (Any): a constant value
        - name (str): a name for the constant; defaults to "Constant[(type(value))]"
            if not provided
        - **kwargs (Any): kwargs to pass to the Task constructor
    """

    def __init__(self, value: Any, name: str = None, **kwargs: Any):
        self.value = value

        # set the name from the value
        if name is None:
            name = repr(self.value)
            if len(name) > 8:
                name = "Constant[{}]".format(type(self.value).__name__)

        super().__init__(name=name, **kwargs)

    def run(self) -> Any:
        return self.value

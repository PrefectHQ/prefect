"""
The tasks in this module can be used to represent constant values.

In general, users will not instantiate these tasks by hand; they will be automatically created
whenever the Prefect engine detects that a constant value is required. In many cases, Prefect
will not add `Constant` tasks to the graph; optimizing them as flow-level attributes instead.
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

    Constant tasks are most commonly used to prevent Prefect from creating a large number
    of auto-generated tasks in Python collections.
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

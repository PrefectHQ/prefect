"""
The tasks in this module can be used to represent constant values.

In general, users will not instantiate these tasks by hand; they will automatically be
applied when users create dependencies between a task and a constant value.

Constant tasks are most commonly used to prevent Prefect from creating a large number
of auto-generated tasks in Python collections.  For example,

```python
from prefect import task, Flow
from prefect.tasks.core.constants import Constant

@task
def do_nothing(values):
    return values

with Flow("Many Small Tasks") as large_flow:
    result = do_nothing({"x": 1, "z": 99})

large_flow.tasks
#    {<Task: 'x'>,
#     <Task: 'z'>,
#     <Task: 1>,
#     <Task: 99>,
#     <Task: Dict>,
#     <Task: List>,
#     <Task: List>,
#     <Task: do_nothing>}

with Flow("Two Tasks") as small_flow:
    result = do_nothing(Constant({"x": 1, "z": 99}))

small_flow.tasks
# {<Task: Constant[dict]>, <Task: do_nothing>}
```
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

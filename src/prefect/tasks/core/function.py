"""
The tasks in this module can be used to represent arbitrary functions.

In general, users will not instantiate these tasks by hand; they will automatically be
applied when users apply the `@task` decorator.
"""

import inspect
from typing import Any, Callable

import prefect


class FunctionTask(prefect.Task):
    """
    A convenience Task for functionally creating Task instances with
    arbitrary callable `run` methods.

    Args:
        - fn (callable): the function to be the task's `run` method
        - name (str, optional): the name of this task
        - **kwargs: keyword arguments which will be passed to the Task
            constructor

    Raises:
        - ValueError: if the provided function violates signature requirements
            for Task run methods

    Example:
    ```python
    task = FunctionTask(lambda x: x - 42, name="Subtract 42")

    with Flow("My Flow") as f:
        result = task(42)
    ```
    """

    def __init__(self, fn: Callable, name: str = None, **kwargs: Any):
        if not callable(fn):
            raise TypeError("fn must be callable.")

        # set the name from the fn
        if name is None:
            name = getattr(fn, "__name__", type(self).__name__)

        prefect.core.task._validate_run_signature(fn)  # type: ignore
        self.run = fn

        super().__init__(name=name, **kwargs)

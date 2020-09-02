"""
The tasks in this module can be used to represent arbitrary functions.

In general, users will not instantiate these tasks by hand; they will
automatically be applied when users apply the `@task` decorator.
"""

from typing import Any, Callable

import prefect


class _DocProxy(object):
    """A descriptor that proxies through the docstring for the wrapped task as
    the docstring for a `FunctionTask` instance."""

    def __init__(self, cls_doc):
        self._cls_doc = cls_doc

    def __get__(self, obj, cls):
        if obj is None:
            return self._cls_doc
        else:
            return getattr(obj.run, "__doc__", None) or self._cls_doc


class FunctionTask(prefect.Task):
    __doc__ = _DocProxy(
        """A convenience Task for functionally creating Task instances with
    arbitrary callable `run` methods.

    Args:
        - fn (callable): the function to be the task's `run` method
        - name (str, optional): the name of this task
        - **kwargs: keyword arguments that will be passed to the Task
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
    )

    def __init__(self, fn: Callable, name: str = None, **kwargs: Any):
        if not callable(fn):
            raise TypeError("fn must be callable.")

        # set the name from the fn
        if name is None:
            name = getattr(fn, "__name__", type(self).__name__)

        prefect.core.task._validate_run_signature(fn)  # type: ignore
        self.run = fn

        super().__init__(name=name, **kwargs)

    def __getattr__(self, k):
        if k == "__wrapped__":
            return self.run
        raise AttributeError(
            f"'FunctionTask' object has no attribute {k}."
            " Did you call this object within a function that should have been"
            "decorated with @prefect.task?"
        )

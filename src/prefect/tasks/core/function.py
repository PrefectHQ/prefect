import inspect
from typing import Callable

import prefect


class FunctionTask(prefect.Task):
    def __init__(self, fn: Callable, name: str = None, **kwargs) -> None:
        if not callable(fn):
            raise TypeError("fn must be callable.")

        # set the name from the fn
        if name is None:
            name = getattr(fn, "__name__", type(self).__name__)

        prefect.core.task._validate_run_signature(fn)
        self.run = fn

        super().__init__(name=name, **kwargs)

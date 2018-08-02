import datetime
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, TypeVar, Union

import prefect
from prefect.utilities.json import Serializable


__all__ = ["Executor"]


class Executor(Serializable):
    def __init__(self):
        self.executor_id = type(self).__name__ + ": " + str(uuid.uuid4())

    @contextmanager
    def start(self) -> Iterable[None]:
        """
        Any initialization this executor needs to perform should be done in this
        context manager, and torn down after yielding.
        """
        yield

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Submit a function to the executor for execution. Returns a future
        """
        raise NotImplementedError()

    def wait(self, futures: Iterable, timeout: datetime.timedelta = None) -> Iterable:
        """
        Resolves futures to their values. Blocks until the future is complete.
        """
        raise NotImplementedError()

    def submit_with_context(
        self, fn: Callable, *args: Any, context: Dict, **kwargs: Any
    ) -> Any:
        """
        Submit a function to the executor that will be run in a specific Prefect context.

        Returns a Any.
        """

        def run_fn_in_context(*args, context, **kwargs):
            with prefect.context(context):
                return fn(*args, **kwargs)

        return self.submit(run_fn_in_context, *args, context=context, **kwargs)

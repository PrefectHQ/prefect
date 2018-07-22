import datetime
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, TypeVar, Union

import prefect
from prefect.utilities.json import Serializable

Future = TypeVar("Future")


class Executor(Serializable):

    @contextmanager
    def start(self):
        """
        Any initialization this executor needs to perform should be done in this
        context manager, and torn down after yielding.
        """
        yield

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        """
        Submit a function to the executor for execution. Returns a future
        """
        raise NotImplementedError()

    def wait(self, futures: List[Future], timeout: datetime.timedelta = None) -> Any:
        """
        Resolves futures to their values. Blocks until the future is complete.
        """
        raise NotImplementedError()

    def submit_with_context(
        self, fn: Callable, *args: Any, context: Dict, **kwargs: Any
    ) -> Future:
        """
        Submit a function to the executor that will be run in a specific Prefect context.

        Returns a Future.
        """

        def run_fn_in_context(*args, context, **kwargs):
            with prefect.context(context):
                return fn(*args, **kwargs)

        return self.submit(run_fn_in_context, *args, context=context, **kwargs)


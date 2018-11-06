# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import datetime
from typing import Any, Callable, Iterable

from prefect.engine.executors.base import Executor
from prefect.utilities.executors import dict_to_list, main_thread_timeout


class LocalExecutor(Executor):
    """
    An executor that runs all functions synchronously and immediately in
    the main thread.  To be used mainly for debugging purposes.
    """

    timeout_handler = staticmethod(main_thread_timeout)

    def map(
        self, fn: Callable, *args: Any, upstream_states: dict, **kwargs: Any
    ) -> Iterable[Any]:

        states = dict_to_list(upstream_states)
        results = []
        for elem in states:
            results.append(self.submit(fn, *args, upstream_states=elem, **kwargs))

        return results

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Submit a function to the executor for execution. Returns the result of the computation.

        Args:
            - fn (Callable): function which is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Any: the result of `fn(*args, **kwargs)`
        """
        return fn(*args, **kwargs)

    def wait(self, futures: Any, timeout: datetime.timedelta = None) -> Any:
        """
        Returns the results of the provided futures.

        Args:
            - futures (Any): objects to wait on
            - timeout (datetime.timedelta): timeout to allow for execution; in
            this case, this kwarg is ignored

        Returns:
            - Any: whatever `futures` were provided
        """
        return futures

# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any, Callable, Iterable

from prefect.engine.executors.base import Executor, time_type
from prefect.utilities.executors import dict_to_list


class LocalExecutor(Executor):
    """
    An executor that runs all functions synchronously and immediately in
    the local thread.  To be used mainly for debugging purposes.
    """

    def map(
        self, fn: Callable, *args: Any, upstream_states=None, **kwargs: Any
    ) -> Iterable[Any]:

        states = dict_to_list(upstream_states)
        results = []
        for elem in states:
            results.append(self.submit(fn, *args, upstream_states=elem, **kwargs))

        return results

    def submit(self, fn, *args, timeout: time_type = None, **kwargs):
        """
        Submit a function to the executor for execution. Returns the result of the computation.

        Args:
            - fn (Callable): function which is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - timeout (datetime.timedelta or int): maximum length of time to allow for
                execution; if `int` is provided, interpreted as seconds.
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Any: the result of `fn(*args, **kwargs)`
        """
        if timeout is not None:
            return self.submit_with_timeout(fn, *args, timeout=timeout, **kwargs)
        return fn(*args, **kwargs)

    def wait(self, futures, timeout=None):
        """
        Returns:
            - Any: whatever `futures` were provided
        """
        return futures

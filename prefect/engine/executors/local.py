from contextlib import contextmanager
from prefect.engine.executors import Executor


class LocalExecutor(Executor):
    """
    An executor that runs all functions synchronously and in
    the local thread.

    LocalExecutors serve as their own Executor contexts.
    """

    @contextmanager
    def __call__(self, **kwargs):
        yield self

    def submit(self, fn, *args, _client_kwargs=None, **kwargs):
        """
        Runs a function locally
        """
        return fn(*args, **kwargs)

    def wait(self, futures, timeout=None):
        """
        Returns the provided futures
        """
        return futures

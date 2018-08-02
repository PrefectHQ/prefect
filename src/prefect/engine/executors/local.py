from prefect.engine.executors.base import Executor


__all__ = ["LocalExecutor"]


class LocalExecutor(Executor):
    """
    An executor that runs all functions synchronously and in
    the local thread.

    LocalExecutors serve as their own Executor contexts.
    """

    def submit(self, fn, *args, **kwargs):
        """
        Runs a function locally
        """
        return fn(*args, **kwargs)

    def wait(self, futures, timeout=None):
        """
        Returns the provided futures
        """
        return futures

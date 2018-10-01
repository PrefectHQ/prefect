# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from prefect.engine.executors.base import Executor


class LocalExecutor(Executor):
    """
    An executor that runs all functions synchronously and immediately in
    the local thread.  To be used mainly for debugging purposes.
    """

    def submit(self, fn, *args, **kwargs):
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

    def wait(self, futures, timeout=None):
        """
        Returns:
            - Any: whatever `futures` were provided
        """
        return futures

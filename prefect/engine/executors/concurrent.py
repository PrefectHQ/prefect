import concurrent.futures
from contextlib import contextmanager

from prefect.engine.executors import Executor


class ThreadPoolExecutor:

    def __init__(self, threads):
        self.threads = threads
        super().__init__()

    @contextmanager
    def __call__(self, context, **kwargs):
        with concurrent.futures.ThreadPoolExecutor(self.threads) as executor:
            yield ConcurrentExecutor(executor=executor)


class ProcessPoolExecutor:

    def __init__(self, processes):
        self.processes = processes
        super().__init__()

    @contextmanager
    def __call__(self, context, **kwargs):
        with concurrent.futures.ProcessPoolExecutor(self.processes) as executor:
            yield ConcurrentExecutor(executor=executor)


class ConcurrentExecutor(Executor):

    def __init__(self, executor):
        self.executor = executor

    def submit(self, fn, *args, _client_kwargs=None, **kwargs):
        """
        Runs a function locally
        """
        return self.executor.submit(fn, *args, **kwargs)

    def wait(self, futures, timeout=None):
        """
        Returns the provided futures
        """
        return concurrent.futures.wait(futures, timeout=timeout)

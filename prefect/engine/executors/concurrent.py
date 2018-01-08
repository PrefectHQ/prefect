import concurrent.futures
from contextlib import contextmanager

from prefect.engine.executors import Executor


class ConcurrentExecutor(Executor):

    def __init__(self):
        self.executor = None
        super().__init__()

    def __getstate__(self):
        state = self.__dict__.copy()
        state['executor'] = None
        return state

    def submit(self, fn, *args, **kwargs):
        return self.executor.submit(fn, *args, **kwargs)

    def wait(self, futures, timeout=None):
        return concurrent.futures.wait(futures, timeout=timeout)


class ThreadPoolExecutor(ConcurrentExecutor):

    def __init__(self, threads):
        self.threads = threads
        super().__init__()

    @contextmanager
    def execution_context(self, **kwargs):
        old_executor = self.executor
        with concurrent.futures.ThreadPoolExecutor(self.threads) as executor:
            self.executor = executor
            yield self
            self.executor = old_executor


class ProcessPoolExecutor(ConcurrentExecutor):

    def __init__(self, processes):
        self.processes = processes
        self.executor = None
        super().__init__()

    @contextmanager
    def execution_context(self, **kwargs):
        old_executor = self.executor
        with concurrent.futures.ProcessPoolExecutor(self.processes) as executor:
            self.executor = executor
            yield self
            self.executor = old_executor

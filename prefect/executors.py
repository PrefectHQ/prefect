import abc
from contextlib import contextmanager
import concurrent.futures
import copy
import distributed
import prefect


class Executor(metaclass=abc.ABCMeta):

    def __init__(self):
        pass

    def __repr__(self):
        return '<{}>'.format(type(self).__name__)

    @contextmanager
    def __call__(self):
        # create a copy so that the original can be serialized without worrying
        # about any attributes created by the context
        executor_copy = copy.copy(self)
        with executor_copy.executor_context():
            yield executor_copy

    @contextmanager
    def executor_context(self):
        """
        Returns an "executor" context manager.

        run_flow and run_task are always called inside the context,
        but other methods (like before_flow_run) can be called
        any time.
        """
        yield None

    @abc.abstractmethod
    def run_flow(self, flow_runner, *args, **kwargs):
        """
        Runs a flow.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def run_task(self, task_runner, upstream_edges, context):
        """
        Runs a task.
        """
        raise NotImplementedError()

    def gather(self, results):
        """
        Called to run any final steps on the results of run_flow and run_task.

        Should block and return actual results, if the executor runs async.
        """
        return results


class LocalExecutor(Executor):
    """
    Executes Flows and Tasks in the local process.
    """

    @contextmanager
    def executor_context(self):
        yield None

    def run_flow(self, flow_runner, *args, **kwargs):
        """
        Runs a flow in the executor.
        """
        return flow_runner.run(*args, **kwargs)

    def run_task(
            self,
            task_runner,
            upstream_edges,
            context):
        """
        Runs a task in the executor.
        """
        return task_runner.run(
            upstream_edges=upstream_edges,
            context=context)


class ThreadPoolExecutor(Executor):
    """
    Executes flows and tasks in a ThreadPool
    """

    def __init__(self, threads=10):
        self.threads = threads
        super().__init__()

    @contextmanager
    def executor_context(self):
        try:
            with concurrent.futures.ThreadPoolExecutor(self.threads) as executor:
                self.executor = executor
                yield
        finally:
            self.executor = None

    @property
    def executor(self):
        if getattr(self, '_executor', None):
            return self._executor
        else:
            raise ValueError(
                'Executor can only be accessed inside the executor_context()')

    @executor.setter
    def executor(self, val):
        self._executor = val

    def run_flow(self, flow_runner, **params):
        """
        Runs a flow in the executor.
        """
        return self.executor.submit(flow_runner.run, **params)

    def run_task(
            self, task_runner, upstream_edges, context):
        """
        Runs a task in the executor.
        """
        concurrent.futures.wait(e['state'] for e in upstream_edges)
        for e in upstream_edges:
            e['state'] = e['state'].result()
        return self.executor.submit(
            task_runner.run,
            upstream_edges=upstream_edges,
            context=context)

    def gather(self, results):
        # block until results are complete
        concurrent.futures.wait(results)
        return {k: v.result() for k, v in results.items()}


class DistributedExecutor(Executor):
    """
    Executes flows and tasks in a Distributed cluster
    """

    @property
    def client(self):
        if getattr(self, '_client', None):
            return self._client
        else:
            raise ValueError(
                'Client can only be accessed inside the executor_context()')

    @client.setter
    def client(self, val):
        self._client = val

    @contextmanager
    def executor_context(self, state):
        try:
            with prefect.utilties.cluster.client() as client:
                self.client = client
                yield
        finally:
            self.client = None

    def run_flow(self, flow_runner, **params):
        return self.client.submit(flow_runner.run, **params)

    def run_task(
            self, task_runner, upstream_edges, context):
        return self.client.submit(
            task_runner.run,
            upstream_edges=upstream_edges,
            context=context,
            resources=task_runner.task.resources,
            pure=False)

    def gather(self, results):
        return self.client.gather(results)

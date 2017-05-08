import abc
import collections
from contextlib import contextmanager
import concurrent.futures
import copy
import distributed
from functools import partial
import prefect


class DistributedExecutor:
    """
    Executes flows and tasks in a Distributed cluster
    """

    def __new__(obj, *args, **kwargs):
        instance = super().__new__(obj)
        instance._init_args = args
        instance._init_kwargs = kwargs
        return instance

    def __init__(self):
        pass

    def __repr__(self):
        return '<{}>'.format(type(self).__name__)

    def copy(self):
        return type(self)(*self._init_args, **self._init_kwargs)

    @contextmanager
    def client(self):
        with prefect.utilities.cluster.client() as client:
            yield client

    @contextmanager
    def __call__(self, **context):
        with self.context(**context):
            with self.client() as client:
                client.run_task = partial(self.run_task, client=client)
                client.run_flow = partial(self.run_flow, client=client)
                yield client

    @contextmanager
    def context(self, **context):
        """
        Context manager that creates a Prefect context including functions
        for running tasks and flows in this executor.
        """

        def run_task(task, block=False, **inputs):
            with self.client() as client:
                future = self.run_task(
                    client=client,
                    task=task,
                    upstream_states={},
                    inputs=inputs,
                    context=prefect.context.to_dict())
                if block:
                    return client.gather(future)

        def run_flow(flow, block=False, **params):
            with self.client() as client:
                future = self.run_flow(
                    client=client,
                    flow=flow,
                    params=params,
                    context=prefect.context.to_dict())
                if block:
                    return client.gather(future)

        def update_progress(n, total=None):
            pass

        context.update(
            {
                'run_task': run_task,
                'run_flow': run_flow,
                'update_progress': update_progress,
            })

        with prefect.context(**context) as context:
            yield context

    def run_task(
            self, client, task, upstream_states, inputs, context=None,
            run_id=None):

        prefect_context = prefect.context.to_dict()
        if context is not None:
            prefect_context.update(context)

        if run_id is None:
            run_id = prefect_context.get('run_id')

        task_runner = prefect.runners.TaskRunner(
            task=task, run_id=run_id, executor=self.copy())

        print('submitting!')
        return client.submit(
            task_runner.run,
            state=None,
            upstream_states=upstream_states,
            inputs=inputs,
            context=prefect_context,
            resources=task.resources,
            pure=False)

    def run_flow(self, client, flow, params, context=None, run_id=None):

        prefect_context = prefect.context.to_dict()
        if context is not None:
            prefect_context.update(context)

        flow_runner = prefect.runners.FlowRunner(
            flow=flow, run_id=run_id, executor=self.copy())

        return client.submit(
            flow_runner.run,
            state=None,
            context=context,
            **params,)

    def run_isolated(self):
        pass


class ThreadPoolExecutor(DistributedExecutor):
    """
    Executes flows and tasks in a LocalCluster ThreadPool
    """

    def __init__(self, threads=10):
        self.threads = threads
        super().__init__()

    @contextmanager
    def client(self):
        lc_args = dict(
            n_workers=1, threads_per_worker=self.threads, nanny=False,)
        with distributed.LocalCluster(**lc_args) as cluster:
            address = cluster.scheduler_address
            with prefect.utilities.cluster.client(address=address) as client:
                yield client

class _LocalClient:
    """
    A mock Distributed client that executes all functions synchronously
    """

    def submit(self, fn, *args, pure=False, resources=None, **kwargs):
        return fn(*args, **kwargs)

    def gather(self, futures):
        return futures

class LocalExecutor(DistributedExecutor):
    """
    An executor that runs all tasks / flows synchronously
    """

    @contextmanager
    def client(self):
        yield _LocalClient()

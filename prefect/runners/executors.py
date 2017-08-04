"""
Executors are responsible for submitting flows and tasks to the backend
for execution.

They have a few main functions:
    1. run_flow(): creates a FlowRun and submits it for execution
    2. run_task(): creates a TaskRun and submits it for execution
    3. execute_task(): submits a task's run() function for execution
    4. context(): sets up a Prefect context that allows calls back to the
        executor.
"""
import abc
import collections
import concurrent.futures
import copy
from contextlib import contextmanager
from functools import partial

import distributed

import prefect
from prefect.utilities.cluster import client as prefect_client


def default_executor():
    option = prefect.config.get('executor', 'default_executor') or 'Executor'
    executor_cls = getattr(prefect.runners.executors, option)
    return executor_cls()


class Executor:

    def __init__(self, serializer=None):
        if serializer is None:
            serializer = prefect.serializers.IdentitySerializer()
        self.serializer = serializer

    def run_flow(self, flow, state, start_tasks=None):
        flow_runner = prefect.runners.FlowRunner(flow, executor=self)
        return flow_runner.run(state=state, start_tasks=start_tasks)

    def run_task(self, task, state, upstream_states, inputs, context=None):
        """
        Arguments
            task: a Prefect Task
            state: a Prefect TaskState
            upstream_states (dict): a dict of { task.name: TaskState } pairs
            inputs (dict): a dict of { key: input } pairs
            context (dict): a context dictionary
        """
        task_runner = prefect.runners.TaskRunner(task, executor=self)
        return task_runner.run(
            state=state,
            upstream_states=upstream_states,
            inputs=inputs,
            context=context)

    def serialize_result(self, result, context=None):
        with prefect.context(context):
            return self.serializer.encode(result)

    def deserialize_result(self, result, context=None):
        """
        task: a Prefect task
        result: the task's serialized result
        context: a Prefect context dictionary
        """
        if result is None:
            return None
        else:
            with prefect.context(context):
                return self.serializer.decode(result)

    @contextmanager
    def client(self, context=None, **kwargs):
        with prefect.context(context):
            with distributed.worker_client(**kwargs) as client:
                yield client


class LocalClient:
    """
    A mock Distributed client that executes all functions locally and
    synchronously
    """

    def submit(self, fn, *args, **kwargs):
        for kw in ['pure', 'resources', 'key']:
            kwargs.pop(kw, None)
        return fn(*args, **kwargs)

    def gather(self, futures):
        return futures

    def close(self):
        pass


class LocalExecutor(Executor):
    """
    An executor that runs all tasks / flows in the local process for debugging.

    This Executor uses a dummy client that has minimal functionality
    """

    @contextmanager
    def client(self, context=None, **kwargs):
        with prefect.context(context):
            yield LocalClient()


# def context_client

# class Executor:
#
#     def __init__(self, distributed_client):
#         if prefect_server is None:
#             prefect_server = prefect.config.get('prefect', 'server')
#         self.distributed_client = distributed_client
#         self.prefect_client = prefect.Client(
#             server=prefect_server,
#             token=prefect_token)
#         self.futures_store = self.distributed_client.channel(
#             'futures-store',
#             max_len=1000000)
#
#     def submit(fn, *args, pure_=False, **kwargs):
#         future = self.distributed_client.submit(
#             fn, *args, **kwargs, pure=pure_)
#         self.futures_store.append(future)
#         return future
#
#     def safe_submit(fn, *args, **kwargs):
#         return self.submit(fn, *args, **kwargs)
#
#     def run_flow(self, flow, params, context=None, flowrun_id=None):
#
#         self.prefect_client.ensure_flow_exists(flow)
#
#         flow_runner = prefect.runners.FlowRunner(
#             flow=flow,
#             id=flowrun_id,
#             executor_class=type(self))
#
#         flowrun_state = self.prefect_client.get_flowrun_state(
#             flow_runner.flowrun_id)
#
#         current_context = prefect.context.to_dict()
#         current_context.update(context or {})
#
#         return self.submit(
#             flow_runner.run,
#             state=flowrun_state,
#             context=current_context)
#
#
#     def run_task(self, task, upstream_results, inputs, state, flowrun_id=None):
#         self.prefect_client.ensure_task_exists(task)
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
# class Executor:
#     """
#     Executes flows and tasks in a Distributed cluster
#     """
#
#     def __new__(obj, *args, **kwargs):
#         instance = super().__new__(obj)
#         instance._init_args = args
#         instance._init_kwargs = kwargs
#         return instance
#
#     def __init__(self):
#         pass
#
#     def __repr__(self):
#         return '<{}>'.format(type(self).__name__)
#
#     def copy(self):
#         return type(self)(*self._init_args, **self._init_kwargs)
#
#     @contextmanager
#     def client(self, separate_thread=True):
#         with prefect_client(separate_thread=separate_thread) as client:
#             yield client
#
#     @contextmanager
#     def __call__(self, **context):
#         """
#         Creates a Prefect context and execution client.
#         """
#         with self.context(**context):
#             with self.client() as client:
#                 client.run_task = partial(self.run_task, client=client)
#                 client.run_flow = partial(self.run_flow, client=client)
#                 yield client
#
#     @contextmanager
#     def context(self, **context):
#         """
#         Context manager that creates a Prefect context including functions
#         for running tasks and flows in this executor.
#         """
#
#         def run_task(task, block=False, **inputs):
#             with self.client() as client:
#                 future = self.run_task(
#                     client=client,
#                     task=task,
#                     upstream_states={},
#                     inputs=inputs,
#                     context=prefect.context.to_dict())
#                 if block:
#                     return client.gather(future)
#
#         def run_flow(flow, block=False, **params):
#             with self.client() as client:
#                 future = self.run_flow(
#                     client=client,
#                     flow=flow,
#                     params=params,
#                     context=prefect.context.to_dict())
#                 if block:
#                     return client.gather(future)
#
#         context.update(
#             {
#                 'run_task': run_task,
#                 'run_flow': run_flow,
#             })
#
#         with prefect.context(**context) as context:
#             yield context
#
#     def run_flow(self, client, flow, params, context=None, id=None,):
#
#         prefect_context = prefect.context.to_dict()
#         if context is not None:
#             prefect_context.update(context)
#
#         flow_runner = prefect.runners.FlowRunner(
#             flow=flow, id=id, executor=self.copy())
#
#         return client.submit(
#             flow_runner.run,
#             state=None,
#             context=context,
#             **params,)
#
#     def run_task(
#             self,
#             client,
#             task,
#             upstream_results,
#             inputs,
#             state=None,
#             context=None,
#             flowrun_id=None,):
#         """
#         Runs a task.
#         """
#
#         prefect_context = prefect.context.to_dict()
#         prefect_context.update(context or {})
#
#         if flowrun_id is None:
#             flowrun_id = prefect_context.get('flowrun_id')
#
#         task_runner = prefect.runners.TaskRunner(
#             task=task, flowrun_id=flowrun_id, executor=self.copy())
#
#         return client.submit(
#             task_runner.run,
#             state=state,
#             upstream_states={k: v.state for k, v in upstream_results.items()},
#             inputs=inputs,
#             context=prefect_context,
#             resources=task.resources,
#             pure=False)
#
#     def _execute_task(self, execute_fn, inputs, context=None):
#         """
#         Executes the actual task function.
#
#         This method should only be called directly by a TaskRunner
#         """
#         prefect_context = prefect.context.to_dict()
#         if context is not None:
#             prefect_context.update(context)
#         return execute_fn(inputs=inputs, context=prefect_context)
#
#
# class LocalExecutor(Executor):
#     pass
#
# class DebugExecutor(Executor):
#     """
#     An executor that runs all tasks / flows in the local process for debugging
#     """
#
#     class LocalClient:
#         """
#         A mock Distributed client that executes all functions synchronously
#         """
#
#         def submit(self, fn, *args, pure=False, resources=None, **kwargs):
#             return fn(*args, **kwargs)
#
#         def gather(self, futures):
#             return futures
#
#
#     @contextmanager
#     def client(self, separate_thread=True):
#         yield self.LocalClient()
#
#

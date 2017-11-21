import abc
from functools import wraps
from contextlib import contextmanager
import prefect
from prefect.engine.task_runner import TaskRunner


def submit_to_self(method):
    """
    Decorator for executor methods that automatically executes them in the
    Executor.

    When a decorated method is called, it and its arguments are automatically
    passed to the executor's submit() method. The Prefect context is also
    serialized and provided. The resulting future is returned.

    class MyExecutor(Executor):

        @submit_to_self
        def method_that_should_run_on_client(x, y):
            return x + y

    """

    def method_with_context(*args, _context, **kwargs):
        with prefect.context.Context(_context):
            return method(*args, **kwargs)

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with prefect.context.Context(kwargs.get('context', {})):
            return self.submit(
                method_with_context,
                self,
                *args,
                _context=prefect.context.Context.as_dict(),
                **kwargs)

    return wrapper


class Executor(metaclass=abc.ABCMeta):
    """
    Executors are objects that yield ExecutorClients, which in turn
    can submit/resolve functions for execution.

    Executor clients are frequently tied to a specific thread, process,
    node, or cluster and often can't be passed between objects. Therefore it
    is important that the Executor object itself is thread-safe and
    serializeable. Prefect classes will never access the executor directly;
    they will first enter an execution context by calling the executor's
    client() method and using the resulting object as the executor.
    """

    def __init__(self):
        pass

    @contextmanager
    def execution_context(self):
        """
        This method is called
        """
        yield

    @abc.abstractmethod
    def submit(self, fn, *args, _client_kwargs=None, **kwargs):
        """
        Submit a function to the executor for execution. Returns a future.
        """
        pass

    @abc.abstractmethod
    def wait(self, futures, timeout=None):
        """
        Resolves futures to their values. Blocks until the future is complete.
        """
        pass

    def set_state(self, state, new_state, result=None):
        """
        Update a state object with a new state and optional result.

        This method must update the passed state object, even if it performs
        other asynchronous operations.
        """
        state.set_state(new_state, result=result)

    @submit_to_self
    def run_task(
            self,
            task,
            state,
            upstream_states,
            inputs,
            ignore_trigger=False,
            context=None):
        task_runner = prefect.engine.TaskRunner(task=task, executor=self)
        return task_runner.run(
            state=state,
            upstream_states=upstream_states,
            inputs=inputs,
            ignore_trigger=ignore_trigger,
            context=context)

    @submit_to_self
    def run_flow(
            self,
            flow,
            state,
            task_states,
            start_tasks,
            inputs,
            context,
            task_contexts=None,
            flow_is_serialized=True,
            return_all_task_states=False):
        if flow_is_serialized:
            flow = prefect.Flow.deserialize(flow)
        flow_runner = prefect.engine.FlowRunner(flow=flow, executor=self)
        return flow_runner.run(
            state=state,
            task_states=task_states,
            start_tasks=start_tasks,
            inputs=inputs,
            context=context,
            task_contexts=task_contexts,
            return_all_task_states=return_all_task_states)

import abc
from functools import wraps

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
        return self.submit(
            method_with_context,
            self,
            *args,
            _context=prefect.context.Context,
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
            executor_context,
            task,
            state,
            upstream_states,
            inputs,
            context,
    ):
        task_runner = prefect.engine.TaskRunner(task=task, executor_context=executor_context)
        return task_runner.run(
            state=state,
            upstream_states=upstream_states,
            inputs=inputs,
            context=context)

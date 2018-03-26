from functools import wraps
from contextlib import contextmanager
import prefect
from prefect.engine.task_runner import TaskRunner
from prefect.utilities.json import Serializable


def run_in_executor(method):
    """
    Decorator for executor methods that automatically executes them in the
    Executor.

    When a decorated method is called, it and its arguments are automatically
    passed to the executor's submit() method. The Prefect context is also
    serialized and provided. The resulting future is returned.

    class MyExecutor(Executor):

        @run_in_executor
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
                _context=prefect.context.Context.to_dict(),
                **kwargs)

    return wrapper


class Executor(Serializable):
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
        yield self

    def submit(self, fn, *args, _client_kwargs=None, **kwargs):
        """
        Submit a function to the executor for execution. Returns a future.
        """
        raise NotImplementedError()

    def wait(self, futures, timeout=None):
        """
        Resolves futures to their values. Blocks until the future is complete.
        """
        raise NotImplementedError()

    def set_state(self, state, new_state, result=None):
        """
        Update a state object with a new state and optional result.

        This method must update the passed state object, even if it performs
        other asynchronous operations.
        """
        state.set_state(new_state, result=result)

    @run_in_executor
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

    def run_flow(
            self,
            flow,
            state,
            task_states,
            start_tasks,
            context,
            parameters=None,
            task_contexts=None,
            flow_is_serialized=True,
            return_all_task_states=False):

        def run_flow_in_executor(
                flow,
                state,
                task_states,
                start_tasks,
                context,
                parameters,
                task_contexts,
                flow_is_serialized,
                return_all_task_states,
        ):
            if flow_is_serialized:
                flow = prefect.Flow.deserialize(flow)
            flow_runner = prefect.engine.FlowRunner(flow=flow, executor=self)
            return flow_runner.run(
                state=state,
                task_states=task_states,
                start_tasks=start_tasks,
                context=context,
                parameters=parameters,
                task_contexts=task_contexts,
                return_all_task_states=return_all_task_states)

        self.submit(
            run_flow_in_executor,
            flow=flow,
            state=state,
            task_states=task_states,
            start_tasks=start_tasks,
            context=context,
            parameters=parameters,
            task_contexts=task_contexts,
            flow_is_serialized=flow_is_serialized,
            return_all_task_states=return_all_task_states,
        )

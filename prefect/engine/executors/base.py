import datetime
from contextlib import contextmanager
from functools import wraps
from typing import Any, Dict, Iterable, TypeVar, Union, Callable, List

import prefect
from prefect.core import Flow, Task
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.state import State
from prefect.engine.task_runner import TaskRunner
from prefect.utilities.json import Serializable

Future = TypeVar("Future")


class Executor(Serializable):
    def __init__(self):
        pass

    @contextmanager
    def start(self):
        """
        This method is called
        """
        yield self

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        """
        Submit a function to the executor for execution. Returns a future.
        """
        raise NotImplementedError()

    def submit_with_context(
        self, fn: Callable, *args: Any, context: Dict, **kwargs: Any
    ) -> Future:
        """
        Submit a function to the executor that will be run in a specific Prefect context.

        Returns a Future.
        """

        def run_fn_in_context(*args, context, **kwargs):
            with prefect.context(context):
                return fn(*args, **kwargs)

        return self.submit(run_fn_in_context, *args, context=context, **kwargs)

    def wait(self, futures: List[Future], timeout: datetime.timedelta = None) -> Any:
        """
        Resolves futures to their values. Blocks until the future is complete.
        """
        raise NotImplementedError()

    def run_flow(
        self,
        flow: Flow,
        state: State,
        task_states: Dict[Task, State],
        start_tasks: Iterable[Task],
        return_tasks: Iterable[Task],
        parameters: Dict,
        context: Dict,
    ) -> Future:
        context = context or {}
        context.update(prefect.context)
        flow_runner = FlowRunner(flow=flow)

        return self.submit_with_context(
            flow_runner.run,
            state=state,
            task_states=task_states,
            start_tasks=start_tasks,
            return_tasks=return_tasks,
            parameters=parameters,
            executor=self,
            context=context,
        )

    def run_task(
        self,
        task: Task,
        state: State,
        upstream_states: Dict[Task, State],
        inputs: Dict[str, Any],
        ignore_trigger: bool = False,
        context: Dict[str, Any] = None,
    ) -> Future:
        context = context or {}
        context.update(prefect.context, _executor=self)
        task_runner = prefect.engine.TaskRunner(task=task)

        return self.submit_with_context(
            task_runner.run,
            state=state,
            upstream_states=upstream_states,
            inputs=inputs,
            ignore_trigger=ignore_trigger,
            context=context
        )

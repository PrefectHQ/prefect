import functools
import logging
import warnings
from collections import defaultdict
from contextlib import contextmanager
from importlib import import_module
from typing import Any, Callable, Dict, Iterable, Iterator, List, Union

import prefect
from prefect.core import Flow, Task
from prefect.engine import executors
from prefect.engine import signals
from prefect.engine.state import Failed, Pending, Running, State, Success
from prefect.engine.task_runner import TaskRunner


try:
    cfg_exec = prefect.config.flows.executor
    *module, cls_name = cfg_exec.split(".")
    module = import_module(".".join(module))
    DEFAULT_EXECUTOR = getattr(module, cls_name)
except:
    warnings.warn(
        f"Could not import {prefect.config.flows.executor}, using prefect.engine.executors.LocalExecutor instead."
    )
    DEFAULT_EXECUTOR = executors.LocalExecutor


def handle_signals(method: Callable[..., State]) -> Callable[..., State]:
    """
    This handler is used to decorate methods that return States but might raise
    Prefect signals.

    The handler attempts to run the method, and if a signal is raised, the appropriate
    state is returned.

    If DONTRUN is raised, the handler does not trap it, but re-raises it.
    """

    @functools.wraps(method)
    def inner(*args: Any, **kwargs: Any) -> State:

        raise_on_exception = prefect.context.get("_raise_on_exception", False)

        try:
            return method(*args, **kwargs)

        # DONTRUN signals get raised for handling
        except signals.DONTRUN as exc:
            logging.debug("DONTRUN signal raised: {}".format(exc))
            raise

        # FAIL signals are trapped and turned into Failed states
        except signals.FAIL as exc:
            logging.debug("{} signal raised.".format(type(exc).__name__))
            if raise_on_exception:
                raise exc
            return exc.state

        # All other exceptions (including other signals) are trapped
        # and turned into Failed states
        except Exception as exc:
            logging.debug("Unexpected error while running task.")
            if raise_on_exception:
                raise exc
            return Failed(message=exc)

    return inner


class FlowRunner:
    def __init__(
        self, flow: Flow, task_runner_cls=None, logger_name: str = None
    ) -> None:
        self.flow = flow
        self.task_runner_cls = task_runner_cls or TaskRunner
        self.logger = logging.getLogger(logger_name or type(self).__name__)

    def run(
        self,
        state: State = None,
        task_states: Dict[Task, State] = None,
        start_tasks: Iterable[Task] = None,
        return_tasks: Iterable[Task] = None,
        parameters: Dict[str, Any] = None,
        executor: "prefect.engine.executors.Executor" = None,
        context: Dict[str, Any] = None,
        task_contexts: Dict[Task, Dict[str, Any]] = None,
    ) -> State:

        state = state or Pending()
        context = context or {}
        return_tasks = return_tasks or []
        if set(return_tasks).difference(self.flow.tasks):
            raise ValueError("Some tasks in return_tasks were not found in the flow.")

        context.update(
            _flow_name=self.flow.name,
            _flow_version=self.flow.version,
            _parameters=parameters,
        )

        try:
            with prefect.context(context):
                state = self.get_pre_run_state(state=state)
                state = self.get_run_state(
                    state=state,
                    task_states=task_states,
                    start_tasks=start_tasks,
                    return_tasks=return_tasks,
                    executor=executor,
                    task_contexts=task_contexts,
                )

        except signals.DONTRUN:
            pass
        return state

    @handle_signals
    def get_pre_run_state(self, state: State) -> State:

        # ---------------------------------------------
        # Check for required parameters
        # ---------------------------------------------

        parameters = prefect.context.get("_parameters", {})
        required_parameters = self.flow.parameters(only_required=True)
        # when required_parameters is an empty dict, the following line will
        # run correctly under Python 3.6+ no matter what parameters is.
        # the extra "or {}" is just a safeguard against this subtle behavior change
        missing = set(required_parameters).difference(parameters or {})
        if missing:
            raise signals.FAIL(
                "Required parameters were not provided: {}".format(missing)
            )

        # ---------------------------------------------
        # Check if the flow run is ready to run
        # ---------------------------------------------

        # the flow run is already finished
        if state.is_finished():
            raise signals.DONTRUN("Flow run has already finished.")

        # the flow run must be either pending or running (possibly redundant with above)
        elif not (state.is_pending() or state.is_running()):
            raise signals.DONTRUN("Flow is not ready to run.")

        # ---------------------------------------------
        # Start!
        # ---------------------------------------------
        return Running()

    @handle_signals
    def get_run_state(
        self,
        state: State,
        task_states: Dict[Task, State] = None,
        start_tasks: Iterable[Task] = None,
        return_tasks: Iterable[Task] = None,
        task_contexts: Dict[Task, Dict[str, Any]] = None,
        executor: "prefect.engine.executors.base.Executor" = None,
    ) -> State:

        task_states = defaultdict(
            lambda: Failed(message="Task state not available."), task_states or {}
        )
        start_tasks = start_tasks or []
        return_tasks = return_tasks or []
        task_contexts = task_contexts or {}
        executor = executor or DEFAULT_EXECUTOR()

        if not state.is_running():
            raise signals.DONTRUN("Flow is not in a Running state.")

        # -- process each task in order

        with executor.start():

            for task in self.flow.sorted_tasks(root_tasks=start_tasks):

                upstream_states = {}
                upstream_inputs = {}

                # -- process each edge to the task
                for edge in self.flow.edges_to(task):

                    # upstream states to pass to the task trigger
                    upstream_states[edge.upstream_task] = task_states[
                        edge.upstream_task
                    ]

                    # extract data from upstream states that pass data
                    # note this will extract data even if the upstream state wasn't successful
                    if edge.key:
                        upstream_inputs[edge.key] = executor.submit(
                            lambda s: s.result, task_states[edge.upstream_task]
                        )

                if task in start_tasks and task in task_states:
                    upstream_inputs.update(task_states[task].cached_inputs)

                # -- run the task
                task_runner = self.task_runner_cls(task=task)
                task_states[task] = executor.submit(
                    task_runner.run,
                    state=task_states.get(task),
                    upstream_states=upstream_states,
                    inputs=upstream_inputs,
                    ignore_trigger=(task in start_tasks),
                    context=task_contexts.get(task),
                )

            # ---------------------------------------------
            # Collect results
            # ---------------------------------------------

            terminal_states = executor.wait(
                {task_states[t] for t in self.flow.terminal_tasks()}
            )
            return_states = executor.wait({t: task_states[t] for t in return_tasks})

            if any(s.is_failed() for s in terminal_states):
                self.logger.info("Flow run FAILED: some terminal tasks failed.")
                state = Failed(
                    message="Some terminal tasks failed.", result=return_states
                )

            elif all(s.is_successful() for s in terminal_states):
                self.logger.info("Flow run SUCCESS: all terminal tasks succeeded")
                state = Success(
                    message="All terminal tasks succeeded.", result=return_states
                )

            else:
                self.logger.info("Flow run PENDING: terminal tasks are incomplete.")
                state = Pending(
                    message="Some terminal tasks are still pending.",
                    result=return_states,
                )

            return state

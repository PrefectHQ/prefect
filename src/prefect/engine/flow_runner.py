
# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import functools
import logging
import warnings
from collections import defaultdict
from contextlib import contextmanager
from importlib import import_module
from typing import Any, Callable, Dict, Iterable, Iterator, List, Union

import prefect
from prefect.core import Flow, Task
from prefect.engine import signals
from prefect.engine.executors import DEFAULT_EXECUTOR
from prefect.engine.state import Failed, Pending, Running, State, Success
from prefect.engine.task_runner import TaskRunner
from prefect.utilities.collections import flatten_seq


def handle_signals(method: Callable[..., State]) -> Callable[..., State]:
    """
    This handler is used to decorate methods that return States but might raise
    Prefect signals.

    The handler attempts to run the method, and if a signal is raised, the appropriate
    state is returned.

    If `DONTRUN` is raised, the handler does not trap it, but re-raises it.
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
    """
    FlowRunners handle the execution of Flows and determine the State of a Flow
    before, during and after the Flow is run.

    In particular, through the FlowRunner you can specify which tasks should be
    the first tasks to run, which tasks should be returned after the Flow is finished,
    and what states each task should be initialized with.

    Args:
        - flow (Flow): the `Flow` to be run
        - task_runner_cls (TaskRunner, optional): The class used for running
            individual Tasks. Defaults to [TaskRunner](task_runner.html)
        - logger_name (str): Optional. The name of the logger to use when
            logging. Defaults to the name of the class.

    Note: new FlowRunners are initialized within the call to `Flow.run()` and in general,
    this is the endpoint through which FlowRunners will be interacted with most frequently.

    Example:
    ```python
    @task
    def say_hello():
        print('hello')

    with Flow() as f:
        say_hello()

    fr = FlowRunner(flow=f)
    flow_state = fr.run()
    ```
    """

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
        throttle: Dict[str, int] = None,
    ) -> State:
        """
        The main endpoint for FlowRunners.  Calling this method will perform all
        computations contained within the Flow and return the final state of the Flow.

        Args:
            - state (State, optional): starting state for the Flow. Defaults to
                `Pending`
            - task_states (dict, optional): dictionary of task states to begin
                computation with, with keys being Tasks and values their corresponding state
            - start_tasks ([Task], optional): list of Tasks to begin computation
                from; if any `start_tasks` have upstream dependencies, their states may need to be provided as well.
                Defaults to `self.flow.root_tasks()`
            - return_tasks ([Task], optional): list of Tasks to include in the
                final returned Flow state. Defaults to `None`
            - parameters (dict, optional): dictionary of any needed Parameter
                values, with keys being strings representing Parameter names and values being their corresponding values
            - executor (Executor, optional): executor to use when performing
                computation; defaults to the executor provided in your prefect configuration
            - context (dict, optional): prefect.Context to use for execution
            - task_contexts (dict, optional): dictionary of individual contexts
                to use for each Task run
            - throttle (dict, optional): dictionary of tags -> int specifying
                how many tasks with a given tag should be allowed to run simultaneously. Used
                for throttling resource usage.

        Returns:
            - State: `State` representing the final post-run state of the `Flow`.
        """
        state = state or Pending()
        context = context or {}
        return_tasks = return_tasks or []
        executor = executor or DEFAULT_EXECUTOR
        throttle = throttle or self.flow.throttle

        if set(return_tasks).difference(self.flow.tasks):
            raise ValueError("Some tasks in return_tasks were not found in the flow.")

        context.update(
            _flow_name=self.flow.name,
            _flow_version=self.flow.version,
            _parameters=parameters,
            _executor=executor,
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
                    throttle=throttle,
                )

        except signals.DONTRUN:
            pass
        return state

    @handle_signals
    def get_pre_run_state(self, state: State) -> State:

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
        task_states: Dict[Task, State],
        start_tasks: Iterable[Task],
        return_tasks: Iterable[Task],
        task_contexts: Dict[Task, Dict[str, Any]],
        executor: "prefect.engine.executors.base.Executor",
        throttle: Dict[str, int] = None,
    ) -> State:

        task_states = defaultdict(
            lambda: Failed(message="Task state not available."), task_states or {}
        )
        start_tasks = start_tasks or []
        return_tasks = set(return_tasks or [])
        sorted_return_tasks = []
        task_contexts = task_contexts or {}
        throttle = throttle or {}

        if not state.is_running():
            raise signals.DONTRUN("Flow is not in a Running state.")

        # -- process each task in order

        with executor.start():

            queues = {}
            for tag, size in throttle.items():
                q = executor.queue(size)
                for i in range(size):
                    q.put(i)  # populate the queue with resource "tickets"
                queues[tag] = q

            for task in self.flow.sorted_tasks(root_tasks=start_tasks):

                if task in return_tasks:
                    sorted_return_tasks.append(task)

                upstream_states = {}
                task_inputs = {}
                maps = dict()

                # -- process each edge to the task
                for edge in self.flow.edges_to(task):

                    if edge.mapped:
                        if edge.key is None:
                                maps.setdefault(None, []).append(task_states[edge.upstream_task])
                        else:
                            maps[edge.key] = task_states[edge.upstream_task]

                    # upstream states to pass to the task trigger
                    if edge.key is None:
                        upstream_states.setdefault(None, []).append(
                            task_states[edge.upstream_task]
                        )
                    else:
                        upstream_states[edge.key] = task_states[edge.upstream_task]

                if task in start_tasks and task in task_states:
                    task_inputs.update(task_states[task].cached_inputs)

                # -- run the task
                task_runner = self.task_runner_cls(task=task)
                task_states[task] = executor.submit(
                    task_runner.run,
                    state=task_states.get(task),
                    upstream_states=upstream_states,
                    inputs=task_inputs,
                    ignore_trigger=(task in start_tasks),
                    context=task_contexts.get(task),
                    queues=[
                        queues.get(tag) for tag in sorted(task.tags) if queues.get(tag)
                    ],
                    maps=maps,
                )
            # ---------------------------------------------
            # Collect results
            # ---------------------------------------------

            # terminal tasks determine if the flow is finished
            terminal_tasks = self.flow.terminal_tasks()
            # reference tasks determine flow state
            reference_tasks = self.flow.reference_tasks()

            final_states = executor.wait(
                {
                    t: task_states[t]
                    for t in terminal_tasks.union(reference_tasks).union(return_tasks)
                }
            )
            terminal_states = set(flatten_seq([final_states[t] for t in terminal_tasks]))
            key_states = set(flatten_seq([final_states[t] for t in reference_tasks]))
            return_states = {t: final_states[t] for t in sorted_return_tasks}

            # check that the flow is finished
            if not all(s.is_finished() for s in terminal_states):
                self.logger.info("Flow run PENDING: terminal tasks are incomplete.")
                state = Pending(
                    message="Some terminal tasks are still pending.",
                    result=return_states,
                )

            # check if any key task failed
            elif any(s.is_failed() for s in key_states):
                self.logger.info("Flow run FAILED: some reference tasks failed.")
                state = Failed(
                    message="Some reference tasks failed.", result=return_states
                )

            # check if all reference tasks succeeded
            elif all(s.is_successful() for s in key_states):
                self.logger.info("Flow run SUCCESS: all reference tasks succeeded")
                state = Success(
                    message="All reference tasks succeeded.", result=return_states
                )

            # check for any unanticipated state that is finished but neither success nor failed
            else:
                self.logger.info("Flow run SUCCESS: no reference tasks failed")
                state = Success(
                    message="No reference tasks failed.", result=return_states
                )

            return state

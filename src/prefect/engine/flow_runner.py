# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import functools
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, Set, Union, Tuple, Optional

import prefect
from prefect import config
from prefect.client import Client
from prefect.core import Edge, Flow, Task
from prefect.engine import signals
from prefect.engine.executors import DEFAULT_EXECUTOR
from prefect.engine.runner import ENDRUN, Runner, call_state_handlers
from prefect.engine.state import (
    Failed,
    Mapped,
    Pending,
    Retrying,
    Running,
    State,
    Success,
)
from prefect.engine.task_runner import TaskRunner
from prefect.utilities.collections import flatten_seq
from prefect.utilities.executors import run_with_heartbeat


class FlowRunner(Runner):
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
        - state_handlers (Iterable[Callable], optional): A list of state change handlers
            that will be called whenever the flow changes state, providing an
            opportunity to inspect or modify the new state. The handler
            will be passed the flow runner instance, the old (prior) state, and the new
            (current) state, with the following signature:

            ```
                state_handler(
                    flow_runner: FlowRunner,
                    old_state: State,
                    new_state: State) -> State
            ```

            If multiple functions are passed, then the `new_state` argument will be the
            result of the previous handler.

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
        self,
        flow: Flow,
        task_runner_cls: type = None,
        state_handlers: Iterable[Callable] = None,
    ) -> None:
        self.flow = flow
        self.task_runner_cls = task_runner_cls or TaskRunner
        self.client = Client()
        super().__init__(state_handlers=state_handlers)

    def _heartbeat(self) -> None:
        flow_run_id = prefect.context.get("_flow_run_id")
        self.client.update_flow_run_heartbeat(flow_run_id)

    def call_runner_target_handlers(self, old_state: State, new_state: State) -> State:
        """
        A special state handler that the FlowRunner uses to call its flow's state handlers.
        This method is called as part of the base Runner's `handle_state_change()` method.

        Args:
            - old_state (State): the old (previous) state
            - new_state (State): the new (current) state

        Returns:
            - State: the new state
        """
        for handler in self.flow.state_handlers:
            new_state = handler(self.flow, old_state, new_state)

        # Set state if in prefect cloud
        if config.get("prefect_cloud", None):
            flow_run_id = prefect.context.get("flow_run_id", None)
            version = prefect.context.get("_flow_run_version")

            res = self.client.set_flow_run_state(
                flow_run_id=flow_run_id,
                version=version,
                state=new_state,
                result_handler=self.flow.result_handler,
            )
            prefect.context.update(_flow_run_version=res.version)  # type: ignore

        return new_state

    def initialize_run(
        self,
        state: Optional[State],
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Tuple[State, Dict[str, Any], Dict[str, Any]]:
        """
        Initializes the Flow run by initializing state, parameters and context appropriately.

        Args:
            - state (State): the proposed initial state of the flow run; can be `None`
            - parameters (dict): the proposed initial parameters for the flow run
            - context (dict): the context to be updated with relevant information

        Returns:
            - tuple: a tuple of the updated state, parameters and context objects
        """
        db_state = None
        if config.get("prefect_cloud", None):
            flow_run_info = self.client.get_flow_run_info(
                flow_run_id=prefect.context.get("flow_run_id", ""),
                result_handler=self.flow.result_handler,
            )
            context.update(_flow_run_version=flow_run_info.version)  # type: ignore
            db_state = flow_run_info.state  # type: ignore

            ## update parameters, prioritizing kwarg-provided params
            db_parameters = flow_run_info.parameters or {}  # type: ignore
            for key, value in db_parameters:  # type: ignore
                if key not in parameters:
                    parameters[key] = value

        state = state or db_state or Pending()  # needs to remain below cloud check
        context.update(_flow_name=self.flow.name, _parameters=parameters)
        return state, parameters, context

    def run(
        self,
        state: State = None,
        task_states: Dict[Task, State] = None,
        start_tasks: Iterable[Task] = None,
        return_tasks: Iterable[Task] = None,
        return_failed: bool = False,
        parameters: Dict[str, Any] = None,
        executor: "prefect.engine.executors.Executor" = None,
        context: Dict[str, Any] = None,
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
            - return_failed (bool, optional): whether to return all tasks
                which fail, regardless of whether they are terminal tasks or in `return_tasks`.
                Defaults to `False`
            - parameters (dict, optional): dictionary of any needed Parameter
                values, with keys being strings representing Parameter names and values being their corresponding values
            - executor (Executor, optional): executor to use when performing
                computation; defaults to the executor specified in your prefect configuration
            - context (dict, optional): prefect.Context to use for execution
                to use for each Task run
            - throttle (dict, optional): dictionary of tags -> int specifying
                how many tasks with a given tag should be allowed to run simultaneously. Used
                for throttling resource usage.

        Returns:
            - State: `State` representing the final post-run state of the `Flow`.

        Raises:
            - ValueError: if any throttle values are `<= 0`
        """

        self.logger.info("Beginning Flow run for '{}'".format(self.flow.name))
        context = context or {}
        return_tasks = set(return_tasks or [])
        executor = executor or DEFAULT_EXECUTOR
        parameters = parameters or {}
        throttle = throttle or self.flow.throttle
        if min(throttle.values(), default=1) <= 0:
            bad_tags = ", ".join(
                ['"' + tag + '"' for tag, num in throttle.items() if num <= 0]
            )
            raise ValueError(
                "Cannot throttle tags {0} - an invalid value less than 1 was provided.".format(
                    bad_tags
                )
            )

        state, parameters, context = self.initialize_run(state, parameters, context)

        if return_tasks.difference(self.flow.tasks):
            raise ValueError("Some tasks in return_tasks were not found in the flow.")

        with prefect.context(context):

            raise_on_exception = prefect.context.get("_raise_on_exception", False)

            try:
                state = self.check_flow_is_pending_or_running(state)
                state = self.set_flow_to_running(state)
                state = self.get_flow_run_state(
                    state,
                    task_states=task_states,
                    start_tasks=start_tasks,
                    return_tasks=return_tasks,
                    return_failed=return_failed,
                    executor=executor,
                    throttle=throttle,
                )

            except ENDRUN as exc:
                state = exc.state

            # All other exceptions are trapped and turned into Failed states
            except Exception as exc:
                self.logger.debug("Unexpected error while running task.")
                if raise_on_exception:
                    raise exc
                return Failed(
                    message="Unexpected error while running task.", result=exc
                )

            return state

    @call_state_handlers
    def check_flow_is_pending_or_running(self, state: State) -> State:
        """
        Checks if the flow is in either a Pending state or Running state. Either are valid
        starting points (because we allow simultaneous runs of the same flow run).

        Args:
            - state (State): the current state of this flow

        Returns:
            - State: the state of the flow after running the check

        Raises:
            - ENDRUN: if the flow is not pending or running
        """

        # the flow run is already finished
        if state.is_finished() is True:
            self.logger.debug("Flow run has already finished.")
            raise ENDRUN(state)

        # the flow run must be either pending or running (possibly redundant with above)
        elif not (state.is_pending() or state.is_running()):
            self.logger.debug("Flow is not ready to run.")
            raise ENDRUN(state)

        return state

    @call_state_handlers
    def set_flow_to_running(self, state: State) -> State:
        """
        Puts Pending flows in a Running state; leaves Running flows Running.

        Args:
            - state (State): the current state of this flow

        Returns:
            - State: the state of the flow after running the check

        Raises:
            - ENDRUN: if the flow is not pending or running
        """
        if state.is_pending():
            self.logger.debug("Starting flow run.")
            return Running(message="Running flow.")
        elif state.is_running():
            return state
        else:
            raise ENDRUN(state)

    @run_with_heartbeat
    @call_state_handlers
    def get_flow_run_state(
        self,
        state: State,
        task_states: Dict[Task, State],
        start_tasks: Iterable[Task],
        return_tasks: Set[Task],
        executor: "prefect.engine.executors.base.Executor",
        return_failed: bool = False,
        throttle: Dict[str, int] = None,
    ) -> State:
        """
        Runs the flow.

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
            - executor (Executor, optional): executor to use when performing
                computation; defaults to the executor provided in your prefect configuration
            - return_failed (bool, optional): whether to return all tasks
                which fail, regardless of whether they are terminal tasks or in `return_tasks`.
                Defaults to `False`
            - throttle (dict, optional): dictionary of tags -> int specifying
                how many tasks with a given tag should be allowed to run simultaneously. Used
                for throttling resource usage.

        Returns:
            - State: `State` representing the final post-run state of the `Flow`.

        Raises:
            - ValueError: if any throttle values are `<= 0`
        """

        if not state.is_running():
            self.logger.debug("Flow is not in a Running state.")
            raise ENDRUN(state)

        task_states = defaultdict(
            lambda: Failed(message="Task state not available."), task_states or {}
        )
        start_tasks = start_tasks or []
        return_tasks = set(return_tasks or [])
        throttle = throttle or {}

        # this set keeps track of any tasks that are mapped over - meaning they are the
        # downstream task of at least one mapped edge
        mapped_tasks = set()

        # -- process each task in order

        with executor.start():

            queues = {}
            for tag, size in throttle.items():
                q = executor.queue(size)
                for i in range(size):
                    q.put(i)  # populate the queue with resource "tickets"
                queues[tag] = q

            for task in self.flow.sorted_tasks(root_tasks=start_tasks):

                upstream_states = {}  # type: Dict[Edge, Union[State, Iterable]]
                task_inputs = {}  # type: Dict[str, Any]

                # -- process each edge to the task
                for edge in self.flow.edges_to(task):
                    upstream_states[edge] = task_states[edge.upstream_task]
                    if edge.mapped:
                        mapped_tasks.add(task)

                # if a task is provided as a start_task and its state is also
                # provided, we assume that means it requires cached_inputs
                if task in start_tasks and task in task_states:
                    passed_state = task_states[task]
                    if not isinstance(passed_state, list):
                        assert isinstance(passed_state, Pending)  # mypy assertion
                        assert isinstance(
                            passed_state.cached_inputs, dict
                        )  # mypy assertion
                        task_inputs.update(passed_state.cached_inputs)

                # -- run the task
                task_runner = self.task_runner_cls(
                    task=task, result_handler=self.flow.result_handler
                )
                task_queues = [
                    queues.get(tag) for tag in sorted(task.tags) if queues.get(tag)
                ]

                if not task in mapped_tasks:
                    upstream_mapped = {
                        e: executor.wait(f)  # type: ignore
                        for e, f in upstream_states.items()
                        if e.upstream_task in mapped_tasks
                    }
                    upstream_states.update(upstream_mapped)

                task_states[task] = executor.submit(
                    task_runner.run,
                    state=task_states.get(task),
                    upstream_states=upstream_states,
                    inputs=task_inputs,
                    ignore_trigger=(task in start_tasks),
                    context=dict(prefect.context, task_id=task.id),
                    queues=task_queues,
                    mapped=task in mapped_tasks,
                    executor=executor,
                )

            # ---------------------------------------------
            # Collect results
            # ---------------------------------------------

            # terminal tasks determine if the flow is finished
            terminal_tasks = self.flow.terminal_tasks()

            # reference tasks determine flow state
            reference_tasks = self.flow.reference_tasks()

            if return_failed:
                final_states = executor.wait(dict(task_states))  # type: ignore
                assert isinstance(final_states, dict)
                failed_tasks = [
                    t
                    for t, state in final_states.items()
                    if (isinstance(state, (Failed, Retrying)))
                    or (
                        isinstance(state, list)
                        and any([isinstance(s, (Failed, Retrying)) for s in state])
                    )
                ]
                return_tasks.update(failed_tasks)
            else:
                final_states = executor.wait(  # type: ignore
                    {
                        t: task_states[t]
                        for t in terminal_tasks.union(reference_tasks).union(
                            return_tasks
                        )
                    }
                )
                assert isinstance(final_states, dict)

        terminal_states = set(flatten_seq([final_states[t] for t in terminal_tasks]))
        key_states = set(flatten_seq([final_states[t] for t in reference_tasks]))
        return_states = {t: final_states[t] for t in return_tasks}

        state = self.determine_final_state(key_states, return_states, terminal_states)
        return state

    def determine_final_state(
        self,
        key_states: Set[State],
        return_states: Dict[Task, State],
        terminal_states: Set[State],
    ) -> State:
        """
        Implements the logic for determining the final state of the flow run.

        Args:
            - key_states ():
            - return_states ():
            - terminal_states ():

        Returns:
            - State: the final state of the flow run
        """
        state = State()  # mypy initialization

        # check that the flow is finished
        if not all(s.is_finished() for s in terminal_states):
            self.logger.info("Flow run RUNNING: terminal tasks are incomplete.")
            state = Running(message="Flow run in progress.", result=return_states)

        # check if any key task failed
        elif any(s.is_failed() for s in key_states):
            self.logger.info("Flow run FAILED: some reference tasks failed.")
            state = Failed(message="Some reference tasks failed.", result=return_states)

        # check if all reference tasks succeeded
        elif all(s.is_successful() for s in key_states):
            self.logger.info("Flow run SUCCESS: all reference tasks succeeded")
            state = Success(
                message="All reference tasks succeeded.", result=return_states
            )

        # check for any unanticipated state that is finished but neither success nor failed
        else:
            self.logger.info("Flow run SUCCESS: no reference tasks failed")
            state = Success(message="No reference tasks failed.", result=return_states)

        return state

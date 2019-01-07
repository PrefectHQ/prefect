# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import functools
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, Union

import prefect
from prefect import config
from prefect.core import Edge, Flow, Task
from prefect.engine import signals
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
    ):
        self.flow = flow
        if task_runner_cls is None:
            task_runner_cls = prefect.engine.get_default_task_runner_class()
        self.task_runner_cls = task_runner_cls
        super().__init__(state_handlers=state_handlers)

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

        return new_state

    def initialize_run(  # type: ignore
        self,
        state: Optional[State],
        context: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Tuple[State, Dict[str, Any]]:
        """
        Initializes the Task run by initializing state and context appropriately.

        If the provided state is a Submitted state, the state it wraps is extracted.

        Args:
            - state (State): the proposed initial state of the flow run; can be `None`
            - context (dict): the context to be updated with relevant information
            - parameters(dict): the parameter values for the run

        Returns:
            - tuple: a tuple of the updated state and context objects
        """

        # overwrite context parameters one-by-one
        if parameters:
            context_params = context.setdefault("parameters", {})
            for param, value in parameters.items():
                context_params[param] = value

        context.update(flow_name=self.flow.name)
        return super().initialize_run(state=state, context=context)

    def run(
        self,
        state: State = None,
        task_states: Dict[Task, State] = None,
        start_tasks: Iterable[Task] = None,
        start_task_ids: Iterable[str] = None,
        return_tasks: Iterable[Task] = None,
        return_failed: bool = False,
        parameters: Dict[str, Any] = None,
        executor: "prefect.engine.executors.Executor" = None,
        context: Dict[str, Any] = None,
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
                from; if any `start_tasks` have upstream dependencies, their states may
                need to be provided as well.
            - start_task_ids ([str], optional): equivalent to `start_tasks`, but accepts
                a list of task IDs. The two options may be used simultaneously.
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

        Returns:
            - State: `State` representing the final post-run state of the `Flow`.

        """

        self.logger.info("Beginning Flow run for '{}'".format(self.flow.name))

        context = context or {}
        return_tasks = set(return_tasks or [])
        parameters = parameters or {}
        if executor is None:
            executor = prefect.engine.get_default_executor_class()()

        if return_tasks.difference(self.flow.tasks):
            raise ValueError("Some tasks in return_tasks were not found in the flow.")

        try:
            state, context = self.initialize_run(state, context, parameters)

            with prefect.context(context):

                raise_on_exception = prefect.context.get("raise_on_exception", False)

                state = self.check_flow_is_pending_or_running(state)
                state = self.set_flow_to_running(state)
                state = self.get_flow_run_state(
                    state,
                    task_states=task_states,
                    start_tasks=start_tasks,
                    start_task_ids=start_task_ids,
                    return_tasks=return_tasks,
                    return_failed=return_failed,
                    executor=executor,
                )

        except ENDRUN as exc:
            state = exc.state

        # All other exceptions are trapped and turned into Failed states
        except Exception as exc:
            self.logger.info("Unexpected error while running flow.")
            if raise_on_exception:
                raise exc
            return Failed(message="Unexpected error while running flow.", result=exc)

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
            self.logger.info("Flow run has already finished.")
            raise ENDRUN(state)

        # the flow run must be either pending or running (possibly redundant with above)
        elif not (state.is_pending() or state.is_running()):
            self.logger.info("Flow is not ready to run.")
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
            self.logger.info("Starting flow run.")
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
        start_task_ids: Iterable[str],
        return_tasks: Set[Task],
        executor: "prefect.engine.executors.base.Executor",
        return_failed: bool = False,
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
            - start_task_ids ([str], optional): equivalent to `start_tasks`, but accepts
                a list of task IDs. The two options may be used simultaneously.
            - return_tasks ([Task], optional): list of Tasks to include in the
                final returned Flow state. Defaults to `None`
            - executor (Executor, optional): executor to use when performing
                computation; defaults to the executor provided in your prefect configuration
            - return_failed (bool, optional): whether to return all tasks
                which fail, regardless of whether they are terminal tasks or in `return_tasks`.
                Defaults to `False`

        Returns:
            - State: `State` representing the final post-run state of the `Flow`.

        """

        if not state.is_running():
            self.logger.info("Flow is not in a Running state.")
            raise ENDRUN(state)

        # make a copy to avoid modifying the user-supplied task_states dict
        task_states = dict(task_states or {})
        return_tasks = set(return_tasks or [])
        start_tasks = list(start_tasks or [])
        if any(i not in self.flow.task_ids for i in start_task_ids or []):
            raise ValueError("Invalid start_task_ids.")
        start_tasks.extend(self.flow.task_ids[i] for i in start_task_ids or [])

        # -- process each task in order

        with executor.start():

            for task in self.flow.sorted_tasks(root_tasks=start_tasks):

                upstream_states = {}  # type: Dict[Edge, Union[State, Iterable]]
                task_inputs = {}  # type: Dict[str, Any]

                # -- process each edge to the task
                for edge in self.flow.edges_to(task):
                    upstream_states[edge] = task_states.get(
                        edge.upstream_task, Pending(message="Task state not available.")
                    )

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

                task_states[task] = executor.submit(
                    task_runner.run,
                    state=task_states.get(task),
                    upstream_states=upstream_states,
                    inputs=task_inputs,
                    # if the task is a "start task", don't check its upstream dependencies
                    check_upstream=(task not in start_tasks),
                    context=dict(prefect.context, task_id=task.id),
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
                final_states = executor.wait(task_states)
                all_final_states = final_states.copy()
                failed_tasks = []
                for t, s in final_states.items():
                    if isinstance(s, (Failed, Retrying)):
                        failed_tasks.append(t)
                    elif s.is_mapped():
                        s.map_states = executor.wait(s.map_states)
                        s.result = [ms.result for ms in s.map_states]
                        all_final_states[t] = s.map_states
                        if any(
                            [isinstance(r, (Failed, Retrying)) for r in s.map_states]
                        ):
                            failed_tasks.append(t)

                return_tasks.update(failed_tasks)
            else:
                # wait until all terminal tasks are finished
                final_tasks = terminal_tasks.union(reference_tasks).union(return_tasks)
                final_states = executor.wait(
                    {
                        t: task_states.get(
                            t, Pending("Task not evaluated by FlowRunner.")
                        )
                        for t in final_tasks
                    }
                )

                # also wait for any children of Mapped tasks to finish, and add them
                # to the dictionary to determine flow state
                all_final_states = final_states.copy()
                for t, s in list(final_states.items()):
                    if s.is_mapped():
                        s.map_states = executor.wait(s.map_states)
                        s.result = [ms.result for ms in s.map_states]
                        all_final_states[t] = s.map_states

                assert isinstance(final_states, dict)

        key_states = set(flatten_seq([all_final_states[t] for t in reference_tasks]))
        terminal_states = set(
            flatten_seq([all_final_states[t] for t in terminal_tasks])
        )
        return_states = {t: final_states[t] for t in return_tasks}

        state = self.determine_final_state(
            key_states=key_states,
            return_states=return_states,
            terminal_states=terminal_states,
        )

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
            - key_states (Set[State]): the states which will determine the success / failure of the flow run
            - return_states (Dict[Task, State]): states to return as results
            - terminal_states (Set[State]): the states of the terminal tasks for this flow

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

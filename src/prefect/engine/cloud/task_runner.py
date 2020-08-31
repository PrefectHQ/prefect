import datetime
import time
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

import pendulum

import prefect
from prefect.client import Client
from prefect.core import Edge, Task
from prefect.engine.result import Result
from prefect.engine.runner import ENDRUN, call_state_handlers
from prefect.engine.state import (
    Cached,
    ClientFailed,
    Failed,
    Queued,
    Retrying,
    State,
)
from prefect.engine.task_runner import TaskRunner, TaskRunnerInitializeResult
from prefect.utilities.exceptions import VersionLockError
from prefect.utilities.executors import tail_recursive
from prefect.utilities.graphql import with_args


class CloudTaskRunner(TaskRunner):
    """
    TaskRunners handle the execution of Tasks and determine the State of a Task
    before, during and after the Task is run.

    In particular, through the TaskRunner you can specify the states of any upstream dependencies,
    and what state the Task should be initialized with.

    Args:
        - task (Task): the Task to be run / executed
        - state_handlers (Iterable[Callable], optional): A list of state change handlers
            that will be called whenever the task changes state, providing an opportunity to
            inspect or modify the new state. The handler will be passed the task runner
            instance, the old (prior) state, and the new (current) state, with the following
            signature: `state_handler(TaskRunner, old_state, new_state) -> State`; If multiple
            functions are passed, then the `new_state` argument will be the result of the
            previous handler.
        - flow_result: the result instance configured for the flow (if any)
    """

    def __init__(
        self,
        task: Task,
        state_handlers: Iterable[Callable] = None,
        flow_result: Result = None,
    ) -> None:
        self.client = Client()
        super().__init__(
            task=task, state_handlers=state_handlers, flow_result=flow_result
        )

    def _heartbeat(self) -> bool:
        try:
            task_run_id = self.task_run_id  # type: str
            self.heartbeat_cmd = ["prefect", "heartbeat", "task-run", "-i", task_run_id]
            self.client.update_task_run_heartbeat(task_run_id)

            # use empty string for testing purposes
            flow_run_id = prefect.context.get("flow_run_id", "")  # type: str
            query = {
                "query": {
                    with_args("flow_run_by_pk", {"id": flow_run_id}): {
                        "flow": {"settings": True},
                    }
                }
            }
            flow_run = self.client.graphql(query).data.flow_run_by_pk
            if not flow_run.flow.settings.get("heartbeat_enabled", True):
                return False
            return True
        except Exception:
            self.logger.exception(
                "Heartbeat failed for Task '{}'".format(self.task.name)
            )
            return False

    def call_runner_target_handlers(self, old_state: State, new_state: State) -> State:
        """
        A special state handler that the TaskRunner uses to call its task's state handlers.
        This method is called as part of the base Runner's `handle_state_change()` method.

        Args:
            - old_state (State): the old (previous) state
            - new_state (State): the new (current) state

        Returns:
            - State: the new state
        """
        raise_on_exception = prefect.context.get("raise_on_exception", False)

        try:
            new_state = super().call_runner_target_handlers(
                old_state=old_state, new_state=new_state
            )
        except Exception as exc:
            msg = "Exception raised while calling state handlers: {}".format(repr(exc))
            self.logger.exception(msg)
            if raise_on_exception:
                raise exc
            new_state = Failed(msg, result=exc)

        task_run_id = prefect.context.get("task_run_id")
        version = prefect.context.get("task_run_version")

        try:
            cloud_state = new_state
            state = self.client.set_task_run_state(
                task_run_id=task_run_id,
                version=version if cloud_state.is_running() else None,
                state=cloud_state,
                cache_for=self.task.cache_for,
            )
        except VersionLockError:
            state = self.client.get_task_run_state(task_run_id=task_run_id)

            if state.is_running():
                self.logger.debug(
                    "Version lock encountered and task {} is already in a running state.".format(
                        self.task.name
                    )
                )
                raise ENDRUN(state=state)

            self.logger.debug(
                "Version lock encountered for task {}, proceeding with state {}...".format(
                    self.task.name, type(state).__name__
                )
            )

            try:
                new_state = state.load_result(self.result)
            except Exception as exc:
                self.logger.debug(
                    "Error encountered attempting to load result for state of {} task...".format(
                        self.task.name
                    )
                )
                self.logger.error(repr(exc))
                raise ENDRUN(state=state)
        except Exception as exc:
            self.logger.exception(
                "Failed to set task state with error: {}".format(repr(exc))
            )
            raise ENDRUN(state=ClientFailed(state=new_state))

        if state.is_queued():
            state.state = old_state  # type: ignore
            raise ENDRUN(state=state)

        prefect.context.update(task_run_version=(version or 0) + 1)

        return new_state

    def initialize_run(  # type: ignore
        self, state: Optional[State], context: Dict[str, Any]
    ) -> TaskRunnerInitializeResult:
        """
        Initializes the Task run by initializing state and context appropriately.

        Args:
            - state (Optional[State]): the initial state of the run
            - context (Dict[str, Any]): the context to be updated with relevant information

        Returns:
            - tuple: a tuple of the updated state, context, and upstream_states objects
        """

        # if the map_index is not None, this is a dynamic task and we need to load
        # task run info for it
        map_index = context.get("map_index")
        if map_index not in [-1, None]:
            try:
                task_run_info = self.client.get_task_run_info(
                    flow_run_id=context.get("flow_run_id", ""),
                    task_id=context.get("task_id", ""),
                    map_index=map_index,
                )

                # if state was provided, keep it; otherwise use the one from db
                state = state or task_run_info.state  # type: ignore
                context.update(
                    task_run_id=task_run_info.id,  # type: ignore
                    task_run_version=task_run_info.version,  # type: ignore
                )
            except Exception as exc:
                self.logger.exception(
                    "Failed to retrieve task state with error: {}".format(repr(exc))
                )
                if state is None:
                    state = Failed(
                        message="Could not retrieve state from Prefect Cloud",
                        result=exc,
                    )
                raise ENDRUN(state=state)

        # we assign this so it can be shared with heartbeat thread
        self.task_run_id = context.get("task_run_id", "")  # type: str
        context.update(checkpointing=True)

        return super().initialize_run(state=state, context=context)

    @call_state_handlers
    def check_task_is_cached(self, state: State, inputs: Dict[str, Result]) -> State:
        """
        Checks if task is cached in the DB and whether any of the caches are still valid.

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Result]): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the task is not ready to run
        """
        if state.is_cached() is True:
            assert isinstance(state, Cached)  # mypy assert
            sanitized_inputs = {key: res.value for key, res in inputs.items()}
            if self.task.cache_validator(
                state, sanitized_inputs, prefect.context.get("parameters")
            ):
                state = state.load_result(self.result)
                return state

        if self.task.cache_for is not None:
            oldest_valid_cache = datetime.datetime.utcnow() - self.task.cache_for
            cached_states = self.client.get_latest_cached_states(
                task_id=prefect.context.get("task_id", ""),
                cache_key=self.task.cache_key,
                created_after=oldest_valid_cache,
            )

            if cached_states:
                self.logger.debug(
                    "Task '{name}': {num} candidate cached states were found".format(
                        name=prefect.context.get("task_full_name", self.task.name),
                        num=len(cached_states),
                    )
                )

                for candidate_state in cached_states:
                    assert isinstance(candidate_state, Cached)  # mypy assert
                    candidate_state.load_cached_results(inputs)
                    sanitized_inputs = {key: res.value for key, res in inputs.items()}
                    if self.task.cache_validator(
                        candidate_state,
                        sanitized_inputs,
                        prefect.context.get("parameters"),
                    ):
                        return candidate_state.load_result(self.result)

                self.logger.debug(
                    "Task '{name}': can't use cache because no candidate Cached states "
                    "were valid".format(
                        name=prefect.context.get("task_full_name", self.task.name)
                    )
                )
            else:
                self.logger.debug(
                    "Task '{name}': can't use cache because no Cached states were found".format(
                        name=prefect.context.get("task_full_name", self.task.name)
                    )
                )

        return state

    def load_results(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> Tuple[State, Dict[Edge, State]]:
        """
        Given the task's current state and upstream states, populates all relevant result
        objects for this task run.

        Args:
            - state (State): the task's current state.
            - upstream_states (Dict[Edge, State]): the upstream state_handlers

        Returns:
            - Tuple[State, dict]: a tuple of (state, upstream_states)

        """
        upstream_results = {}

        try:
            if state.is_mapped():
                # ensures mapped children are only loaded once
                state = state.load_result(self.result)
            for edge, upstream_state in upstream_states.items():
                upstream_states[edge] = upstream_state.load_result(
                    edge.upstream_task.result or self.flow_result
                )
                if edge.key is not None:
                    upstream_results[edge.key] = (
                        edge.upstream_task.result or self.flow_result
                    )

            state.load_cached_results(upstream_results)
            return state, upstream_states
        except Exception as exc:
            new_state = Failed(
                message=f"Failed to retrieve task results: {exc}", result=exc
            )
            final_state = self.handle_state_change(old_state=state, new_state=new_state)
            raise ENDRUN(final_state)

    @tail_recursive
    def run(
        self,
        state: State = None,
        upstream_states: Dict[Edge, State] = None,
        context: Dict[str, Any] = None,
        is_mapped_parent: bool = False,
    ) -> State:
        """
        The main endpoint for TaskRunners.  Calling this method will conditionally execute
        `self.task.run` with any provided inputs, assuming the upstream dependencies are in a
        state which allow this Task to run.  Additionally, this method will wait and perform
        Task retries which are scheduled for <= 1 minute in the future.

        Args:
            - state (State, optional): initial `State` to begin task run from;
                defaults to `Pending()`
            - upstream_states (Dict[Edge, State]): a dictionary
                representing the states of any tasks upstream of this one. The keys of the
                dictionary should correspond to the edges leading to the task.
            - context (dict, optional): prefect Context to use for execution
            - is_mapped_parent (bool): a boolean indicating whether this task run is the run of
                a parent mapped task

        Returns:
            - `State` object representing the final post-run state of the Task
        """
        with prefect.context(context or {}):
            end_state = super().run(
                state=state,
                upstream_states=upstream_states,
                context=context,
                is_mapped_parent=is_mapped_parent,
            )
            while (end_state.is_retrying() or end_state.is_queued()) and (
                end_state.start_time <= pendulum.now("utc").add(minutes=10)  # type: ignore
            ):
                assert isinstance(end_state, (Retrying, Queued))
                naptime = max(
                    (end_state.start_time - pendulum.now("utc")).total_seconds(), 0
                )
                for _ in range(int(naptime) // 30):
                    # send heartbeat every 30 seconds to let API know task run is still alive
                    self.client.update_task_run_heartbeat(
                        task_run_id=prefect.context.get("task_run_id")
                    )
                    naptime -= 30
                    time.sleep(30)

                if naptime > 0:
                    time.sleep(naptime)  # ensures we don't start too early

                self.client.update_task_run_heartbeat(
                    task_run_id=prefect.context.get("task_run_id")
                )
                # mapped children will retrieve their latest info inside
                # initialize_run(), but we can load up-to-date versions
                # for all other task runs here
                if prefect.context.get("map_index") in [-1, None]:
                    task_run_info = self.client.get_task_run_info(
                        flow_run_id=prefect.context.get("flow_run_id"),
                        task_id=prefect.context.get("task_id"),
                        map_index=prefect.context.get("map_index"),
                    )

                    # if state was provided, keep it; otherwise use the one from db
                    context.update(task_run_version=task_run_info.version)  # type: ignore

                end_state = super().run(
                    state=end_state,
                    upstream_states=upstream_states,
                    context=context,
                    is_mapped_parent=is_mapped_parent,
                )

            return end_state

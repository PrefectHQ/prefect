import copy
import datetime
import threading
import time
import warnings
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, Type

import pendulum

import prefect
from prefect.client import Client
from prefect.core import Edge, Task
from prefect.utilities.executors import tail_recursive
from prefect.engine.cloud.utilities import prepare_state_for_cloud
from prefect.engine.result import NoResult, Result
from prefect.engine.result_handlers import ResultHandler
from prefect.engine.runner import ENDRUN, call_state_handlers
from prefect.engine.state import (
    Cached,
    Cancelled,
    ClientFailed,
    Failed,
    Mapped,
    Retrying,
    Queued,
    State,
)
from prefect.engine.task_runner import TaskRunner, TaskRunnerInitializeResult
from prefect.utilities.executors import PeriodicMonitoredCall
from prefect.utilities.graphql import with_args
from prefect.utilities.threads import ThreadEventLoop


class CloudTaskRunner(TaskRunner):
    """
    TaskRunners handle the execution of Tasks and determine the State of a Task
    before, during and after the Task is run.

    In particular, through the TaskRunner you can specify the states of any upstream dependencies,
    and what state the Task should be initialized with.

    Args:
        - task (Task): the Task to be run / executed
        - state_handlers (Iterable[Callable], optional): A list of state change handlers
            that will be called whenever the task changes state, providing an
            opportunity to inspect or modify the new state. The handler
            will be passed the task runner instance, the old (prior) state, and the new
            (current) state, with the following signature: `state_handler(TaskRunner, old_state, new_state) -> State`;
            If multiple functions are passed, then the `new_state` argument will be the
            result of the previous handler.
        - result_handler (ResultHandler, optional): the handler to use for
            retrieving and storing state results during execution (if the Task doesn't already have one);
            if not provided here or by the Task, will default to the one specified in your config
    """

    def __init__(
        self,
        task: Task,
        state_handlers: Iterable[Callable] = None,
        result_handler: ResultHandler = None,
    ) -> None:
        self.client = Client()
        self.state = None
        super().__init__(
            task=task, state_handlers=state_handlers, result_handler=result_handler
        )
        self.logger.info("CLOUD TASK RUNNER")

    def _heartbeat(self) -> bool:
        self.logger.info("HEARTBEAT")
        task_run_id = self.task_run_id  # type: ignore
        self.client.update_task_run_heartbeat(task_run_id)
        return True

    @tail_recursive
    def _run(
        self,
        manager,
        state: State = None,
        upstream_states: Dict[Edge, State] = None,
        context: Dict[str, Any] = None,
        executor: "prefect.engine.executors.Executor" = None,
    ) -> None:
        """
        The main endpoint for TaskRunners.  Calling this method will conditionally execute
        `self.task.run` with any provided inputs, assuming the upstream dependencies are in a
        state which allow this Task to run.  Additionally, this method will wait and perform Task retries
        which are scheduled for <= 1 minute in the future.

        Args:
            - state (State, optional): initial `State` to begin task run from;
                defaults to `Pending()`
            - upstream_states (Dict[Edge, State]): a dictionary
                representing the states of any tasks upstream of this one. The keys of the
                dictionary should correspond to the edges leading to the task.
            - context (dict, optional): prefect Context to use for execution
            - executor (Executor, optional): executor to use when performing
                computation; defaults to the executor specified in your prefect configuration

        Returns:
            - `State` object representing the final post-run state of the Task
        """

        try:
            context = context or {}

            if not state:
                task_run_info = self.client.get_task_run_info(
                    flow_run_id=context.get("flow_run_id", ""),
                    task_id=context.get("task_id", ""),
                    map_index=map_index,
                )
                state = task_run_info.state

            self.state = state

            self.state = super().run(
                state=state,
                upstream_states=upstream_states,
                context=context,
                executor=executor,
            )
            while (self.state.is_retrying() or self.state.is_queued()) and (
                self.state.start_time <= pendulum.now("utc").add(minutes=1)  # type: ignore
            ):
                assert isinstance(self.state, (Retrying, Queued))
                naptime = max(
                    (self.state.start_time - pendulum.now("utc")).total_seconds(), 0
                )
                time.sleep(naptime)

                # currently required as context has reset to its original state
                task_run_info = self.client.get_task_run_info(
                    flow_run_id=context.get("flow_run_id", ""),
                    task_id=context.get("task_id", ""),
                    map_index=context.get("map_index"),
                )
                context.update(task_run_version=task_run_info.version)  # type: ignore

                end_state = super().run(
                    state=self.state,
                    upstream_states=upstream_states,
                    context=context,
                    executor=executor,
                )
        except Exception:
            self.logger.exception("Error occured on run")

        self.logger.info("TaskRunner completed")

        manager.emit(event="exit")

    def check_valid_initial_state(self, flow_run_id: str) -> bool:
        state = self.fetch_current_flow_run_state(flow_run_id)
        return state != Cancelled

    def run(self, **kwargs: Any) -> State:
        manager = ThreadEventLoop(logger=self.logger)
        flow_run_id = prefect.context.get("flow_run_id", "")  # type: str

        if not self.check_valid_initial_state(flow_run_id):
            raise RuntimeError("Flow run initial state is invalid. It will not be run!")

        # start a state listener thread, pulling states for this flow run id from cloud.
        # Events are reported back to the main thread (here). Why a separate thread?
        # Among other reasons, when we start doing subscriptions later, it will continue
        # to work with little modification (replacing the periodic caller with a thread)
        state_thread = PeriodicMonitoredCall(
            interval=3,
            function=self.stream_flow_run_state_events,
            logger=self.logger,
            flow_run_id=flow_run_id,
            manager=manager,
        )
        manager.add_thread(state_thread, state_thread.cancel)

        # note: this creates a cloud flow runner which has a heartbeat
        worker_thread = threading.Thread(
            target=self._run, kwargs={"manager": manager, **kwargs}
        )
        manager.add_thread(worker_thread)

        manager.add_event_handler("state", self.on_state_event)

        manager.run()
        return self.state

    def on_state_event(self, manager, event, payload):
        self.logger.info("state event: {} {}".format(event, payload))
        if event == "state" and payload == Cancelled:
            manager.emit(event="exit")

    def fetch_current_flow_run_state(self, flow_run_id: str) -> Type[State]:
        query = {
            "query": {
                with_args("flow_run_by_pk", {"id": flow_run_id}): {
                    "state": True,
                    "flow": {"settings": True},
                }
            }
        }

        flow_run = self.client.graphql(query).data.flow_run_by_pk
        return State.parse(flow_run.state)

    # TODO: check task run states, not flow runs... or both?
    def stream_flow_run_state_events(self, manager, flow_run_id: str) -> None:
        self.logger.info("STREAM: {}".format(flow_run_id))
        state = self.fetch_current_flow_run_state(flow_run_id)
        self.logger.info("STREAM STATE: {}".format(state))

        # note: currently we are polling the latest known state. In the future when subscriptions are
        # available we can stream all state transistions, since we are guarenteed to have ordering
        # without duplicates. Until then, we will apply filtering of the states we want to see before
        # it hits the queue here instead of the main thread.

        if state == Cancelled:
            # TODO: better way to get manager queue
            manager.emit(event="state", payload=state)

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
            cloud_state = prepare_state_for_cloud(new_state)
            state = self.client.set_task_run_state(
                task_run_id=task_run_id,
                version=version,
                state=cloud_state,
                cache_for=self.task.cache_for,
            )
        except Exception as exc:
            self.logger.exception(
                "Failed to set task state with error: {}".format(repr(exc))
            )
            raise ENDRUN(state=ClientFailed(state=new_state))

        if state.is_queued():
            state.state = old_state  # type: ignore
            raise ENDRUN(state=state)

        if version is not None:
            prefect.context.update(task_run_version=version + 1)  # type: ignore

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
        self.task_run_id = context.get("task_run_id")  # type: ignore
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
        if self.task.cache_for is not None:
            oldest_valid_cache = datetime.datetime.utcnow() - self.task.cache_for
            cached_states = self.client.get_latest_cached_states(
                task_id=prefect.context.get("task_id", ""),
                cache_key=self.task.cache_key,
                created_after=oldest_valid_cache,
            )

            if not cached_states:
                self.logger.info(
                    "Task '{name}': can't use cache because no Cached states were found".format(
                        name=prefect.context.get("task_full_name", self.task.name)
                    )
                )
            else:
                self.logger.info(
                    "Task '{name}': {num} candidate cached states were found".format(
                        name=prefect.context.get("task_full_name", self.task.name),
                        num=len(cached_states),
                    )
                )

            for candidate_state in cached_states:
                assert isinstance(candidate_state, Cached)  # mypy assert
                candidate_state.cached_inputs = {
                    key: res.to_result(inputs[key].result_handler)  # type: ignore
                    for key, res in (candidate_state.cached_inputs or {}).items()
                }
                sanitized_inputs = {key: res.value for key, res in inputs.items()}
                if self.task.cache_validator(
                    candidate_state, sanitized_inputs, prefect.context.get("parameters")
                ):
                    candidate_state._result = candidate_state._result.to_result(
                        self.task.result_handler
                    )
                    return candidate_state

                self.logger.info(
                    "Task '{name}': can't use cache because no candidate Cached states "
                    "were valid".format(
                        name=prefect.context.get("task_full_name", self.task.name)
                    )
                )

        return state

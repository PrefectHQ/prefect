import collections
import threading
import queue
import warnings
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union, Type

import prefect
from prefect.client import Client
from prefect.core import Flow, Task
from prefect.engine.cloud import CloudTaskRunner
from prefect.engine.cloud.utilities import prepare_state_for_cloud
from prefect.engine.flow_runner import FlowRunner, FlowRunnerInitializeResult
from prefect.engine.runner import ENDRUN
from prefect.engine.state import Failed, State, Cancelled
from prefect.engine.executors.base import Executor
from prefect.utilities.executors import PeriodicMonitoredCall
from prefect.utilities.exceptions import ExecutorError
from prefect.utilities.graphql import with_args
from prefect.utilities.threads import ThreadEventLoop

QueueItem = collections.namedtuple("QueueItem", "event payload")


class CloudFlowRunner(FlowRunner):
    """
    FlowRunners handle the execution of Flows and determine the State of a Flow
    before, during and after the Flow is run.

    In particular, through the FlowRunner you can specify which tasks should be
    the first tasks to run, which tasks should be returned after the Flow is finished,
    and what states each task should be initialized with.

    Args:
        - flow (Flow): the `Flow` to be run
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

    with Flow("My Flow") as f:
        say_hello()

    fr = FlowRunner(flow=f)
    flow_state = fr.run()
    ```
    """

    def __init__(self, flow: Flow, state_handlers: Iterable[Callable] = None) -> None:
        self.client = Client()
        self.executor = None  # type: Optional[Executor]
        self.state = None  # type: Optional[State]
        super().__init__(
            flow=flow, task_runner_cls=CloudTaskRunner, state_handlers=state_handlers
        )

    def _heartbeat(self) -> bool:
        flow_run_id = prefect.context.get("flow_run_id", "")  # type: str
        self.client.update_flow_run_heartbeat(flow_run_id)
        return True

    def check_valid_initial_state(self, flow_run_id: str) -> bool:
        state = self.fetch_current_flow_run_state(flow_run_id)
        return state != Cancelled

    def cancel(self, wait: bool = True) -> List[Any]:
        self.logger.debug("Requested to cancel flow run")
        if self.executor:
            return self.executor.shutdown(wait=wait)
        raise RuntimeError("Flow is not running, thus cannot be cancelled")

    def _run(
        self,
        manager,
        executor: "prefect.engine.executors.Executor" = None,
        **kwargs: Any
    ) -> None:
        try:
            if executor is None:
                executor = prefect.engine.get_default_executor_class()()
            self.executor = executor

            self.state = super().run(executor=self.executor, **kwargs)
        except ExecutorError:
            if self.executor and self.executor.accepting_work:
                self.logger.exception("Executor error while still accepting work")
        except Exception:
            self.logger.exception("Error occured on run")

        self.logger.debug("FlowRunner completed")

        manager.emit(event="exit")

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
        self.logger.debug("state event: {} {}".format(event, payload))
        if event == "state" and payload == Cancelled:
            self.cancel()
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

    def stream_flow_run_state_events(self, manager, flow_run_id: str) -> None:
        state = self.fetch_current_flow_run_state(flow_run_id)

        # note: currently we are polling the latest known state. In the future when subscriptions are
        # available we can stream all state transistions, since we are guarenteed to have ordering
        # without duplicates. Until then, we will apply filtering of the states we want to see before
        # it hits the queue here instead of the main thread.

        if state == Cancelled:
            # TODO: better way to get manager queue
            manager.emit(event="state", payload=state)

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
        raise_on_exception = prefect.context.get("raise_on_exception", False)

        try:
            new_state = super().call_runner_target_handlers(
                old_state=old_state, new_state=new_state
            )
        except Exception as exc:
            msg = "Exception raised while calling state handlers: {}".format(repr(exc))
            self.logger.debug(msg)
            if raise_on_exception:
                raise exc
            new_state = Failed(msg, result=exc)

        flow_run_id = prefect.context.get("flow_run_id", None)
        version = prefect.context.get("flow_run_version")

        try:
            cloud_state = prepare_state_for_cloud(new_state)
            self.client.set_flow_run_state(
                flow_run_id=flow_run_id, version=version, state=cloud_state
            )
        except Exception as exc:
            self.logger.debug(
                "Failed to set flow state with error: {}".format(repr(exc))
            )
            raise ENDRUN(state=new_state)

        prefect.context.update(flow_run_version=version + 1)

        return new_state

    def initialize_run(  # type: ignore
        self,
        state: Optional[State],
        task_states: Dict[Task, State],
        context: Dict[str, Any],
        task_contexts: Dict[Task, Dict[str, Any]],
        parameters: Dict[str, Any],
    ) -> FlowRunnerInitializeResult:
        """
        Initializes the Task run by initializing state and context appropriately.

        If the provided state is a Submitted state, the state it wraps is extracted.

        Args:
            - state (Optional[State]): the initial state of the run
            - task_states (Dict[Task, State]): a dictionary of any initial task states
            - context (Dict[str, Any], optional): prefect.Context to use for execution
                to use for each Task run
            - task_contexts (Dict[Task, Dict[str, Any]], optional): contexts that will be provided to each task
            - parameters(dict): the parameter values for the run

        Returns:
            - NamedTuple: a tuple of initialized objects:
                `(state, task_states, context, task_contexts)`
        """

        # load id from context
        flow_run_id = prefect.context.get("flow_run_id")

        try:
            flow_run_info = self.client.get_flow_run_info(flow_run_id)
        except Exception as exc:
            self.logger.debug(
                "Failed to retrieve flow state with error: {}".format(repr(exc))
            )
            if state is None:
                state = Failed(
                    message="Could not retrieve state from Prefect Cloud", result=exc
                )
            raise ENDRUN(state=state)

        updated_context = context or {}
        updated_context.update(flow_run_info.context or {})
        updated_context.update(
            flow_id=flow_run_info.flow_id,
            flow_run_id=flow_run_info.id,
            flow_run_version=flow_run_info.version,
            flow_run_name=flow_run_info.name,
            scheduled_start_time=flow_run_info.scheduled_start_time,
        )

        tasks = {t.slug: t for t in self.flow.tasks}
        # update task states and contexts
        for task_run in flow_run_info.task_runs:
            task = tasks[task_run.task_slug]
            task_states.setdefault(task, task_run.state)
            task_contexts.setdefault(task, {}).update(
                task_id=task_run.task_id,
                task_run_id=task_run.id,
                task_run_version=task_run.version,
            )

        # if state is set, keep it; otherwise load from Cloud
        state = state or flow_run_info.state  # type: ignore

        # update parameters, prioritizing kwarg-provided params
        updated_parameters = flow_run_info.parameters or {}  # type: ignore
        updated_parameters.update(parameters)

        return super().initialize_run(
            state=state,
            task_states=task_states,
            context=updated_context,
            task_contexts=task_contexts,
            parameters=updated_parameters,
        )

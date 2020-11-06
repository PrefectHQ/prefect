import os
import signal
import threading
from time import sleep as time_sleep
from typing import Any, Callable, Dict, Iterable, Optional, Iterator
from contextlib import contextmanager

import pendulum

import prefect
from prefect.client import Client
from prefect.core import Flow, Task
from prefect.engine.cloud import CloudTaskRunner
from prefect.engine.flow_runner import FlowRunner, FlowRunnerInitializeResult
from prefect.engine.runner import ENDRUN
from prefect.engine.state import Failed, Queued, State, Cancelling, Cancelled
from prefect.utilities.exceptions import VersionLockError
from prefect.utilities.graphql import with_args


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
        super().__init__(
            flow=flow, task_runner_cls=CloudTaskRunner, state_handlers=state_handlers
        )

    def _heartbeat(self) -> bool:
        try:
            # use empty string for testing purposes
            flow_run_id = prefect.context.get("flow_run_id", "")  # type: str
            self.client.update_flow_run_heartbeat(flow_run_id)
            self.heartbeat_cmd = ["prefect", "heartbeat", "flow-run", "-i", flow_run_id]

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
                "Heartbeat failed for Flow '{}'".format(self.flow.name)
            )
            return False

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
            self.logger.exception(msg)
            if raise_on_exception:
                raise exc
            new_state = Failed(msg, result=exc)

        flow_run_id = prefect.context.get("flow_run_id", None)
        version = prefect.context.get("flow_run_version")

        try:
            cloud_state = new_state
            state = self.client.set_flow_run_state(
                flow_run_id=flow_run_id,
                version=version if cloud_state.is_running() else None,
                state=cloud_state,
            )
        except VersionLockError as exc:
            state = self.client.get_flow_run_state(flow_run_id=flow_run_id)

            if state.is_running():
                self.logger.debug(
                    "Version lock encountered and flow is already in a running state."
                )
                raise ENDRUN(state=state) from exc

            self.logger.debug(
                "Version lock encountered, proceeding with state {}...".format(
                    type(state).__name__
                )
            )
            new_state = state
        except Exception as exc:
            self.logger.exception(
                "Failed to set flow state with error: {}".format(repr(exc))
            )
            raise ENDRUN(state=new_state) from exc

        if state.is_queued():
            state.state = old_state  # type: ignore
            raise ENDRUN(state=state)

        prefect.context.update(flow_run_version=(version or 0) + 1)

        return new_state

    @contextmanager
    def check_for_cancellation(self) -> Iterator:
        """Contextmanager used to wrap a cancellable section of a flow run."""

        cancelling = False
        done = threading.Event()
        flow_run_version = None
        context = prefect.context.to_dict()

        def interrupt_if_cancelling() -> None:
            # We need to copy the context into this thread, since context is a
            # thread local.
            with prefect.context(context):
                flow_run_id = prefect.context["flow_run_id"]
                while True:
                    exiting_context = done.wait(
                        prefect.config.cloud.check_cancellation_interval
                    )
                    try:
                        self.logger.debug("Checking flow run state...")
                        flow_run_info = self.client.get_flow_run_info(flow_run_id)
                    except Exception:
                        self.logger.warning(
                            "Error getting flow run info", exc_info=True
                        )
                        continue
                    if not flow_run_info.state.is_running():
                        self.logger.warning(
                            "Flow run is no longer in a running state; the current state is: %r",
                            flow_run_info.state,
                        )
                    if isinstance(flow_run_info.state, Cancelling):
                        self.logger.info(
                            "Flow run has been cancelled, cancelling active tasks"
                        )
                        nonlocal cancelling
                        nonlocal flow_run_version
                        cancelling = True
                        flow_run_version = flow_run_info.version
                        # If not already leaving context, raise KeyboardInterrupt in the main thread
                        if not exiting_context:
                            if os.name == "nt":
                                # This doesn't actually send a signal, so it will only
                                # interrupt the next Python bytecode instruction - if the
                                # main thread is blocked in a c extension the interrupt
                                # won't be seen until that returns.
                                from _thread import interrupt_main

                                interrupt_main()
                            else:
                                signal.pthread_kill(
                                    threading.main_thread().ident, signal.SIGINT  # type: ignore
                                )
                        break
                    elif exiting_context:
                        break

        thread = threading.Thread(target=interrupt_if_cancelling, daemon=True)
        thread.start()
        try:
            yield
        except KeyboardInterrupt:
            if not cancelling:
                raise
        finally:
            done.set()
            thread.join()
            if cancelling:
                prefect.context.update(flow_run_version=flow_run_version)
                raise ENDRUN(state=Cancelled("Flow run is cancelled"))

    def run(
        self,
        state: State = None,
        task_states: Dict[Task, State] = None,
        return_tasks: Iterable[Task] = None,
        parameters: Dict[str, Any] = None,
        task_runner_state_handlers: Iterable[Callable] = None,
        executor: "prefect.engine.executors.Executor" = None,
        context: Dict[str, Any] = None,
        task_contexts: Dict[Task, Dict[str, Any]] = None,
    ) -> State:
        """
        The main endpoint for FlowRunners.  Calling this method will perform all
        computations contained within the Flow and return the final state of the Flow.

        Args:
            - state (State, optional): starting state for the Flow. Defaults to
                `Pending`
            - task_states (dict, optional): dictionary of task states to begin
                computation with, with keys being Tasks and values their corresponding state
            - return_tasks ([Task], optional): list of Tasks to include in the
                final returned Flow state. Defaults to `None`
            - parameters (dict, optional): dictionary of any needed Parameter
                values, with keys being strings representing Parameter names and values being
                their corresponding values
            - task_runner_state_handlers (Iterable[Callable], optional): A list of state change
                handlers that will be provided to the task_runner, and called whenever a task
                changes state.
            - executor (Executor, optional): executor to use when performing
                computation; defaults to the executor specified in your prefect configuration
            - context (Dict[str, Any], optional): prefect.Context to use for execution
                to use for each Task run
            - task_contexts (Dict[Task, Dict[str, Any]], optional): contexts that will be
                provided to each task

        Returns:
            - State: `State` representing the final post-run state of the `Flow`.
        """
        context = (context or {}).copy()
        context.update(running_with_backend=True)

        end_state = super().run(
            state=state,
            task_states=task_states,
            return_tasks=return_tasks,
            parameters=parameters,
            task_runner_state_handlers=task_runner_state_handlers,
            executor=executor,
            context=context,
            task_contexts=task_contexts,
        )
        # If start time is more than 10 minutes in the future,
        # we fail the run so Lazarus can pick it up and reschedule it.
        while end_state.is_queued() and (
            end_state.start_time <= pendulum.now("utc").add(minutes=10)  # type: ignore
        ):
            assert isinstance(end_state, Queued)
            time_remaining = max(
                (end_state.start_time - pendulum.now("utc")).total_seconds(), 0
            )
            self.logger.debug(
                (
                    f"Flow run is in a Queued state. Sleeping for at most {time_remaining:.2f} "
                    f"seconds and attempting to run again."
                )
            )
            # Sleep until not in a queued state, then attempt to re-run
            while time_remaining > 0:
                delay = min(
                    prefect.config.cloud.check_cancellation_interval, time_remaining
                )
                time_remaining -= delay
                # Imported `time.sleep` as `time_sleep` to allow monkeypatching in tests
                time_sleep(delay)

                flow_run_info = self.client.get_flow_run_info(
                    flow_run_id=prefect.context.get("flow_run_id")
                )
                context.update(flow_run_version=flow_run_info.version)
                if not isinstance(flow_run_info.state, Queued):
                    break

            # When concurrency slots become free, this will eventually result
            # in a non queued state, but will result in more or less just waiting
            # until the orchestration layer says we are clear to go. Purposefully
            # not passing `state` so we can refresh the info from cloud,
            # allowing us to prematurely bail out of flow runs that have already
            # reached a finished state via another process.
            end_state = super().run(
                task_states=task_states,
                return_tasks=return_tasks,
                parameters=parameters,
                task_runner_state_handlers=task_runner_state_handlers,
                executor=executor,
                context=context,
                task_contexts=task_contexts,
            )

        return end_state

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
            - task_contexts (Dict[Task, Dict[str, Any]], optional): contexts that will be
                provided to each task
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
            raise ENDRUN(state=state) from exc

        updated_context = context or {}
        updated_context.update(flow_run_info.context or {})
        updated_context.update(
            flow_id=flow_run_info.flow_id,
            flow_run_id=flow_run_info.id,
            flow_run_version=flow_run_info.version,
            flow_run_name=flow_run_info.name,
            scheduled_start_time=flow_run_info.scheduled_start_time,
        )

        tasks = {slug: t for t, slug in self.flow.slugs.items()}
        # update task states and contexts
        for task_run in flow_run_info.task_runs:
            try:
                task = tasks[task_run.task_slug]
            except KeyError as exc:
                msg = (
                    f"Task slug {task_run.task_slug} not found in the current Flow; "
                    f"this is usually caused by changing the Flow without reregistering "
                    f"it with the Prefect API."
                )
                raise KeyError(msg) from exc
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

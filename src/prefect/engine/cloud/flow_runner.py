import warnings
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

import prefect
from prefect.client import Client
from prefect.core import Flow, Task
from prefect.engine.flow_runner import FlowRunner, FlowRunnerInitializeResult
from prefect.engine.runner import ENDRUN
from prefect.engine.state import Failed, State
from prefect.engine.cloud import CloudTaskRunner
from prefect.engine.cloud.utilities import prepare_state_for_cloud


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

    def _heartbeat(self) -> None:
        try:
            flow_run_id = prefect.context.get("flow_run_id")
            self.client.update_flow_run_heartbeat(flow_run_id)
        except:
            warnings.warn("Heartbeat failed for Flow '{}'".format(self.flow.name))

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
            flow_run_version=flow_run_info.version,
            scheduled_start_time=flow_run_info.scheduled_start_time,
        )

        # update task states and contexts
        for task_run in flow_run_info.task_runs:
            task = self.flow.task_ids[task_run.task_id]
            task_states.setdefault(task, task_run.state)
            task_contexts.setdefault(task, {}).update(
                task_run_version=task_run.version, task_run_id=task_run.id
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

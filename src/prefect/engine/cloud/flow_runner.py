# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import warnings
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

import prefect
import prefect.engine.cloud
from prefect.client import Client
from prefect.core import Flow
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.runner import ENDRUN
from prefect.engine.state import Failed, State


class CloudFlowRunner(FlowRunner):
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

    def __init__(self, flow: Flow, state_handlers: Iterable[Callable] = None) -> None:
        self.client = Client()
        super().__init__(
            flow=flow,
            task_runner_cls=prefect.engine.cloud.CloudTaskRunner,
            state_handlers=state_handlers,
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
        new_state = super().call_runner_target_handlers(
            old_state=old_state, new_state=new_state
        )

        flow_run_id = prefect.context.get("flow_run_id", None)
        version = prefect.context.get("flow_run_version")

        try:
            self.client.set_flow_run_state(
                flow_run_id=flow_run_id,
                version=version,
                state=new_state,
                result_handler=self.flow.result_handler,
            )
        except Exception as exc:
            raise ENDRUN(state=new_state)

        prefect.context.update(flow_run_version=version + 1)  # type: ignore

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

        try:
            flow_run_info = self.client.get_flow_run_info(
                flow_run_id=prefect.context.get("flow_run_id", ""),
                result_handler=self.flow.result_handler,
            )
        except Exception as exc:
            if state is None:
                state = Failed(
                    message="Could not retrieve state from Prefect Cloud", result=exc
                )
            raise ENDRUN(state=state)

        context.update(flow_run_version=flow_run_info.version)  # type: ignore
        # if state is set, keep it; otherwise load from db
        state = state or flow_run_info.state  # type: ignore

        # update parameters, prioritizing kwarg-provided params
        updated_parameters = flow_run_info.parameters or {}  # type: ignore
        updated_parameters.update(parameters)

        return super().initialize_run(
            state=state, context=context, parameters=updated_parameters
        )

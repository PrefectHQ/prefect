# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any, Callable, Dict, Iterable, Optional, Tuple

import prefect
from prefect import config
from prefect.client import Client
from prefect.client.result_handlers import ResultHandler
from prefect.core import Flow, Task
from prefect.engine import signals
from prefect.engine.state import State
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.task_runner import TaskRunner


class CloudTaskRunner(TaskRunner):
    """
    TaskRunners handle the execution of Tasks and determine the State of a Task
    before, during and after the Task is run.

    In particular, through the TaskRunner you can specify the states of any upstream dependencies,
    any inputs required for this Task to run, and what state the Task should be initialized with.

    Args:
        - task (Task): the Task to be run / executed
        - result_handler (ResultHandler, optional): the handler to use for
            retrieving and storing state results during execution
        - state_handlers (Iterable[Callable], optional): A list of state change handlers
            that will be called whenever the task changes state, providing an
            opportunity to inspect or modify the new state. The handler
            will be passed the task runner instance, the old (prior) state, and the new
            (current) state, with the following signature:

            ```
                state_handler(
                    task_runner: TaskRunner,
                    old_state: State,
                    new_state: State) -> State
            ```

            If multiple functions are passed, then the `new_state` argument will be the
            result of the previous handler.
    """

    def __init__(
        self,
        task: Task,
        result_handler: ResultHandler = None,
        state_handlers: Iterable[Callable] = None,
    ) -> None:
        self.task = task
        self.client = Client()
        self.result_handler = result_handler
        super().__init__(
            task=task, result_handler=result_handler, state_handlers=state_handlers
        )

    def _heartbeat(self) -> None:
        task_run_id = self.task_run_id
        self.client.update_task_run_heartbeat(task_run_id)

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
        for handler in self.task.state_handlers:
            new_state = handler(self.task, old_state, new_state)

        task_run_id = prefect.context.get("task_run_id")
        version = prefect.context.get("task_run_version")

        res = self.client.set_task_run_state(
            task_run_id=task_run_id,
            version=version,
            state=new_state,
            cache_for=self.task.cache_for,
            result_handler=self.result_handler,
        )
        prefect.context.update(task_run_version=res.version)  # type: ignore

        return new_state

    def initialize_run(
        self, state: Optional[State], context: Dict[str, Any]
    ) -> Tuple[State, Dict[str, Any]]:
        """
        Initializes the Task run by initializing state and context appropriately.

        Args:
            - state (State): the proposed initial state of the flow run; can be `None`
            - context (dict): the context to be updated with relevant information

        Returns:
            - tuple: a tuple of the updated state and context objects
        """
        flow_run_id = context.get("flow_run_id", None)
        task_run_info = self.client.get_task_run_info(
            flow_run_id,
            context.get("task_id", ""),
            map_index=context.get("map_index", None),
            result_handler=self.result_handler,
        )

        # if state is set, keep it; otherwise load from db
        state = state or task_run_info.state  # type: ignore
        context.update(
            task_run_version=task_run_info.version,  # type: ignore
            task_run_id=task_run_info.id,  # type: ignore
        )
        self.task_run_id = task_run_info.id  # type: ignore

        context.update(task_name=self.task.name)
        return super().initialize_run(state=state, context=context)


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

    def __init__(
        self,
        flow: Flow,
        task_runner_cls: type = None,
        state_handlers: Iterable[Callable] = None,
    ) -> None:
        self.flow = flow
        self.task_runner_cls = task_runner_cls or CloudTaskRunner
        self.client = Client()
        super().__init__(
            flow=flow,
            task_runner_cls=self.task_runner_cls,
            state_handlers=state_handlers,
        )

    def _heartbeat(self) -> None:
        flow_run_id = prefect.context.get("flow_run_id")
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

        flow_run_id = prefect.context.get("flow_run_id", None)
        version = prefect.context.get("flow_run_version")

        res = self.client.set_flow_run_state(
            flow_run_id=flow_run_id,
            version=version,
            state=new_state,
            result_handler=self.flow.result_handler,
        )
        prefect.context.update(flow_run_version=res.version)  # type: ignore

        return new_state

    def initialize_run(
        self, state: Optional[State], context: Dict[str, Any]
    ) -> Tuple[State, Dict[str, Any]]:
        """
        Initializes the Flow run by initializing state and context appropriately.

        Args:
            - state (State): the proposed initial state of the flow run; can be `None`
            - context (dict): the context to be updated with relevant information

        Returns:
            - tuple: a tuple of the updated state and context objects
        """

        flow_run_info = self.client.get_flow_run_info(
            flow_run_id=prefect.context.get("flow_run_id", ""),
            result_handler=self.flow.result_handler,
        )
        context.update(flow_run_version=flow_run_info.version)  # type: ignore
        # if state is set, keep it; otherwise load from db
        state = state or flow_run_info.state  # type: ignore

        ## update parameters, prioritizing kwarg-provided params
        parameters = flow_run_info.parameters or {}  # type: ignore
        parameters.update(context.get("parameters", {}))
        context.update(parameters=parameters)

        return super().initialize_run(state=state, context=context)

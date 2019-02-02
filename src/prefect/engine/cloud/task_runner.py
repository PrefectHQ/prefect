# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import copy
import warnings
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

import prefect
from prefect.client import Client
from prefect.core import Edge, Task
from prefect.engine.result import NoResult
from prefect.engine.result_handlers import ResultHandler
from prefect.engine.runner import ENDRUN, call_state_handlers
from prefect.engine.state import Cached, Failed, Mapped, State
from prefect.engine.task_runner import TaskRunner, TaskRunnerInitializeResult
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
        super().__init__(
            task=task, state_handlers=state_handlers, result_handler=result_handler
        )

    def _heartbeat(self) -> None:
        try:
            task_run_id = self.task_run_id  # type: ignore
            self.client.update_task_run_heartbeat(task_run_id)  # type: ignore
        except:
            warnings.warn("Heartbeat failed for Task '{}'".format(self.task.name))

    def prepare_state_for_run(self, state: State) -> State:
        res = state._result
        state._result = res.read()
        if (  # type: ignore
            hasattr(state, "cached_inputs")
            and state.cached_inputs is not None  # type: ignore
        ):
            state.cached_inputs = {  # type: ignore
                k: r.read() for k, r in state.cached_inputs.items()  # type: ignore
            }  # type: ignore
        return state

    def prepare_state_for_cloud(self, state: State) -> State:
        """
        Prepares a Prefect State for being sent to Cloud; this ensures that any data attributes
        are properly handled prior to being shipped off to a database.

        Args:
            - state (State): the Prefect State to prepare

        Returns:
            - State: a sanitized copy of the original state
        """
        res = state._result
        cloud_state = copy.copy(state)
        cloud_state._result = res.write() if cloud_state.is_cached() else NoResult
        if (
            hasattr(cloud_state, "cached_inputs")
            and cloud_state.cached_inputs is not None  # type: ignore
        ):
            cloud_state.cached_inputs = {  # type: ignore
                k: r.write()
                for k, r in cloud_state.cached_inputs.items()  # type: ignore
            }
        return cloud_state

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
            self.logger.debug(
                "Exception raised while calling state handlers: {}".format(repr(exc))
            )
            if raise_on_exception:
                raise exc
            new_state = Failed(
                "Exception raised while calling state handlers.", result=exc
            )

        task_run_id = prefect.context.get("task_run_id")
        version = prefect.context.get("task_run_version")

        try:
            cloud_state = self.prepare_state_for_cloud(new_state)
            self.client.set_task_run_state(
                task_run_id=task_run_id,
                version=version,
                state=cloud_state,
                cache_for=self.task.cache_for,
            )
        except Exception as exc:
            self.logger.debug(
                "Failed to set task state with error: {}".format(repr(exc))
            )
            raise ENDRUN(state=new_state)

        if version is not None:
            prefect.context.update(task_run_version=version + 1)  # type: ignore

        return new_state

    def initialize_run(  # type: ignore
        self, state: Optional[State], context: Dict[str, Any]
    ) -> TaskRunnerInitializeResult:
        """
        Initializes the Task run by initializing state and context appropriately.

        Args:
            - state (State): the proposed initial state of the flow run; can be `None`
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
                    task_id=self.task.id,
                    map_index=map_index,
                )

                # if state was provided, keep it; otherwise use the one from db
                state = state or task_run_info.state  # type: ignore
                context.update(
                    task_run_version=task_run_info.version,  # type: ignore
                    task_run_id=task_run_info.id,  # type: ignore
                )
            except Exception as exc:
                self.logger.debug(
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
        if state is not None:
            state = self.prepare_state_for_run(state)

        return super().initialize_run(
            state=state, context=context, upstream_states=upstream_states
        )

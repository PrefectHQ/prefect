# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import warnings
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

import prefect
from prefect.client import Client
from prefect.core import Edge, Task
from prefect.engine.result_handlers import ResultHandler
from prefect.engine.runner import ENDRUN, call_state_handlers
from prefect.engine.state import Failed, Mapped, State
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
            (current) state, with the following signature:
            ```python
                state_handler(
                    task_runner: TaskRunner,
                    old_state: State,
                    new_state: State) -> State
            ```
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
            self.client.set_task_run_state(
                task_run_id=task_run_id,
                version=version,
                state=new_state,
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
        self,
        state: Optional[State],
        context: Dict[str, Any],
        upstream_states: Dict[Edge, State],
    ) -> TaskRunnerInitializeResult:
        """
        Initializes the Task run by initializing state and context appropriately.

        Args:
            - state (State): the proposed initial state of the flow run; can be `None`
            - context (Dict[str, Any]): the context to be updated with relevant information
            - upstream_states (Dict[Edge, State]): a dictionary
                representing the states of tasks upstream of this one

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

        ## ensure all inputs have been handled
        if state is not None:
            state.ensure_raw()
        for up_state in upstream_states.values():
            up_state.ensure_raw()

        return super().initialize_run(
            state=state, context=context, upstream_states=upstream_states
        )

    @call_state_handlers
    def finalize_run(self, state: State, upstream_states: Dict[Edge, State]) -> State:
        """
        Ensures that all results are handled appropriately on the final state.

        Args:
            - state (State): the final state of this task
            - upstream_states (Dict[Edge, Union[State, List[State]]]): the upstream states

        Returns:
            - State: the state of the task after running the check
        """
        raise_on_exception = prefect.context.get("raise_on_exception", False)
        from prefect.serialization.result_handlers import ResultHandlerSchema

        ## if a state has a "cached" attribute or a "cached_inputs" attribute, we need to handle it
        if getattr(state, "cached_inputs", None) is not None:
            try:
                input_handlers = {}

                for edge, upstream_state in upstream_states.items():
                    if edge.key is not None:
                        input_handlers[edge.key] = upstream_state._metadata["result"][
                            "result_handler"
                        ]
                state.handle_inputs(input_handlers)
            except Exception as exc:
                self.logger.debug(
                    "Exception raised while serializing inputs: {}".format(repr(exc))
                )
                if raise_on_exception:
                    raise exc
                new_state = Failed(
                    "Exception raised while serializing inputs.", result=exc
                )
                return new_state

        if state.is_successful() and state.cached is not None:  # type: ignore
            try:
                input_handlers = {}

                for edge, upstream_state in upstream_states.items():
                    if edge.key is not None:
                        input_handlers[edge.key] = upstream_state._metadata["result"][
                            "result_handler"
                        ]

                state.cached.handle_inputs(input_handlers)  # type: ignore
                state.cached.handle_outputs(self.result_handler)  # type: ignore
            except Exception as exc:
                self.logger.debug(
                    "Exception raised while serializing cached data: {}".format(
                        repr(exc)
                    )
                )
                if raise_on_exception:
                    raise exc
                new_state = Failed(
                    "Exception raised while serializing cached data.", result=exc
                )
                return new_state

        ## finally, update state _metadata attribute with information about how to handle this state's data
        state._metadata["result"].setdefault("raw", True)
        state._metadata["result"].setdefault(
            "result_handler", ResultHandlerSchema().dump(self.result_handler)
        )
        return state

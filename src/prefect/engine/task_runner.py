from contextlib import redirect_stdout
from contextlib import AbstractContextManager
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    NamedTuple,
    Optional,
    Set,
    Tuple,
)

import pendulum

import prefect
from prefect import config
from prefect.core import Edge, Task
from prefect.engine import signals
from prefect.engine.result.base import Result, ResultNotImplementedError
from prefect.engine.runner import ENDRUN, Runner, call_state_handlers
from prefect.engine.state import (
    Cached,
    Failed,
    Looped,
    Mapped,
    Paused,
    Pending,
    Resume,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Success,
    TimedOut,
    TriggerFailed,
)
from prefect.utilities.executors import (
    RecursiveCall,
    tail_recursive,
)
from prefect.utilities.compatibility import nullcontext
from prefect.exceptions import TaskTimeoutSignal


TaskRunnerInitializeResult = NamedTuple(
    "TaskRunnerInitializeResult", [("state", State), ("context", Dict[str, Any])]
)


class TaskRunner(Runner):
    """
    TaskRunners handle the execution of Tasks and determine the State of a Task
    before, during and after the Task is run.

    In particular, through the TaskRunner you can specify the states of any upstream dependencies
    and what state the Task should be initialized with.

    Args:
        - task (Task): the Task to be run / executed
        - state_handlers (Iterable[Callable], optional): A list of state change handlers that
            will be called whenever the task changes state, providing an opportunity to inspect
            or modify the new state. The handler will be passed the task runner instance, the
            old (prior) state, and the new (current) state, with the following signature:
            `state_handler(TaskRunner, old_state, new_state) -> Optional[State]`; If multiple
            functions are passed, then the `new_state` argument will be the result of the
            previous handler.
        - flow_result: the result instance configured for the flow (if any)
    """

    def __init__(
        self,
        task: Task,
        state_handlers: Iterable[Callable] = None,
        flow_result: Result = None,
    ):
        self.context = prefect.context.to_dict()
        self.task = task

        # Use result from task over the one provided off the parent Flow object
        if task.result:
            self.result = task.result
        else:
            self.result = Result().copy() if flow_result is None else flow_result.copy()

        self.flow_result = flow_result
        super().__init__(state_handlers=state_handlers)

    def __repr__(self) -> str:
        return "<{}: {}>".format(type(self).__name__, self.task.name)

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
        self.logger.debug(
            "Task '{name}': Handling state change from {old} to {new}".format(
                name=prefect.context.get("task_full_name", self.task.name),
                old=type(old_state).__name__,
                new=type(new_state).__name__,
            )
        )
        for handler in self.task.state_handlers:
            new_state = handler(self.task, old_state, new_state) or new_state

        return new_state

    def initialize_run(  # type: ignore
        self, state: Optional[State], context: Dict[str, Any]
    ) -> TaskRunnerInitializeResult:
        """
        Initializes the Task run by initializing state and context appropriately.

        If the task is being retried, then we retrieve the run count from the initial Retry
        state. Otherwise, we assume the run count is 1. The run count is stored in context as
        task_run_count.

        Also, if the task is being resumed through a `Resume` state, updates context to have
        `resume=True`.

        Args:
            - state (Optional[State]): the initial state of the run
            - context (Dict[str, Any]): the context to be updated with relevant information

        Returns:
            - tuple: a tuple of the updated state, context, upstream_states, and inputs objects
        """
        state, context = super().initialize_run(state=state, context=context)

        if isinstance(state, Retrying):
            run_count = state.run_count + 1
        else:
            run_count = state.context.get("task_run_count", 1)

        # detect if currently Paused with a recent start_time
        should_resume = (
            isinstance(state, Paused)
            and state.start_time
            and state.start_time <= pendulum.now("utc")  # type: ignore
        )
        if isinstance(state, Resume) or should_resume:
            context.update(resume=True)

        if "_loop_count" in state.context:
            loop_result = state._result
            if loop_result.value is None and loop_result.location is not None:  # type: ignore
                loop_result_value = self.result.read(loop_result.location).value  # type: ignore
            else:
                loop_result_value = loop_result.value  # type: ignore
            loop_context = {
                "task_loop_count": state.context.pop("_loop_count"),
                "task_loop_result": loop_result_value,
            }
            context.update(loop_context)

        context.update(
            task_run_count=run_count,
            task_name=self.task.name,
            task_tags=self.task.tags,
        )
        # Use the config stored in context if possible (should always be present)
        try:
            checkpointing = context["config"]["flows"]["checkpointing"]
        except KeyError:
            checkpointing = config.flows.checkpointing
        context.setdefault("checkpointing", checkpointing)

        map_index = context.get("map_index", None)
        if isinstance(map_index, int) and context.get("task_full_name"):
            context.update(
                logger=prefect.utilities.logging.get_logger(
                    context.get("task_full_name")
                )
            )
        else:
            context.update(logger=self.task.logger)

        # If provided, use task's target as result location
        if self.task.target:
            if not isinstance(self.task.target, str):
                self.result._formatter = self.task.target  # type: ignore
                self.result.location = None
            else:
                self.result.location = self.task.target

        return TaskRunnerInitializeResult(state=state, context=context)

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
        state which allow this Task to run.

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
        upstream_states = upstream_states or {}
        context = context or prefect.context.to_dict()
        map_index = context.setdefault("map_index", None)
        context["task_full_name"] = "{name}{index}".format(
            name=self.task.name,
            index=("" if map_index is None else "[{}]".format(map_index)),
        )

        task_inputs = {}  # type: Dict[str, Any]

        try:
            # initialize the run
            state, context = self.initialize_run(state, context)

            # run state transformation pipeline
            with prefect.context(context):

                if prefect.context.get("task_loop_count") is None:
                    self.logger.info(
                        "Task '{name}': Starting task run...".format(
                            name=context["task_full_name"]
                        )
                    )

                # check to make sure the task is in a pending state
                state = self.check_task_is_ready(state)

                # check if the task has reached its scheduled time
                state = self.check_task_reached_start_time(state)

                # Tasks never run if the upstream tasks haven't finished
                state = self.check_upstream_finished(
                    state, upstream_states=upstream_states
                )

                # check if any upstream tasks skipped (and if we need to skip)
                state = self.check_upstream_skipped(
                    state, upstream_states=upstream_states
                )

                # populate / hydrate all result objects
                state, upstream_states = self.load_results(
                    state=state, upstream_states=upstream_states
                )

                # retrieve task inputs from upstream and also explicitly passed inputs
                task_inputs = self.get_task_inputs(
                    state=state, upstream_states=upstream_states
                )

                if is_mapped_parent:
                    state = self.check_task_ready_to_map(
                        state, upstream_states=upstream_states
                    )

                # dynamically set task run name
                self.set_task_run_name(task_inputs=task_inputs)

                if self.task.target:
                    # check to see if there is a Result at the task's target
                    state = self.check_target(state, inputs=task_inputs)
                else:
                    # check to see if the task has a cached result
                    state = self.check_task_is_cached(state, inputs=task_inputs)

                # check if the task's trigger passes
                # triggers can raise Pauses, which require task_inputs to be available for caching
                # so we run this after the previous step
                state = self.check_task_trigger(state, upstream_states=upstream_states)

                # set the task state to running
                state = self.set_task_to_running(state, inputs=task_inputs)

                # run the task
                state = self.get_task_run_state(state, inputs=task_inputs)

                # cache the output, if appropriate
                state = self.cache_result(state, inputs=task_inputs)

                # check if the task needs to be retried
                state = self.check_for_retry(state, inputs=task_inputs)

                state = self.check_task_is_looping(
                    state,
                    inputs=task_inputs,
                    upstream_states=upstream_states,
                    context=context,
                )

        # for pending signals, including retries and pauses we need to make sure the
        # task_inputs are set
        except (ENDRUN, signals.PrefectStateSignal) as exc:
            state = exc.state
        except RecursiveCall as exc:
            raise exc

        except Exception as exc:
            msg = "Task '{name}': Unexpected error while running task: {exc}".format(
                name=context["task_full_name"], exc=repr(exc)
            )
            self.logger.exception(msg)
            state = Failed(message=msg, result=exc)
            if prefect.context.get("raise_on_exception"):
                raise exc

        # to prevent excessive repetition of this log
        # since looping relies on recursively calling self.run
        # TODO: figure out a way to only log this one single time instead of twice
        if prefect.context.get("task_loop_count") is None:
            # wrapping this final log in prefect.context(context) ensures
            # that any run-context, including task-run-ids, are respected
            with prefect.context(context):
                self.logger.info(
                    "Task '{name}': Finished task run for task with final state: "
                    "'{state}'".format(
                        name=context["task_full_name"], state=type(state).__name__
                    )
                )

        return state

    @call_state_handlers
    def check_upstream_finished(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> State:
        """
        Checks if the upstream tasks have all finshed.

        Args:
            - state (State): the current state of this task
            - upstream_states (Dict[Edge, Union[State, List[State]]]): the upstream states

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if upstream tasks are not finished.
        """
        all_states = set()  # type: Set[State]
        for edge, upstream_state in upstream_states.items():
            # if the upstream state is Mapped, and this task is also mapped,
            # we want each individual child to determine if it should
            # proceed or not based on its upstream parent in the mapping
            if isinstance(upstream_state, Mapped) and not edge.mapped:
                all_states.update(upstream_state.map_states)
            else:
                all_states.add(upstream_state)

        if not all(s.is_finished() for s in all_states):
            self.logger.debug(
                "Task '{name}': Not all upstream states are finished; "
                "ending run.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            raise ENDRUN(state)
        return state

    @call_state_handlers
    def check_upstream_skipped(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> State:
        """
        Checks if any of the upstream tasks have skipped.

        Args:
            - state (State): the current state of this task
            - upstream_states (Dict[Edge, State]): the upstream states

        Returns:
            - State: the state of the task after running the check
        """

        all_states = set()  # type: Set[State]
        for edge, upstream_state in upstream_states.items():

            # if the upstream state is Mapped, and this task is also mapped,
            # we want each individual child to determine if it should
            # skip or not based on its upstream parent in the mapping
            if isinstance(upstream_state, Mapped) and not edge.mapped:
                all_states.update(upstream_state.map_states)
            else:
                all_states.add(upstream_state)

        if self.task.skip_on_upstream_skip and any(s.is_skipped() for s in all_states):
            self.logger.debug(
                "Task '{name}': Upstream states were skipped; ending run.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            raise ENDRUN(
                state=Skipped(
                    message=(
                        "Upstream task was skipped; if this was not the intended "
                        "behavior, consider changing `skip_on_upstream_skip=False` "
                        "for this task."
                    )
                )
            )
        return state

    @call_state_handlers
    def check_task_ready_to_map(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> State:
        """
        Checks if the parent task is ready to proceed with mapping.

        Args:
            - state (State): the current state of this task
            - upstream_states (Dict[Edge, Union[State, List[State]]]): the upstream states

        Raises:
            - ENDRUN: either way, we dont continue past this point
        """
        if state.is_mapped():
            # this indicates we are executing a re-run of a mapped pipeline;
            # in this case, we populate both `map_states` and `cached_inputs`
            # to ensure the flow runner can properly regenerate the child tasks,
            # regardless of whether we mapped over an exchanged piece of data
            # or a non-data-exchanging upstream dependency
            if len(state.map_states) == 0 and state.n_map_states > 0:  # type: ignore
                state.map_states = [None] * state.n_map_states  # type: ignore
            state.cached_inputs = {
                edge.key: state._result  # type: ignore
                for edge, state in upstream_states.items()
                if edge.key
            }
            raise ENDRUN(state)

        # we can't map if there are no success states with iterables upstream
        if upstream_states and not any(
            [
                edge.mapped and state.is_successful()
                for edge, state in upstream_states.items()
            ]
        ):
            new_state = Failed("No upstream states can be mapped over.")  # type: State
            raise ENDRUN(new_state)
        elif not all(
            [
                hasattr(state.result, "__getitem__")
                for edge, state in upstream_states.items()
                if state.is_successful() and not state.is_mapped() and edge.mapped
            ]
        ):
            new_state = Failed("At least one upstream state has an unmappable result.")
            raise ENDRUN(new_state)
        else:
            # compute and set n_map_states
            n_map_states = min(
                [
                    len(s.result)
                    for e, s in upstream_states.items()
                    if e.mapped and s.is_successful() and not s.is_mapped()
                ]
                + [
                    s.n_map_states  # type: ignore
                    for e, s in upstream_states.items()
                    if e.mapped and s.is_mapped()
                ],
                default=0,
            )
            new_state = Mapped(
                "Ready to proceed with mapping.", n_map_states=n_map_states
            )
            raise ENDRUN(new_state)

    @call_state_handlers
    def check_task_trigger(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> State:
        """
        Checks if the task's trigger function passes.

        Args:
            - state (State): the current state of this task
            - upstream_states (Dict[Edge, Union[State, List[State]]]): the upstream states

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the trigger raises an error
        """
        try:
            if not self.task.trigger(upstream_states):
                raise signals.TRIGGERFAIL(message="Trigger failed")

        except signals.PrefectStateSignal as exc:

            self.logger.debug(
                "Task '{name}': {signal} signal raised during execution.".format(
                    name=prefect.context.get("task_full_name", self.task.name),
                    signal=type(exc).__name__,
                )
            )
            if prefect.context.get("raise_on_exception"):
                raise exc
            raise ENDRUN(exc.state) from exc

        # Exceptions are trapped and turned into TriggerFailed states
        except Exception as exc:
            self.logger.exception(
                "Task '{name}': Unexpected error while evaluating task trigger: "
                "{exc}".format(
                    exc=repr(exc),
                    name=prefect.context.get("task_full_name", self.task.name),
                )
            )
            if prefect.context.get("raise_on_exception"):
                raise exc
            raise ENDRUN(
                TriggerFailed(
                    "Unexpected error while checking task trigger: {}".format(
                        repr(exc)
                    ),
                    result=exc,
                )
            ) from exc

        return state

    @call_state_handlers
    def check_task_is_ready(self, state: State) -> State:
        """
        Checks to make sure the task is ready to run (Pending or Mapped).

        Args:
            - state (State): the current state of this task

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the task is not ready to run
        """

        # the task is ready
        if state.is_pending():
            return state

        # the task is mapped, in which case we still proceed so that the children tasks
        # are generated
        elif state.is_mapped():
            self.logger.debug(
                "Task '%s': task is already mapped, but run will proceed so children are generated.",
                prefect.context.get("task_full_name", self.task.name),
            )
            return state

        # this task is already running
        elif state.is_running():
            self.logger.debug(
                "Task '%s': task is already running.",
                prefect.context.get("task_full_name", self.task.name),
            )
            raise ENDRUN(state)

        elif state.is_cached():
            return state

        # this task is already finished
        elif state.is_finished():
            self.logger.debug(
                "Task '{name}': Task is already finished.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            raise ENDRUN(state)

        # this task is not pending
        else:
            self.logger.debug(
                "Task '{name}': Task is not ready to run or state was unrecognized "
                "({state}).".format(
                    name=prefect.context.get("task_full_name", self.task.name),
                    state=state,
                )
            )
            raise ENDRUN(state)

    @call_state_handlers
    def check_task_reached_start_time(self, state: State) -> State:
        """
        Checks if a task is in a Scheduled state and, if it is, ensures that the scheduled
        time has been reached. Note: Scheduled states include Retry states. Scheduled
        states with no start time (`start_time = None`) are never considered ready;
        they must be manually placed in another state.

        Args:
            - state (State): the current state of this task

        Returns:
            - State: the state of the task after performing the check

        Raises:
            - ENDRUN: if the task is Scheduled with a future scheduled time
        """
        if isinstance(state, Scheduled):
            # handle case where no start_time is set
            if state.start_time is None:
                self.logger.debug(
                    "Task '{name}' is scheduled without a known start_time; "
                    "ending run.".format(
                        name=prefect.context.get("task_full_name", self.task.name)
                    )
                )
                raise ENDRUN(state)

            # handle case where start time is in the future
            elif state.start_time and state.start_time > pendulum.now("utc"):
                self.logger.debug(
                    "Task '{name}': start_time has not been reached; "
                    "ending run.".format(
                        name=prefect.context.get("task_full_name", self.task.name)
                    )
                )
                raise ENDRUN(state)

        return state

    def get_task_inputs(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> Dict[str, Result]:
        """
        Given the task's current state and upstream states, generates the inputs for
        this task. Upstream state result values are used.

        Args:
            - state (State): the task's current state.
            - upstream_states (Dict[Edge, State]): the upstream state_handlers

        Returns:
            - Dict[str, Result]: the task inputs

        """
        task_inputs = {}  # type: Dict[str, Result]

        for edge, upstream_state in upstream_states.items():
            # construct task inputs
            if edge.key is not None:
                task_inputs[edge.key] = upstream_state._result  # type: ignore

        return task_inputs

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
        return state, upstream_states

    def set_task_run_name(self, task_inputs: Dict[str, Result]) -> None:
        """
        Sets the name for this task run and adds to `prefect.context`

        Args:
            - task_inputs (Dict[str, Result]): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        """

        task_run_name = self.task.task_run_name

        if task_run_name:
            raw_inputs = {k: r.value for k, r in task_inputs.items()}
            formatting_kwargs = {
                **prefect.context.get("parameters", {}),
                **prefect.context,
                **raw_inputs,
            }

            if not isinstance(task_run_name, str):
                task_run_name = task_run_name(**formatting_kwargs)
            else:
                task_run_name = task_run_name.format(**formatting_kwargs)

            prefect.context.update({"task_run_name": task_run_name})

    @call_state_handlers
    def check_target(self, state: State, inputs: Dict[str, Result]) -> State:
        """
        Checks if a Result exists at the task's target.

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Result]): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            - State: the state of the task after running the check
        """
        from dask.base import tokenize

        result = self.result
        target = self.task.target

        if result and target:
            raw_inputs = {k: r.value for k, r in inputs.items()}
            formatting_kwargs = {
                **prefect.context.get("parameters", {}).copy(),
                **prefect.context,
                **raw_inputs,
            }

            # self can't be used as a formatting parameter because it would ruin all method calls such as
            # result.exists() by providing two values of self
            formatting_kwargs.pop("self", None)

            if not isinstance(target, str):
                target = target(**formatting_kwargs)

            if result.exists(target, **formatting_kwargs):  # type: ignore
                known_location = target.format(**formatting_kwargs)  # type: ignore
                new_res = result.read(known_location)
                cached_state = Cached(
                    result=new_res,
                    hashed_inputs={
                        key: tokenize(val.value) for key, val in inputs.items()
                    },
                    cached_result_expiration=None,
                    cached_parameters=formatting_kwargs.get("parameters"),
                    message=f"Result found at task target {known_location}",
                )
                return cached_state

        return state

    @call_state_handlers
    def check_task_is_cached(self, state: State, inputs: Dict[str, Result]) -> State:
        """
        Checks if task is cached and whether the cache is still valid.

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Result]): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the task is not ready to run
        """
        if state.is_cached():
            assert isinstance(state, Cached)  # mypy assert
            sanitized_inputs = {key: res.value for key, res in inputs.items()}
            if self.task.cache_validator(
                state, sanitized_inputs, prefect.context.get("parameters")
            ):
                return state
            else:
                state = Pending("Cache was invalid; ready to run.")

        if self.task.cache_for is not None:
            candidate_states = []  # type: ignore
            if prefect.context.get("caches"):
                candidate_states = prefect.context.caches.get(
                    self.task.cache_key or self.task.name, []
                )
            sanitized_inputs = {key: res.value for key, res in inputs.items()}
            for candidate in candidate_states:
                if self.task.cache_validator(
                    candidate, sanitized_inputs, prefect.context.get("parameters")
                ):
                    return candidate

        if self.task.cache_for is not None:
            self.logger.warning(
                "Task '{name}': Can't use cache because it "
                "is now invalid".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
        return state or Pending("Cache was invalid; ready to run.")

    @call_state_handlers
    def set_task_to_running(self, state: State, inputs: Dict[str, Result]) -> State:
        """
        Sets the task to running

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Result]): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the task is not ready to run
        """
        if not state.is_pending():
            self.logger.debug(
                "Task '{name}': Can't set state to Running because it "
                "isn't Pending; ending run.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            raise ENDRUN(state)

        new_state = Running(message="Starting task run.")
        return new_state

    @call_state_handlers
    def get_task_run_state(self, state: State, inputs: Dict[str, Result]) -> State:
        """
        Runs the task and traps any signals or errors it raises.
        Also checkpoints the result of a successful task, if `task.checkpoint` is `True`.

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Result], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            - State: the state of the task after running the check

        Raises:
            - signals.PAUSE: if the task raises PAUSE
            - ENDRUN: if the task is not ready to run
        """
        task_name = prefect.context.get("task_full_name", self.task.name)

        if not state.is_running():
            self.logger.debug(
                f"Task {task_name!r}: Can't run task because it's not in a Running "
                "state; ending run."
            )

            raise ENDRUN(state)

        value = None
        raw_inputs = {k: r.value for k, r in inputs.items()}
        new_state = None
        try:
            self.logger.debug(f"Task {task_name!r}: Calling task.run() method...")

            # Create a stdout redirect if the task has log_stdout enabled
            log_context = (
                redirect_stdout(prefect.utilities.logging.RedirectToLog(self.logger))
                if getattr(self.task, "log_stdout", False)
                else nullcontext()
            )  # type: AbstractContextManager

            with log_context:
                value = prefect.utilities.executors.run_task_with_timeout(
                    task=self.task,
                    args=(),
                    kwargs=raw_inputs,
                    logger=self.logger,
                )

        except TaskTimeoutSignal as exc:  # Convert timeouts to a `TimedOut` state
            if prefect.context.get("raise_on_exception"):
                raise exc
            state = TimedOut("Task timed out during execution.", result=exc)
            return state

        except signals.LOOP as exc:  # Convert loop signals to a `Looped` state
            new_state = exc.state
            assert isinstance(new_state, Looped)
            value = new_state.result
            new_state.message = exc.state.message or "Task is looping ({})".format(
                new_state.loop_count
            )

        except signals.SUCCESS as exc:
            # Success signals can be treated like a normal result
            new_state = exc.state
            assert isinstance(new_state, Success)
            value = new_state.result

        except Exception as exc:  # Handle exceptions in the task
            if prefect.context.get("raise_on_exception"):
                raise
            self.logger.error(
                f"Task {task_name!r}: Exception encountered during task execution!",
                exc_info=True,
            )
            state = Failed(f"Error during execution of task: {exc!r}", result=exc)
            return state

        # checkpoint tasks if a result is present, except for when the user has opted out by
        # disabling checkpointing
        if (
            prefect.context.get("checkpointing") is True
            and self.task.checkpoint is not False
            and value is not None
        ):
            try:
                formatting_kwargs = {
                    **prefect.context.get("parameters", {}).copy(),
                    **prefect.context,
                    **raw_inputs,
                }
                result = self.result.write(value, **formatting_kwargs)
            except ResultNotImplementedError:
                result = self.result.from_value(value=value)
        else:
            result = self.result.from_value(value=value)

        if new_state is not None:
            new_state.result = result
            return new_state

        state = Success(result=result, message="Task run succeeded.")
        return state

    @call_state_handlers
    def cache_result(self, state: State, inputs: Dict[str, Result]) -> State:
        """
        Caches the result of a successful task, if appropriate. Alternatively,
        if the task is failed, caches the inputs.

        Tasks are cached if:
            - task.cache_for is not None
            - the task state is Successful
            - the task state is not Skipped (which is a subclass of Successful)

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Result], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            - State: the state of the task after running the check

        """
        from dask.base import tokenize

        if (
            state.is_successful()
            and not state.is_skipped()
            and self.task.cache_for is not None
        ):
            expiration = pendulum.now("utc") + self.task.cache_for
            cached_state = Cached(
                result=state._result,
                hashed_inputs={key: tokenize(val.value) for key, val in inputs.items()},
                cached_result_expiration=expiration,
                cached_parameters=prefect.context.get("parameters"),
                message=state.message,
            )
            return cached_state

        return state

    @call_state_handlers
    def check_for_retry(self, state: State, inputs: Dict[str, Result]) -> State:
        """
        Checks to see if a FAILED task should be retried.

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Result]): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            - State: the state of the task after running the check
        """
        if state.is_failed():

            # Check if the exception is an instance of any of the retry_on types and
            # do not retry if it is not
            if (
                self.task.retry_on
                and state.result is not None
                and not any(
                    isinstance(state.result, retry_on_type)
                    for retry_on_type in self.task.retry_on
                )
            ):
                self.logger.info(
                    "Task '{name}': Skipping retry. Exception of type {exc_type!r} is "
                    "not an instance of the retry on exception types.".format(
                        name=prefect.context.get("task_full_name", self.task.name),
                        exc_type=type(state.result).__name__,
                    )
                )
                return state

            run_count = prefect.context.get("task_run_count", 1)
            loop_result = None
            state_context = None
            if prefect.context.get("task_loop_count") is not None:

                loop_result = self.result.from_value(
                    value=prefect.context.get("task_loop_result")
                )

                # checkpoint tasks if a result is present, except for when the user has opted
                # out by disabling checkpointing
                if (
                    prefect.context.get("checkpointing") is True
                    and self.task.checkpoint is not False
                    and loop_result.value is not None
                ):
                    try:
                        raw_inputs = {k: r.value for k, r in inputs.items()}
                        formatting_kwargs = {
                            **prefect.context.get("parameters", {}).copy(),
                            **prefect.context,
                            **raw_inputs,
                        }
                        loop_result = self.result.write(
                            loop_result.value, **formatting_kwargs
                        )
                    except ResultNotImplementedError:
                        pass

                state_context = {"_loop_count": prefect.context["task_loop_count"]}
            if run_count <= self.task.max_retries:
                start_time = pendulum.now("utc") + self.task.retry_delay
                msg = "Retrying Task (after attempt {n} of {m})".format(
                    n=run_count, m=self.task.max_retries + 1
                )
                retry_state = Retrying(
                    start_time=start_time,
                    context=state_context,
                    message=msg,
                    run_count=run_count,
                    result=loop_result,
                )
                return retry_state

        return state

    def check_task_is_looping(
        self,
        state: State,
        inputs: Dict[str, Result] = None,
        upstream_states: Dict[Edge, State] = None,
        context: Dict[str, Any] = None,
    ) -> State:
        """
        Checks to see if the task is in a `Looped` state and if so, rerun the pipeline with an
        incremeneted `loop_count`.

        Args:
            - state (State, optional): initial `State` to begin task run from;
                defaults to `Pending()`
            - inputs (Dict[str, Result], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.
            - upstream_states (Dict[Edge, State]): a dictionary
                representing the states of any tasks upstream of this one. The keys of the
                dictionary should correspond to the edges leading to the task.
            - context (dict, optional): prefect Context to use for execution

        Returns:
            - `State` object representing the final post-run state of the Task
        """
        if state.is_looped():
            assert isinstance(state, Looped)  # mypy assert
            assert isinstance(context, dict)  # mypy assert
            msg = "Looping task (on loop index {})".format(state.loop_count)
            context.update(
                {
                    "task_loop_result": state.result,
                    "task_loop_count": state.loop_count + 1,
                }
            )
            context.update(task_run_version=prefect.context.get("task_run_version"))
            new_state = Pending(message=msg)
            raise RecursiveCall(
                self.run,
                self,
                new_state,
                upstream_states=upstream_states,
                context=context,
            )

        return state

import collections
import copy
import itertools
import threading
from functools import partial, wraps
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    NamedTuple,
    Sized,
    Tuple,
    TYPE_CHECKING,
    Union,
)

import pendulum

import prefect
from prefect import config
from prefect.core import Edge, Task
from prefect.engine import signals
from prefect.engine.result import NoResult, Result
from prefect.engine.runner import ENDRUN, Runner, call_state_handlers
from prefect.engine.state import (
    Cached,
    Failed,
    Mapped,
    Paused,
    Pending,
    Resume,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Submitted,
    Success,
    TimedOut,
    TriggerFailed,
)
from prefect.utilities.executors import main_thread_timeout, run_with_heartbeat

if TYPE_CHECKING:
    from prefect.engine.result_handlers import ResultHandler


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
        - state_handlers (Iterable[Callable], optional): A list of state change handlers
            that will be called whenever the task changes state, providing an
            opportunity to inspect or modify the new state. The handler
            will be passed the task runner instance, the old (prior) state, and the new
            (current) state, with the following signature: `state_handler(TaskRunner, old_state, new_state) -> Optional[State]`;
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
        result_handler: "ResultHandler" = None,
    ):
        self.task = task
        self.result_handler = (
            task.result_handler
            or result_handler
            or prefect.engine.get_default_result_handler_class()()
        )
        super().__init__(state_handlers=state_handlers)

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

        Also, if the task is being resumed through a `Resume` state, updates context to have `resume=True`.

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
            run_count = 1

        if isinstance(state, Resume):
            context.update(resume=True)

        context.update(task_run_count=run_count, task_name=self.task.name)

        return TaskRunnerInitializeResult(state=state, context=context)

    def run(
        self,
        state: State = None,
        upstream_states: Dict[Edge, State] = None,
        context: Dict[str, Any] = None,
        executor: "prefect.engine.executors.Executor" = None,
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
            - executor (Executor, optional): executor to use when performing
                computation; defaults to the executor specified in your prefect configuration

        Returns:
            - `State` object representing the final post-run state of the Task
        """
        upstream_states = upstream_states or {}
        context = context or {}
        map_index = context.setdefault("map_index", None)
        context["task_full_name"] = "{name}{index}".format(
            name=self.task.name,
            index=("" if map_index is None else "[{}]".format(map_index)),
        )

        if executor is None:
            executor = prefect.engine.get_default_executor_class()()

        # if mapped is true, this task run is going to generate a Mapped state. It won't
        # actually run, but rather spawn children tasks to map over its inputs. We
        # detect this case by checking for:
        #   - upstream edges that are `mapped`
        #   - no `map_index` (which indicates that this is the child task, not the parent)
        mapped = any([e.mapped for e in upstream_states]) and map_index is None
        task_inputs = {}  # type: Dict[str, Any]

        self.logger.info(
            "Task '{name}': Starting task run...".format(name=context["task_full_name"])
        )

        try:
            # initialize the run
            state, context = self.initialize_run(state, context)

            # run state transformation pipeline
            with prefect.context(context):

                # check to make sure the task is in a pending state
                state = self.check_task_is_ready(state)

                # check if the task has reached its scheduled time
                state = self.check_task_reached_start_time(state)

                # Tasks never run if the upstream tasks haven't finished
                state = self.check_upstream_finished(
                    state, upstream_states=upstream_states
                )

                # if the task is mapped, process the mapped children and exit
                if mapped:
                    state = self.run_mapped_task(
                        state=state,
                        upstream_states=upstream_states,
                        context=context,
                        executor=executor,
                    )

                    state = self.wait_for_mapped_task(state=state, executor=executor)

                    self.logger.debug(
                        "Task '{name}': task has been mapped; ending run.".format(
                            name=context["task_full_name"]
                        )
                    )
                    raise ENDRUN(state)

                # check if any upstream tasks skipped (and if we need to skip)
                state = self.check_upstream_skipped(
                    state, upstream_states=upstream_states
                )

                # retrieve task inputs from upstream and also explicitly passed inputs
                task_inputs = self.get_task_inputs(
                    state=state, upstream_states=upstream_states
                )

                # check to see if the task has a cached result
                state = self.check_task_is_cached(state, inputs=task_inputs)

                # check if the task's trigger passes
                # triggers can raise Pauses, which require task_inputs to be available for caching
                # so we run this after the previous step
                state = self.check_task_trigger(state, upstream_states=upstream_states)

                # set the task state to running
                state = self.set_task_to_running(state)

                # run the task
                state = self.get_task_run_state(
                    state, inputs=task_inputs, timeout_handler=executor.timeout_handler
                )

                # cache the output, if appropriate
                state = self.cache_result(state, inputs=task_inputs)

                # check if the task needs to be retried
                state = self.check_for_retry(state, inputs=task_inputs)

        # for pending signals, including retries and pauses we need to make sure the
        # task_inputs are set
        except (ENDRUN, signals.PrefectStateSignal) as exc:
            if exc.state.is_pending():
                exc.state.cached_inputs = task_inputs or {}  # type: ignore
            state = exc.state
            if not isinstance(exc, ENDRUN) and prefect.context.get(
                "raise_on_exception"
            ):
                raise exc

        except Exception as exc:
            msg = "Task '{name}': unexpected error while running task: {exc}".format(
                name=context["task_full_name"], exc=repr(exc)
            )
            self.logger.error(msg)
            state = Failed(message=msg, result=exc)
            if prefect.context.get("raise_on_exception"):
                raise exc

        self.logger.info(
            "Task '{name}': finished task run for task with final state: '{state}'".format(
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
        if not all(s.is_finished() for s in upstream_states.values()):
            self.logger.debug(
                "Task '{name}': not all upstream states are finished; ending run.".format(
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
        for upstream_state in upstream_states.values():
            if isinstance(upstream_state, Mapped):
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
    def check_task_trigger(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> State:
        """
        Checks if the task's trigger function passes. If the upstream_states is empty,
        then the trigger is not called.

        Args:
            - state (State): the current state of this task
            - upstream_states (Dict[Edge, Union[State, List[State]]]): the upstream states

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the trigger raises an error
        """

        all_states = set()  # type: Set[State]
        for upstream_state in upstream_states.values():
            if isinstance(upstream_state, Mapped):
                all_states.update(upstream_state.map_states)
            else:
                all_states.add(upstream_state)

        try:
            if not upstream_states:
                return state
            elif not self.task.trigger(all_states):
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
            raise ENDRUN(exc.state)

        # Exceptions are trapped and turned into TriggerFailed states
        except Exception as exc:
            self.logger.debug(
                "Task '{name}': unexpected error while evaluating task trigger: {exc}".format(
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
            )

        return state

    @call_state_handlers
    def check_task_is_ready(self, state: State) -> State:
        """
        Checks to make sure the task is ready to run (Pending or Mapped).

        If the state is Paused, an ENDRUN is raised.

        Args:
            - state (State): the current state of this task

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the task is not ready to run
        """

        # the task is paused
        if isinstance(state, Paused):
            self.logger.debug(
                "Task '{name}': task is paused; ending run.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            raise ENDRUN(state)

        # the task is ready
        elif state.is_pending():
            return state

        # the task is mapped, in which case we still proceed so that the children tasks
        # are generated (note that if the children tasks)
        elif state.is_mapped():
            self.logger.debug(
                "Task '{name}': task is mapped, but run will proceed so children are generated.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            return state

        # this task is already running
        elif state.is_running():
            self.logger.debug(
                "Task '{name}': task is already running.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            raise ENDRUN(state)

        elif state.is_cached():
            return state

        # this task is already finished
        elif state.is_finished():
            self.logger.debug(
                "Task '{name}': task is already finished.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            raise ENDRUN(state)

        # this task is not pending
        else:
            self.logger.debug(
                "Task '{name}' is not ready to run or state was unrecognized ({state}).".format(
                    name=prefect.context.get("task_full_name", self.task.name),
                    state=state,
                )
            )
            raise ENDRUN(state)

    @call_state_handlers
    def check_task_reached_start_time(self, state: State) -> State:
        """
        Checks if a task is in a Scheduled state and, if it is, ensures that the scheduled
        time has been reached. Note: Scheduled states include Retry states.

        Args:
            - state (State): the current state of this task

        Returns:
            - State: the state of the task after performing the check

        Raises:
            - ENDRUN: if the task is Scheduled with a future scheduled time
        """
        if isinstance(state, Scheduled):
            if state.start_time and state.start_time > pendulum.now("utc"):
                self.logger.debug(
                    "Task '{name}': start_time has not been reached; ending run.".format(
                        name=prefect.context.get("task_full_name", self.task.name)
                    )
                )
                raise ENDRUN(state)
        return state

    def get_task_inputs(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> Dict[str, Result]:
        """
        Given the task's current state and upstream states, generates the inputs for this task.
        Upstream state result values are used. If the current state has `cached_inputs`, they
        will override any upstream values which are `NoResult`.

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
                task_inputs[  # type: ignore
                    edge.key
                ] = upstream_state._result.to_result()  # type: ignore

        if state.is_pending() and state.cached_inputs is not None:  # type: ignore
            task_inputs.update(
                {
                    k: r.to_result()
                    for k, r in state.cached_inputs.items()  # type: ignore
                    if task_inputs.get(k, NoResult) == NoResult
                }
            )

        return task_inputs

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
            if self.task.cache_validator(
                state, inputs, prefect.context.get("parameters")
            ):
                state._result = state._result.to_result()
                return state
            else:
                self.logger.debug(
                    "Task '{name}': can't use cache because it "
                    "is now invalid".format(
                        name=prefect.context.get("task_full_name", self.task.name)
                    )
                )
                return Pending("Cache was invalid; ready to run.")
        return state

    @call_state_handlers
    def run_mapped_task(
        self,
        state: State,
        upstream_states: Dict[Edge, State],
        context: Dict[str, Any],
        executor: "prefect.engine.executors.Executor",
    ) -> State:
        """
        If the task is being mapped, submits children tasks for execution. Returns a `Mapped` state.

        Args:
            - state (State): the current task state
            - upstream_states (Dict[Edge, State]): the upstream states
            - context (dict, optional): prefect Context to use for execution
            - executor (Executor): executor to use when performing computation

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the current state is not `Running`
        """

        map_upstream_states = []

        # we don't know how long the iterables are, but we want to iterate until we reach
        # the end of the shortest one
        counter = itertools.count()

        # infinite loop, if upstream_states has any entries
        while True and upstream_states:
            i = next(counter)
            states = {}

            try:

                for edge, upstream_state in upstream_states.items():

                    # if the edge is not mapped over, then we simply take its state
                    if not edge.mapped:
                        states[edge] = upstream_state

                    # if the edge is mapped and the upstream state is Mapped, then we are mapping
                    # over a mapped task. In this case, we take the appropriately-indexed upstream
                    # state from the upstream tasks's `Mapped.map_states` array.
                    # Note that these "states" might actually be futures at this time; we aren't
                    # blocking until they finish.
                    elif edge.mapped and upstream_state.is_mapped():
                        states[edge] = upstream_state.map_states[i]  # type: ignore

                    # Otherwise, we are mapping over the result of a "vanilla" task. In this
                    # case, we create a copy of the upstream state but set the result to the
                    # appropriately-indexed item from the upstream task's `State.result`
                    # array.
                    else:
                        states[edge] = copy.copy(upstream_state)

                        # if the current state is already Mapped, then we might be executing
                        # a re-run of the mapping pipeline. In that case, the upstream states
                        # might not have `result` attributes (as any required results could be
                        # in the `cached_inputs` attribute of one of the child states).
                        # Therefore, we only try to get a result if EITHER this task's
                        # state is not already mapped OR the upstream result is not None.
                        if not state.is_mapped() or upstream_state.result != NoResult:
                            states[edge].result = upstream_state.result[  # type: ignore
                                i
                            ]
                        elif state.is_mapped():
                            if i >= len(state.map_states):  # type: ignore
                                raise IndexError()

                # only add this iteration if we made it through all iterables
                map_upstream_states.append(states)

            # index error means we reached the end of the shortest iterable
            except IndexError:
                break

        def run_fn(
            state: State, map_index: int, upstream_states: Dict[Edge, State]
        ) -> State:
            map_context = context.copy()
            map_context.update(map_index=map_index)
            return self.run(
                upstream_states=upstream_states,
                # if we set the state here, then it will not be processed by `initialize_run()`
                state=state,
                context=map_context,
                executor=executor,
            )

        # generate initial states, if available
        if isinstance(state, Mapped):
            initial_states = list(state.map_states)  # type: List[Optional[State]]
        else:
            initial_states = []
        initial_states.extend([None] * (len(map_upstream_states) - len(initial_states)))

        # map over the initial states, a counter representing the map_index, and also the mapped upstream states
        map_states = executor.map(
            run_fn, initial_states, range(len(map_upstream_states)), map_upstream_states
        )

        return Mapped(
            message="Mapped tasks submitted for execution.", map_states=map_states
        )

    @call_state_handlers
    def wait_for_mapped_task(
        self, state: State, executor: "prefect.engine.executors.Executor"
    ) -> State:
        """
        Blocks until a mapped state's children have finished running.

        Args:
            - state (State): the current `Mapped` state
            - executor (Executor): the run's executor

        Returns:
            - State: the new state
        """
        if state.is_mapped():
            assert isinstance(state, Mapped)  # mypy assert
            state.map_states = executor.wait(state.map_states)
        return state

    @call_state_handlers
    def set_task_to_running(self, state: State) -> State:
        """
        Sets the task to running

        Args:
            - state (State): the current state of this task

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the task is not ready to run
        """
        if not state.is_pending():
            self.logger.debug(
                "Task '{name}': can't set state to Running because it "
                "isn't Pending; ending run.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            raise ENDRUN(state)

        return Running(message="Starting task run.")

    @run_with_heartbeat
    @call_state_handlers
    def get_task_run_state(
        self,
        state: State,
        inputs: Dict[str, Result],
        timeout_handler: Optional[Callable],
    ) -> State:
        """
        Runs the task and traps any signals or errors it raises.
        Also checkpoints the result of a successful task, if `task.checkpoint` is `True`.

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Result], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.
            - timeout_handler (Callable, optional): function for timing out
                task execution, with call signature `handler(fn, *args, **kwargs)`. Defaults to
                `prefect.utilities.executors.main_thread_timeout`

        Returns:
            - State: the state of the task after running the check

        Raises:
            - signals.PAUSE: if the task raises PAUSE
            - ENDRUN: if the task is not ready to run
        """
        if not state.is_running():
            self.logger.debug(
                "Task '{name}': can't run task because it's not in a "
                "Running state; ending run.".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )

            raise ENDRUN(state)

        try:
            self.logger.debug(
                "Task '{name}': Calling task.run() method...".format(
                    name=prefect.context.get("task_full_name", self.task.name)
                )
            )
            timeout_handler = timeout_handler or main_thread_timeout
            raw_inputs = {k: r.value for k, r in inputs.items()}
            result = timeout_handler(
                self.task.run, timeout=self.task.timeout, **raw_inputs
            )

        # inform user of timeout
        except TimeoutError as exc:
            if prefect.context.get("raise_on_exception"):
                raise exc
            state = TimedOut(
                "Task timed out during execution.", result=exc, cached_inputs=inputs
            )
            return state

        result = Result(value=result, result_handler=self.result_handler)
        state = Success(result=result, message="Task run succeeded.")

        if state.is_successful() and self.task.checkpoint is True:
            state._result.store_safe_value()

        return state

    @call_state_handlers
    def cache_result(self, state: State, inputs: Dict[str, Result]) -> State:
        """
        Caches the result of a successful task, if appropriate.

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
        if (
            state.is_successful()
            and not state.is_skipped()
            and self.task.cache_for is not None
        ):
            expiration = pendulum.now("utc") + self.task.cache_for
            cached_state = Cached(
                result=state._result,
                cached_inputs=inputs,
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
            - inputs (Dict[str, Result], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            - State: the state of the task after running the check
        """
        if state.is_failed():
            run_count = prefect.context.get("task_run_count", 1)
            if run_count <= self.task.max_retries:
                start_time = pendulum.now("utc") + self.task.retry_delay
                msg = "Retrying Task (after attempt {n} of {m})".format(
                    n=run_count, m=self.task.max_retries + 1
                )
                retry_state = Retrying(
                    start_time=start_time,
                    cached_inputs=inputs,
                    message=msg,
                    run_count=run_count,
                )
                return retry_state

        return state

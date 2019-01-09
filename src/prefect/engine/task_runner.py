# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
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
    Sized,
    Tuple,
    Union,
)

import pendulum

import prefect
from prefect import config
from prefect.client.result_handlers import ResultHandler
from prefect.core import Edge, Task
from prefect.engine import signals
from prefect.engine.runner import ENDRUN, Runner, call_state_handlers
from prefect.engine.state import (
    CachedState,
    Failed,
    Mapped,
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


class TaskRunner(Runner):
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
    ):
        self.task = task
        self.result_handler = result_handler
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
        for handler in self.task.state_handlers:
            new_state = handler(self.task, old_state, new_state)

        return new_state

    def initialize_run(  # type: ignore
        self,
        state: Optional[State],
        context: Dict[str, Any],
        upstream_states: Dict[Edge, State],
        inputs: Dict[str, Any],
    ) -> Tuple[State, Dict[str, Any], Dict[Edge, State], Dict[str, Any]]:
        """
        Initializes the Task run by initializing state and context appropriately.

        If the task is being retried, then we retrieve the run count from the initial Retry
        state. Otherwise, we assume the run count is 1. The run count is stored in context as
        task_run_count.

        Also, if the task is being resumed through a `Resume` state, updates context to have `resume=True`.

        Args:
            - state (State): the proposed initial state of the flow run; can be `None`
            - context (Dict[str, Any]): the context to be updated with relevant information
            - upstream_states (Dict[Edge, State]): the upstream states
            - inputs (Dict[str, Any]): a dictionary of inputs to the task that should override
                the inputs taken from upstream states

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

        return state, context, upstream_states, inputs

    def run(
        self,
        state: State = None,
        upstream_states: Dict[Edge, State] = None,
        inputs: Dict[str, Any] = None,
        check_upstream: bool = True,
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
            - inputs (Dict[str, Any], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments. Any keys that are provided will override the
                `State`-based inputs provided in upstream_states.
            - check_upstream (bool): boolean specifying whether to check upstream states
                when deciding if the task should run. Defaults to `True`, but could be set to
                `False` to force the task to run.
            - context (dict, optional): prefect Context to use for execution
            - executor (Executor, optional): executor to use when performing
                computation; defaults to the executor specified in your prefect configuration

        Returns:
            - `State` object representing the final post-run state of the Task
        """
        upstream_states = upstream_states or {}
        inputs = inputs or {}
        context = context or {}
        map_index = context.setdefault("map_index", None)
        task_name = "{name}{index}".format(
            name=self.task.name,
            index=("" if map_index is None else "[{}]".format(map_index)),
        )

        task_inputs = {}  # type: Dict[str, Any]
        if executor is None:
            executor = prefect.engine.get_default_executor_class()()

        # if mapped is true, this task run is going to generate a Mapped state. It won't
        # actually run, but rather spawn children tasks to map over its inputs. We
        # detect this case by checking for:
        #   - upstream edges that are `mapped`
        #   - no `map_index` (which indicates that this is the child task, not the parent)
        mapped = any([e.mapped for e in upstream_states]) and map_index is None

        self.logger.info("Starting task run for task '{name}'".format(name=task_name))

        try:
            # initialize the run
            state, context, upstream_states, inputs = self.initialize_run(
                state, context, upstream_states, inputs
            )

            # run state transformation pipeline
            with prefect.context(context):

                # check to make sure the task is in a pending state
                state = self.check_task_is_pending(state)

                # check if the task has reached its scheduled time
                state = self.check_task_reached_start_time(state)

                # prepare this task to generate mapped children tasks
                if mapped:

                    if check_upstream:

                        # check if upstream tasks have all finished
                        state = self.check_upstream_finished(
                            state, upstream_states=upstream_states
                        )

                    # set the task state to running
                    state = self.set_task_to_running(state)

                    # kick off the mapped run
                    state = self.get_task_mapped_state(
                        state=state,
                        upstream_states=upstream_states,
                        inputs=inputs,
                        check_upstream=check_upstream,
                        context=prefect.context.to_dict(),
                        executor=executor,
                    )

                # run pipeline for a "normal" task
                else:

                    # if necessary, wait for any mapped upstream states to finish running
                    upstream_states = self.wait_for_mapped_upstream(
                        upstream_states=upstream_states, executor=executor
                    )

                    # retrieve task inputs from upstream and also explicitly passed inputs
                    # this must be run after the `wait_for_mapped_upstream` step
                    task_inputs = self.get_task_inputs(
                        upstream_states=upstream_states, inputs=inputs
                    )

                    if check_upstream:

                        # Tasks never run if the upstream tasks haven't finished
                        state = self.check_upstream_finished(
                            state, upstream_states=upstream_states
                        )

                        # check if any upstream tasks skipped (and if we need to skip)
                        state = self.check_upstream_skipped(
                            state, upstream_states=upstream_states
                        )

                        # check if the task's trigger passes
                        state = self.check_task_trigger(
                            state, upstream_states=upstream_states
                        )

                    # check to see if the task has a cached result
                    state = self.check_task_is_cached(state, inputs=task_inputs)

                    # set the task state to running
                    state = self.set_task_to_running(state)

                    # run the task
                    state = self.get_task_run_state(
                        state,
                        inputs=task_inputs,
                        timeout_handler=executor.timeout_handler,
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
            if prefect.context.get("raise_on_exception"):
                raise exc

        except Exception as exc:
            msg = "Unexpected error while running task: {}".format(str(exc))
            self.logger.info(msg)
            state = Failed(message=msg, result=exc)
            raise_on_exception = prefect.context.get("raise_on_exception", False)
            if raise_on_exception:
                raise exc

        self.logger.info(
            "Finished task run for task '{name}' with final state: '{state}'".format(
                name=task_name, state=type(state).__name__
            )
        )
        return state

    def wait_for_mapped_upstream(
        self,
        upstream_states: Dict[Edge, State],
        executor: "prefect.engine.executors.Executor",
    ) -> Dict[Edge, State]:
        """
        Waits until any upstream `Mapped` states have finished computing their results

        Args:
            - upstream_states (Dict[Edge, State]): the upstream states
            - executor (Executor): the executor

        Returns:
            - Dict[Edge, State]: the upstream states
        """

        for edge, upstream_state in upstream_states.items():

            # if the upstream state is Mapped, wait until its results are all available
            # note that this step is only called by tasks that are not Mapped themselves,
            # so this will not block after every mapped task (unless its result is needed).
            if not edge.mapped and upstream_state.is_mapped():
                assert isinstance(upstream_state, Mapped)  # mypy assert
                upstream_state.map_states = executor.wait(upstream_state.map_states)
                upstream_state.result = [s.result for s in upstream_state.map_states]

        return upstream_states

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

            self.logger.info(
                "{0} signal raised during execution of task '{1}'.".format(
                    type(exc).__name__, self.task.name
                )
            )
            if prefect.context.get("raise_on_exception"):
                raise exc
            raise ENDRUN(exc.state)

        # Exceptions are trapped and turned into TriggerFailed states
        except Exception as exc:
            self.logger.info(
                "Unexpected error while evaluating task trigger '{}'.".format(
                    self.task.name
                )
            )
            if prefect.context.get("raise_on_exception"):
                raise exc
            raise ENDRUN(
                TriggerFailed(
                    "Unexpected error while checking task trigger.", result=exc
                )
            )

        return state

    @call_state_handlers
    def check_task_is_pending(self, state: State) -> State:
        """
        Checks to make sure the task is in a PENDING state.

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

        # this task is already running
        elif state.is_running():
            self.logger.info("Task '{}' is already running.".format(self.task.name))
            raise ENDRUN(state)

        # this task is already finished
        elif state.is_finished():
            self.logger.info("Task '{}' is already finished.".format(self.task.name))
            raise ENDRUN(state)

        # this task is not pending
        else:
            self.logger.info(
                "Task '{0}' is not ready to run or state was unrecognized ({1}).".format(
                    self.task.name, state
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
            - State: the state of the task after running the task

        Raises:
            - ENDRUN: if the task is not a start task and Scheduled with a future
                scheduled time
        """
        if isinstance(state, Scheduled):
            if state.start_time and state.start_time > pendulum.now("utc"):
                raise ENDRUN(state)
        return state

    def get_task_inputs(
        self, upstream_states: Dict[Edge, State], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Given the upstream states and provided inputs, generates a task dictionary of
        inputs to this task.

        Args:
            - upstream_states (Dict[Edge, State]): the upstream states
            - inputs (Dict[str, Any]): any inputs that were explicitly provided to the task. These
                will override any inputs inferred from upstream states.

        Returns:
            - Dict[str, Any]: the task inputs

        """
        task_inputs = {}
        for edge, upstream_state in upstream_states.items():
            # construct task inputs
            if edge.key is not None:
                task_inputs[edge.key] = upstream_state.result

        task_inputs.update(inputs)
        return task_inputs

    @call_state_handlers
    def check_task_is_cached(self, state: State, inputs: Dict[str, Any]) -> State:
        """
        Checks if task is cached and whether the cache is still valid.

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Any]): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the task is not ready to run
        """
        if isinstance(state, CachedState) and self.task.cache_validator(
            state, inputs, prefect.context.get("parameters")
        ):
            raise ENDRUN(Success(result=state.cached_result, cached=state))
        return state

    @call_state_handlers
    def get_task_mapped_state(
        self,
        state: State,
        upstream_states: Dict[Edge, State],
        inputs: Dict[str, Any],
        check_upstream: bool,
        context: Dict[str, Any],
        executor: "prefect.engine.executors.Executor",
    ) -> State:
        """
        If the task is being mapped, sets the task to `Mapped` and submits children tasks
        for execution

        Args:
            - state (State): the current task state
            - upstream_states (Dict[Edge, State]): the upstream states
            - inputs (Dict[str, Any], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.
            - check_upstream (bool): boolean specifying whether to check upstream states
                when deciding if the task should run. Defaults to `True`, but could be set to
                `False` to force the task to run.
            - context (dict, optional): prefect Context to use for execution
            - executor (Executor): executor to use when performing computation

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the current state is not `Running`
        """

        if not state.is_running():
            raise ENDRUN(state)

        map_upstream_states = []

        # we don't know how long the iterables are, but we want to iterate until we reach
        # the end of the shortest one
        counter = itertools.count()
        while True:
            i = next(counter)
            i_states = {}

            try:

                for edge, upstream_state in upstream_states.items():

                    # if the edge is not mapped over, then we simply take its state
                    if not edge.mapped:
                        i_states[edge] = upstream_state

                    # if the edge is mapped and the upstream state is Mapped, then we are mapping
                    # over a mapped task. In this case, we take the appropriately-indexed upstream
                    # state from the upstream tasks's `Mapped.map_states` array.
                    # Note that these "states" might actually be futures at this time; we aren't
                    # blocking until they finish.
                    elif edge.mapped and upstream_state.is_mapped():
                        i_states[edge] = upstream_state.map_states[i]  # type: ignore

                    # Otherwise, we are mapping over the result of a "vanilla" task. In this
                    # case, we create a copy of the upstream state but set the result to the
                    # appropriately-indexed item from the upstream task's `State.result`
                    # array.
                    else:
                        i_states[edge] = copy.copy(upstream_state)
                        i_states[edge].result = upstream_state.result[i]  # type: ignore

                # only add this iteration if we made it through all iterables
                map_upstream_states.append(i_states)

            # index error means we reached the end of the shortest iterable
            except IndexError:
                break

        def run_fn(map_index: int, upstream_states: Dict[Edge, State]) -> State:
            context.update(map_index=map_index)
            return self.run(
                upstream_states=upstream_states,
                # if we set the state here, then it will not be processed by `initialize_run()`
                state=None,
                inputs=inputs,
                check_upstream=check_upstream,
                context=context,
                executor=executor,
            )

        # map over a counter representing the map_index and also the upstream states array
        map_states = executor.map(
            run_fn, range(len(map_upstream_states)), map_upstream_states
        )
        return Mapped(
            message="Mapped tasks submitted for execution.", map_states=map_states
        )

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
            raise ENDRUN(state)

        return Running(message="Starting task run.")

    @run_with_heartbeat
    @call_state_handlers
    def get_task_run_state(
        self, state: State, inputs: Dict[str, Any], timeout_handler: Optional[Callable]
    ) -> State:
        """
        Runs the task and traps any signals or errors it raises.

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Any], optional): a dictionary of inputs whose keys correspond
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
            raise ENDRUN(state)

        try:
            self.logger.info("Running task...")
            timeout_handler = timeout_handler or main_thread_timeout
            result = timeout_handler(self.task.run, timeout=self.task.timeout, **inputs)

        # inform user of timeout
        except TimeoutError as exc:
            if prefect.context.get("raise_on_exception"):
                raise exc
            return TimedOut(
                "Task timed out during execution.", result=exc, cached_inputs=inputs
            )

        return Success(result=result, message="Task run succeeded.")

    @call_state_handlers
    def cache_result(self, state: State, inputs: Dict[str, Any]) -> State:
        """
        Caches the result of a successful task, if appropriate.

        Tasks are cached if:
            - task.cache_for is not None
            - the task state is Successful
            - the task state is not Skipped (which is a subclass of Successful)

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Any], optional): a dictionary of inputs whose keys correspond
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
            cached_state = CachedState(
                cached_inputs=inputs,
                cached_result_expiration=expiration,
                cached_parameters=prefect.context.get("parameters"),
                cached_result=state.result,
            )
            return Success(
                result=state.result, message=state.message, cached=cached_state
            )

        return state

    @call_state_handlers
    def check_for_retry(self, state: State, inputs: Dict[str, Any]) -> State:
        """
        Checks to see if a FAILED task should be retried.

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Any], optional): a dictionary of inputs whose keys correspond
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
                return Retrying(
                    start_time=start_time,
                    cached_inputs=inputs,
                    message=msg,
                    run_count=run_count,
                )

        return state

# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
import collections
import copy
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

        Args:
            - state (State): the proposed initial state of the flow run; can be `None`
            - context (Dict[str, Any]): the context to be updated with relevant information
            - upstream_states (Dict[Edge, State]): the upstream states
            - inputs (Dict[str, Any]): a dictionary of inputs to the task that should override
                the inputs taken from upstream states

        Returns:
            - tuple: a tuple of the updated state, context, upstream_states, and inputs objects
        """
        context.update(task_name=self.task.name)
        state, context = super().initialize_run(state=state, context=context)
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
        if executor is None:
            executor = prefect.engine.get_default_executor_class()()
        self.executor = executor
        task_inputs = {}  # type: Dict[str, Any]

        # if mapped is true, this task run is going to generate a Mapped state. It won't
        # actually run, but rather spawn children tasks to map over its inputs. We detect
        # this case by checking for:
        #   - upstream edges that are `mapped`
        #   - no `map_index` in context (which indicates that this is the child task, not the
        #       parent)
        mapped = (
            any([e.mapped for e in upstream_states])
            and context.get("map_index") is None
        )

        self.logger.info(
            "Starting task run for task '{name}{index}'".format(
                name=self.task.name,
                index=(
                    ""
                    if context.get("map_index") is None
                    else "[{}]".format(context.get("map_index"))
                ),
            )
        )

        # if run fails to initialize, end the run
        try:
            state, context, upstream_states, inputs = self.initialize_run(
                state, context, upstream_states, inputs
            )
        except ENDRUN as exc:
            state = exc.state
            return state

        # run state transformation pipeline
        with prefect.context(context):

            try:

                # retrieve the run number and place in context,
                # or put resume in context if needed
                state = self.update_context_from_state(state=state)

                if not mapped:

                    # wait for mapped tasks to finish all sub-tasks, since we need their
                    # results
                    self.wait_for_upstream_mapped(
                        upstream_states=upstream_states, executor=executor
                    )

                    # construct task inputs
                    for edge, upstream_state in upstream_states.items():
                        if edge.key is not None:
                            if upstream_state.is_mapped():
                                task_inputs[edge.key] = [
                                    s.result
                                    for s in upstream_state.result  # type: ignore
                                ]
                            else:
                                task_inputs[edge.key] = upstream_state.result
                    task_inputs.update(inputs)

                # the upstream checks are only performed if `check_upstream is True` and
                # the task is not `mapped`. Mapped tasks do not actually do work, but spawn
                # dynamic tasks to map work across inputs. Therefore we defer upstream
                # checks to the dynamic tasks.
                if check_upstream and not mapped:
                    # check if all upstream tasks have finished
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
                # check to make sure the task is in a pending state
                state = self.check_task_is_pending(state)

                # check if the task has reached its scheduled time
                state = self.check_task_reached_start_time(state)

                # check to see if the task has a cached result
                state = self.check_task_is_cached(state, inputs=task_inputs)

                # set the task state to running
                state = self.set_task_to_running(state)

                # run the task!
                if not mapped:

                    state = self.get_task_run_state(
                        state,
                        inputs=task_inputs,
                        timeout_handler=executor.timeout_handler,
                    )

                    # cache the output, if appropriate
                    state = self.cache_result(state, inputs=task_inputs)

                    # check if the task needs to be retried
                    state = self.check_for_retry(state, inputs=task_inputs)

                # or, if the task is mapped, run the mapped tasks!
                else:
                    state = self.check_upstreams_for_mapping(
                        state=state, upstream_states=upstream_states
                    )
                    state = self.get_task_mapped_state(
                        upstream_states=upstream_states,
                        inputs=inputs,
                        check_upstream=check_upstream,
                        context=context,
                        executor=executor,
                    )

            # a ENDRUN signal at any point breaks the chain and we return
            # the most recently computed state
            except ENDRUN as exc:
                state = exc.state

            except signals.PAUSE as exc:
                state = exc.state
                state.cached_inputs = task_inputs or {}  # type: ignore

            except Exception as exc:
                state = Failed(
                    message="Unexpected error while running Task", result=exc
                )
                raise_on_exception = prefect.context.get("raise_on_exception", False)
                if raise_on_exception:
                    raise exc

            self.logger.info(
                "Finished task run for task '{name}{index}' with final state: '{state}'".format(
                    name=self.task.name,
                    index=(
                        ""
                        if context.get("map_index") is None
                        else "[{}]".format(context.get("map_index"))
                    ),
                    state=type(state).__name__,
                )
            )
        return state

    @call_state_handlers
    def update_context_from_state(self, state: State) -> State:
        """
        Updates context with information contained in the task state:

        If the task is being retried, then we retrieve the run count from the initial Retry
        state. Otherwise, we assume the run count is 1. The run count is stored in context as
        task_run_count.

        Also, if the task is being resumed through a `Resume` state, updates context to have `resume=True`.

        Args:
            - state (State): the current state of the task

        Returns:
            - State: the state of the task after running the check
        """
        if isinstance(state, Retrying):
            run_count = state.run_count + 1
        else:
            run_count = 1
        if isinstance(state, Resume):
            prefect.context.update(resume=True)
        prefect.context.update(task_run_count=run_count)
        return state

    @call_state_handlers
    def check_upstream_finished(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> State:
        """
        Checks if the upstream tasks have all finshed.

        Args:
            - state (State): the current state of this task
            - upstream_states (Dict[Edge, State]): the upstream states

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if upstream tasks are not finished.
        """
        if not all(s.is_finished() for s in upstream_states.values()):
            raise ENDRUN(state)
        return state

    def wait_for_upstream_mapped(
        self,
        upstream_states: Dict[Edge, State],
        executor: "prefect.engine.executors.Executor",
    ) -> None:
        """
        If the upstream states contain any mapped futures, this method will wait for the futures
        to complete and update the Mapped.result arrays with their results.

        Args:
            - upstream_states (Dict[Edge, State]): the upstream states
            - executor (Executor): the executor
        """
        for upstream_state in upstream_states.values():
            if upstream_state.is_mapped():
                upstream_state.map_states = executor.wait(upstream_state.map_states)
                upstream_state.result = [s.result for s in upstream_state.map_states]

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
        if self.task.skip_on_upstream_skip and any(
            s.is_skipped() for s in upstream_states.values()
        ):
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
            - upstream_states (Dict[Edge, State]): the upstream states

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the trigger raises an error
        """
        # the trigger itself could raise a failure, but we raise TriggerFailed just in case
        raise_on_exception = prefect.context.get("raise_on_exception", False)

        try:
            if not upstream_states:
                return state
            elif not self.task.trigger(upstream_states):
                raise signals.TRIGGERFAIL(message="Trigger failed")

        except signals.PAUSE:
            raise

        except signals.PrefectStateSignal as exc:
            self.logger.info(
                "{0} signal raised during execution of task '{1}'.".format(
                    type(exc).__name__, self.task.name
                )
            )
            if raise_on_exception:
                raise exc
            raise ENDRUN(exc.state)

        # Exceptions are trapped and turned into TriggerFailed states
        except Exception as exc:
            self.logger.info(
                "Unexpected error while running task '{}'.".format(self.task.name)
            )
            if raise_on_exception:
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
    def check_upstreams_for_mapping(
        self, state: State, upstream_states: Dict[Edge, State]
    ) -> State:
        """
        If the task is being mapped, checks if the upstream states are in a state
        to be mapped over.

        Args:
            - state (State): the current state of this task
            - upstream_states (Dict[Edge, State]): the upstream states

        Returns:
            - State: the state of the task after running the check

        Raises:
            - ENDRUN: if the task is not ready to be mapped
        """
        if not state.is_running():
            raise ENDRUN(state)

        mapped_upstreams = [val for e, val in upstream_states.items() if e.mapped]

        ## no inputs provided
        if not mapped_upstreams:
            raise ENDRUN(
                state=Skipped(message="No inputs provided to map over.", result=[])
            )

        iterable_values = []
        for value in mapped_upstreams:
            underlying = value if not isinstance(value, State) else value.result
            # if we are on the second stage of mapping, the upstream "states"
            # are going to be non-iterable futures representing lists of states;
            # this allows us to skip if any upstreams are known to be empty
            if isinstance(underlying, collections.abc.Sized):
                iterable_values.append(underlying)

        ## check that no upstream values are empty
        if any([len(v) == 0 for v in iterable_values]):
            raise ENDRUN(
                state=Skipped(message="Empty inputs provided to map over.", result=[])
            )

        return state

    def get_task_mapped_state(
        self,
        upstream_states: Dict[Edge, State],
        inputs: Dict[str, Any],
        check_upstream: bool,
        context: Dict[str, Any],
        executor: "prefect.engine.executors.Executor",
    ) -> State:
        """
        If the task is being mapped, sets the task to `Mapped`

        Args:
            - state (State): the current state of this task
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
        """

        # we can only iterate over the SHORTEST available iterator (similar to how zip() works).
        # we compute the number of maps as the minimum iterator length
        state_lengths = [
            len(s.result)  # type: ignore
            for e, s in upstream_states.items()
            if e.mapped
        ]
        n_maps = min(state_lengths or [0])

        map_upstream_states = []
        for i in range(n_maps):
            i_states = upstream_states.copy()
            for edge, upstream_state in upstream_states.items():

                # if the edge is mapped and the state is Mapped, then we are mapping
                # over a task that was, itself, mapped. We simply grab the appropriately
                # indexed state from the list.
                if edge.mapped and upstream_state.is_mapped():
                    i_states[edge] = upstream_state.result[i]  # type: ignore

                # if the edge is mapped but the state is a single State, then we are mapping
                # over the result of a "vanilla" task. We create a copy of the parent state and
                # set its result to the appropriately indexed parent result
                elif edge.mapped:
                    i_states[edge] = copy.copy(upstream_state)
                    i_states[edge].result = upstream_state.result[i]  # type: ignore

                # otherwise, we're not mapping over the task and we should just use its
                # state as given.
                else:
                    i_states[edge] = upstream_state
            map_upstream_states.append(i_states)

        def run_fn(map_index: int, upstream_states: Dict[Edge, State]) -> State:
            context.update(map_index=map_index)
            return self.run(
                upstream_states=upstream_states,
                state=None,  # Pending("Child task."),  # will need to revisit this
                inputs=inputs,
                check_upstream=check_upstream,
                context=context,
                executor=executor,
            )

        map_states = executor.map(run_fn, range(n_maps), map_upstream_states)
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

        raise_on_exception = prefect.context.get("raise_on_exception", False)

        try:
            self.logger.info("Running task...")
            timeout_handler = timeout_handler or main_thread_timeout
            result = timeout_handler(self.task.run, timeout=self.task.timeout, **inputs)

        except signals.PAUSE:
            raise

        # PrefectStateSignals are trapped and turned into States
        except signals.PrefectStateSignal as exc:
            self.logger.info("{} signal raised.".format(type(exc).__name__))
            if raise_on_exception:
                raise exc
            return exc.state

        # inform user of timeout
        except TimeoutError as exc:
            if raise_on_exception:
                raise exc
            return TimedOut(
                "Task timed out during execution.", result=exc, cached_inputs=inputs
            )

        # Exceptions are trapped and turned into Failed states
        except Exception as exc:
            self.logger.info("Unexpected error while running task.")
            if raise_on_exception:
                raise exc
            return Failed("Unexpected error while running task.", result=exc)

        return Success(result=result, message="Task run succeeded.")

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

# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import collections
import datetime
import functools
import logging
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterable, List, Union, Set, Optional

import prefect
from prefect.core import Edge, Task
from prefect.engine import signals
from prefect.engine.state import (
    CachedState,
    Failed,
    Pending,
    Retrying,
    Running,
    Skipped,
    State,
    Success,
    TriggerFailed,
)
from prefect.utilities.executors import main_thread_timeout


class ENDRUN(Exception):
    """
    An ENDRUN exception is used by TaskRunner steps to indicate that state processing should
    stop. The pipeline result should be the state contained in the exception.
    """

    def __init__(self, state: State = None) -> None:
        """
        Args
            - state (State): the state that should be used as the result of the TaskRunner
                run.
        """
        self.state = state
        super().__init__()


def call_state_handlers(method: Callable[..., State]) -> Callable[..., State]:
    """
    Decorator that calls the TaskRunner's state_handlers method if a run step
    results in a modified state.
    """

    @functools.wraps(method)
    def inner(self: "TaskRunner", state: State, *args: Any, **kwargs: Any) -> State:
        new_state = method(self, state, *args, **kwargs)
        if new_state is state:
            return new_state
        else:
            return self.handle_state_change(old_state=state, new_state=new_state)

    return inner


class TaskRunner:
    """
    TaskRunners handle the execution of Tasks and determine the State of a Task
    before, during and after the Task is run.

    In particular, through the TaskRunner you can specify the states of any upstream dependencies,
    any inputs required for this Task to run, and what state the Task should be initialized with.

    Args:
        - task (Task): the Task to be run / executed
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
        - logger_name (str): Optional. The name of the logger to use when
            logging. Defaults to the name of the class.
    """

    def __init__(
        self,
        task: Task,
        state_handlers: Iterable[Callable] = None,
        logger_name: str = None,
    ) -> None:
        self.task = task
        if state_handlers and not isinstance(state_handlers, collections.Sequence):
            raise TypeError("state_handlers should be iterable.")
        self.state_handlers = state_handlers or []
        self.logger = logging.getLogger(logger_name or type(self).__name__)

    def handle_state_change(self, old_state: State, new_state: State) -> State:
        """
        Calls any handlers associated with the TaskRunner and Task.

        This method will only be called when the state changes (`old_state is not new_state`)

        Args:
            - old_state (State): the old (previous) state of the task
            - new_state (State): the new (current) state of the task

        Returns:
            State: the updated state of the task

        Raises:
            - PAUSE: if raised by a handler
            - ENDRUN(Failed()): if any of the handlers fail

        """
        raise_on_exception = prefect.context.get("_raise_on_exception", False)

        # run the task's handlers first
        try:
            for task_handler in self.task.state_handlers:
                new_state = task_handler(self.task, old_state, new_state)

            for runner_handler in self.state_handlers:
                new_state = runner_handler(self, old_state, new_state)

        # raise pauses
        except prefect.engine.signals.PAUSE:
            raise
        # trap signals
        except signals.PrefectStateSignal as exc:
            if raise_on_exception:
                raise
            return exc.state
        # abort on errors
        except Exception as exc:
            if raise_on_exception:
                raise
            raise ENDRUN(
                Failed("Exception raised while calling state handlers.", message=exc)
            )
        return new_state

    def run(
        self,
        state: State = None,
        upstream_states: Dict[Edge, Union[State, List[State]]] = None,
        inputs: Dict[str, Any] = None,
        ignore_trigger: bool = False,
        context: Dict[str, Any] = None,
        queues: Iterable = None,
        timeout_handler: Callable = None,
    ) -> State:
        """
        The main endpoint for TaskRunners.  Calling this method will conditionally execute
        `self.task.run` with any provided inputs, assuming the upstream dependencies are in a
        state which allow this Task to run.

        Args:
            - state (State, optional): initial `State` to begin task run from;
                defaults to `Pending()`
            - upstream_states (Dict[Edge, Union[State, List[State]]]): a dictionary
                representing the states of any tasks upstream of this one. The keys of the
                dictionary should correspond to the edges leading to the task.
            - inputs (Dict[str, Any], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments. Any keys that are provided will override the
                `State`-based inputs provided in upstream_states.
            - ignore_trigger (bool): boolean specifying whether to ignore the
                Task trigger; defaults to `False`
            - context (dict, optional): prefect Context to use for execution
            - queues ([queue], optional): list of queues of tickets to use when deciding
                whether it's safe for the Task to run based on resource limitations. The
                Task will only begin running when a ticket from each queue is available.
            - timeout_handler (Callable, optional): function for timing out
                task execution, with call signature `handler(fn, *args, **kwargs)`. Defaults to
                `prefect.utilities.executors.main_thread_timeout`

        Returns:
            - `State` object representing the final post-run state of the Task
        """

        queues = queues or []
        state = state or Pending()
        upstream_states = upstream_states or {}
        inputs = inputs or {}
        context = context or {}

        # construct task inputs
        task_inputs = {}
        for edge, v in upstream_states.items():
            if edge.key is None:
                continue
            if isinstance(v, list):
                task_inputs[edge.key] = [s.result for s in v]
            else:
                task_inputs[edge.key] = v.result
        task_inputs.update(inputs)

        # gather upstream states
        upstream_states_set = set(
            prefect.utilities.collections.flatten_seq(upstream_states.values())
        )

        # apply throttling
        while True:
            tickets = []
            for q in queues:
                try:
                    tickets.append(q.get(timeout=2))  # timeout after 2 seconds
                except Exception:
                    for ticket, q in zip(tickets, queues):
                        q.put(ticket)
            if len(tickets) == len(queues):
                break

        # run state transformation pipeline
        with prefect.context(context, _task_name=self.task.name):

            try:
                # check if all upstream tasks have finished
                state = self.check_upstream_finished(
                    state, upstream_states_set=upstream_states_set
                )

                # check if any upstream tasks skipped (and if we need to skip)
                state = self.check_upstream_skipped(
                    state, upstream_states_set=upstream_states_set
                )

                # check if the task's trigger passes
                state = self.check_task_trigger(
                    state,
                    upstream_states_set=upstream_states_set,
                    ignore_trigger=ignore_trigger,
                )

                # check to make sure the task is in a pending state
                state = self.check_task_is_pending(state)

                # check to see if the task has a cached result
                state = self.check_task_is_cached(state, inputs=task_inputs)

                # set the task state to running
                state = self.set_task_to_running(state)

                # run the task!
                state = self.run_task(
                    state, inputs=task_inputs, timeout_handler=timeout_handler
                )

                # cache the output, if appropriate
                state = self.cache_result(state, inputs=task_inputs)

                # check if the task needs to be retried
                state = self.check_for_retry(state, inputs=task_inputs)

            # a ENDRUN signal at any point breaks the chain and we return
            # the most recently computed state
            except ENDRUN as exc:
                state = exc.state

            except signals.PAUSE as exc:
                state.cached_inputs = task_inputs or {}
                state.message = exc

            finally:  # resource is now available
                for ticket, q in zip(tickets, queues):
                    q.put(ticket)

        return state

    @call_state_handlers
    def check_upstream_finished(
        self, state: State, upstream_states_set: Set[State]
    ) -> State:
        """
        Checks if the upstream tasks have all finshed.

        Args:
            - state (State): the current state of this task
            - upstream_states_set: a set containing the states of any upstream tasks.

        Returns:
            State: the state of the task after running the check

        Raises:
            - signals.ENDRUN: if upstream tasks are not finished.
        """
        if not all(s.is_finished() for s in upstream_states_set):
            raise ENDRUN(state)
        return state

    @call_state_handlers
    def check_upstream_skipped(
        self, state: State, upstream_states_set: Set[State]
    ) -> State:
        """
        Checks if any of the upstream tasks have skipped.

        Args:
            - state (State): the current state of this task
            - upstream_states_set: a set containing the states of any upstream tasks.

        Returns:
            State: the state of the task after running the check
        """
        if self.task.skip_on_upstream_skip and any(
            isinstance(s, Skipped) for s in upstream_states_set
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
        self,
        state: State,
        upstream_states_set: Set[State],
        ignore_trigger: bool = False,
    ) -> State:
        """
        Checks if the task's trigger function passes. If the upstream_states_set is empty,
        then the trigger is not called.

        Args:
            - state (State): the current state of this task
            - upstream_states_set (Set[State]): a set containing the states of any upstream tasks.
            - ignore_trigger (bool): a boolean indicating whether to ignore the
                tasks's trigger

        Returns:
            State: the state of the task after running the check

        Raises:
            - signals.ENDRUN: if the trigger raises DONTRUN
        """
        # the trigger itself could raise a failure, but we raise TriggerFailed just in case
        raise_on_exception = prefect.context.get("_raise_on_exception", False)

        try:
            if not upstream_states_set:
                return state
            elif not ignore_trigger and not self.task.trigger(upstream_states_set):
                raise signals.TRIGGERFAIL(message="Trigger failed")

        except signals.PAUSE:
            raise

        except signals.PrefectStateSignal as exc:
            logging.debug("{} signal raised.".format(type(exc).__name__))
            if raise_on_exception:
                raise exc
            raise ENDRUN(exc.state)

        # Exceptions are trapped and turned into TriggerFailed states
        except Exception as exc:
            logging.debug("Unexpected error while running task.")
            if raise_on_exception:
                raise exc
            raise ENDRUN(TriggerFailed(message=exc))

        return state

    @call_state_handlers
    def check_task_is_pending(self, state: State) -> State:
        """
        Checks to make sure the task is in a PENDING state.

        Args:
            - state (State): the current state of this task

        Returns:
            State: the state of the task after running the check

        Raises:
            - signals.ENDRUN: if the task is not ready to run
        """
        # the task is ready
        if state.is_pending():
            return state

        # this task is already running
        elif state.is_running():
            self.logger.debug("Task is already running.")
            raise ENDRUN(state)

        # this task is already finished
        elif state.is_finished():
            self.logger.debug("Task is already finished.")
            raise ENDRUN(state)

        # this task is not pending
        else:
            self.logger.debug(
                "Task is not ready to run or state was unrecognized ({}).".format(state)
            )
            raise ENDRUN(state)

    @call_state_handlers
    def check_task_is_cached(self, state: State, inputs: Dict[str, Any]) -> State:
        """
        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Any], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            State: the state of the task after running the check

        Raises:
            - signals.ENDRUN: if the task is not ready to run
        """
        if isinstance(state, CachedState) and self.task.cache_validator(
            state, inputs, prefect.context.get("_parameters")
        ):
            raise ENDRUN(Success(result=state.cached_result, cached=state))
        return state

    @call_state_handlers
    def set_task_to_running(self, state: State) -> State:
        """
        Sets the task to running

        Args:
            - state (State): the current state of this task

        Returns:
            State: the state of the task after running the check

        Raises:
            - signals.ENDRUN: if the task is not ready to run
        """
        if not state.is_pending():
            raise ENDRUN(state)

        return Running(message="Starting task run.")

    @call_state_handlers
    def run_task(
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
            State: the state of the task after running the check

        Raises:
            - signals.PAUSE: if the task raises PAUSE
            - signals.ENDRUN: if the task is not ready to run
        """
        if not state.is_running():
            raise ENDRUN(state)

        raise_on_exception = prefect.context.get("_raise_on_exception", False)

        try:
            timeout_handler = timeout_handler or main_thread_timeout
            result = timeout_handler(self.task.run, timeout=self.task.timeout, **inputs)

        except signals.DONTRUN:
            return Skipped()

        except signals.PAUSE:
            raise

        # PrefectStateSignals are trapped and turned into States
        except signals.PrefectStateSignal as exc:
            logging.debug("{} signal raised.".format(type(exc).__name__))
            if raise_on_exception:
                raise exc
            return exc.state

        # Exceptions are trapped and turned into Failed states
        except Exception as exc:
            logging.debug("Unexpected error while running task.")
            if raise_on_exception:
                raise exc
            return Failed(message=exc)

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
            State: the state of the task after running the check

        """
        if (
            state.is_successful()
            and not isinstance(state, Skipped)
            and self.task.cache_for is not None
        ):
            expiration = datetime.datetime.utcnow() + self.task.cache_for
            cached_state = CachedState(
                cached_inputs=inputs,
                cached_result_expiration=expiration,
                cached_parameters=prefect.context.get("_parameters"),
                cached_result=state.result,
            )
            return Success(
                result=state.result, message=state.message, cached=cached_state
            )

        return state

    @call_state_handlers
    def check_for_retry(self, state: State, inputs: Dict[str, Any]) -> State:
        """
        Checks to see if a FAILED task should be retried. Also assigns a retry time to
        RETRYING states that don't have one set (for example, if raised from inside a task).

        Args:
            - state (State): the current state of this task
            - inputs (Dict[str, Any], optional): a dictionary of inputs whose keys correspond
                to the task's `run()` arguments.

        Returns:
            State: the state of the task after running the check
        """
        if state.is_failed() or (
            isinstance(state, Retrying) and state.scheduled_time is None
        ):
            run_number = prefect.context.get("_task_run_number", 1)
            if run_number <= self.task.max_retries or isinstance(state, Retrying):
                scheduled_time = datetime.datetime.utcnow() + self.task.retry_delay
                msg = "Retrying Task (after attempt {n} of {m})".format(
                    n=run_number, m=self.task.max_retries + 1
                )
                return Retrying(
                    scheduled_time=scheduled_time, cached_inputs=inputs, message=msg
                )

        return state

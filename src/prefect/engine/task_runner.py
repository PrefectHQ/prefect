import datetime
import functools
import logging
import types
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, MutableMapping, Union

import prefect
from prefect.core import Task
from prefect.engine import signals
from prefect.engine.state import (
    CachedState,
    Failed,
    MessageType,
    Pending,
    Retrying,
    Running,
    Skipped,
    State,
    Success,
    TriggerFailed,
)


def handle_signals(method: Callable[..., State]) -> Callable[..., State]:
    """
    This handler is used to decorate methods that return States but might raise
    Prefect signals.

    The handler attempts to run the method, and if a signal is raised, the appropriate
    state is returned.

    If DONTRUN is raised, the handler does not trap it, but re-raises it.
    """

    @functools.wraps(method)
    def inner(self: "TaskRunner", *args: Any, **kwargs: Any) -> State:

        raise_on_exception = prefect.context.get("_raise_on_exception", False)

        try:
            return method(self, *args, **kwargs)

        # DONTRUN signals get raised for handling
        except signals.DONTRUN as exc:
            logging.debug("DONTRUN signal raised: {}".format(exc))
            raise

        # RETRY signals are trapped and turned into Retry states
        except signals.RETRY as exc:
            logging.debug("RETRY signal raised")
            if raise_on_exception:
                raise exc
            return self.get_retry_state(inputs=kwargs.get("inputs"))

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

    return inner


class TaskRunner:
    def __init__(self, task: Task, logger_name: str = None) -> None:
        self.task = task
        self.logger = logging.getLogger(logger_name or type(self).__name__)

    def run(
        self,
        state: State = None,
        upstream_states: Dict[Task, State] = None,
        inputs: Dict[str, Any] = None,
        ignore_trigger: bool = False,
        context: Dict[str, Any] = None,
    ) -> State:

        state = state or Pending()
        context = context or {}

        with prefect.context(context, _task_name=self.task.name):
            try:
                parameters = prefect.context.get("_parameters")
                state = self.get_pre_run_state(
                    state=state,
                    upstream_states=upstream_states,
                    ignore_trigger=ignore_trigger,
                    inputs=inputs,
                    parameters=parameters,
                )
                state = self.get_run_state(state=state, inputs=inputs)
                state = self.get_post_run_state(state=state, inputs=inputs)

            # a DONTRUN signal at any point breaks the chain and we return
            # the most recently computed state
            except signals.DONTRUN as exc:
                if "manual_only" in str(exc):
                    state.cached_inputs = inputs or {}
                pass

        return state

    @handle_signals
    def get_pre_run_state(
        self,
        state: State,
        upstream_states: Dict[Task, State] = None,
        ignore_trigger: bool = False,
        inputs: Dict[str, Any] = None,
        parameters: Dict[str, Any] = None,
    ) -> State:
        """
        Checks if a task is ready to run.

        This method accepts an initial state and returns the next state that the task
        should take. If it should not change state, it returns None.
        """
        upstream_states = upstream_states or {}

        # ---------------------------------------------------------
        # check upstream tasks
        # ---------------------------------------------------------

        # make sure all upstream tasks are finished
        if not all(s.is_finished() for s in upstream_states.values()):
            raise signals.DONTRUN("Upstream tasks are not finished.")

        # ---------------------------------------------------------
        # check upstream skips and propagate if appropriate
        # ---------------------------------------------------------

        if self.task.propagate_skip and any(
            isinstance(s, Skipped) for s in upstream_states.values()
        ):
            return Skipped(message="Upstream task was skipped.")

        # ---------------------------------------------------------
        # check trigger
        # ---------------------------------------------------------

        # the trigger itself could raise a failure, but we raise TriggerFailed just in case
        if not ignore_trigger and not self.task.trigger(upstream_states):
            raise signals.TRIGGERFAIL(message="Trigger failed.")

        # ---------------------------------------------------------
        # check this task's state
        # ---------------------------------------------------------

        # this task is already running
        elif state.is_running():
            raise signals.DONTRUN("Task is already running.")

        # this task is already finished
        elif state.is_finished():
            raise signals.DONTRUN("Task is already finished.")

        # this task is not pending
        elif not state.is_pending():
            raise signals.DONTRUN(
                "Task is not ready to run or state was unrecognized ({}).".format(state)
            )

        # ---------------------------------------------------------
        # We can start!
        # ---------------------------------------------------------
        if isinstance(state, CachedState) and self.task.cache_validator(
            state, inputs, parameters
        ):
            return Success(result=state.cached_outputs)

        return Running(message="Starting task run")

    @handle_signals
    def get_run_state(self, state: State, inputs: Dict[str, Any] = None) -> State:
        """
        Runs a task.

        This method accepts an initial state and returns the next state that the task
        should take. If it should not change state, it returns None.
        """

        inputs = inputs or {}

        if not state.is_running():
            raise signals.DONTRUN("Task is not in a Running state.")

        try:
            self.logger.debug("Starting TaskRun")
            result = self.task.run(**inputs)  # type: ignore
        except signals.DONTRUN as exc:
            raise signals.SKIP(
                message="DONTRUN was raised inside a task and interpreted as SKIP. "
                "Message was: {}".format(str(exc))
            )

        return Success(result=result, message="Task run succeeded.")

    @handle_signals
    def get_post_run_state(self, state: State, inputs: Dict[str, Any] = None) -> State:
        """
        If the final state failed, this method checks to see if it should be retried.
        """
        if not state.is_finished():
            raise signals.DONTRUN("Task is not in a Finished state.")

        # check failed states for retry (except for TriggerFailed, which doesn't retry)
        if isinstance(state, Failed) and not isinstance(state, TriggerFailed):
            run_number = prefect.context.get("_task_run_number", 1)
            if run_number <= self.task.max_retries:
                return self.get_retry_state(inputs=inputs)

        raise signals.DONTRUN("State requires no further processing.")

    def get_retry_state(self, inputs: Dict[str, Any] = None) -> State:
        """
        Returns a Retry state with the appropriate scheduled_time and last_run_number set.
        """
        run_number = prefect.context.get("_task_run_number", 1)
        scheduled_time = datetime.datetime.utcnow() + self.task.retry_delay
        msg = "Retrying Task (after attempt {n} of {m})".format(
            n=run_number, m=self.task.max_retries + 1
        )
        self.logger.info(msg)
        return Retrying(
            scheduled_time=scheduled_time, cached_inputs=inputs, message=msg
        )

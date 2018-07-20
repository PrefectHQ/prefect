import datetime
import logging
import types
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, MutableMapping, Union

import prefect
from prefect import signals
from prefect.core import Task
from prefect.engine.state import (
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


def handle_signals(method: Callable) -> Callable:
    """
    This handler is used to decorate methods that return States but might raise
    Prefect signals.

    The handler attempts to run the method, and if a signal is raised, the appropriate
    state is returned.

    If DONTRUN is raised, the handler returns None to indicate there is no state change.
    """

    def inner(self, *args, **kwargs) -> State:

        raise_on_fail = prefect.context.get("_raise_on_fail", False)

        try:
            return method(self, *args, **kwargs)

        except signals.DONTRUN as exc:
            logging.debug("DONTRUN signal raised: {}".format(exc))
            return None

        except signals.SUCCESS as exc:
            logging.debug("SUCCESS signal raised.")
            return Success(data=exc.result, message=exc)

        except signals.TRIGGERFAIL as exc:
            logging.debug("TRIGGERFAIL signal raised.")
            if raise_on_fail:
                raise exc
            return TriggerFailed(data=exc.result, message=exc)

        except signals.FAIL as exc:
            logging.debug("FAIL signal raised.")
            if raise_on_fail:
                raise exc
            return self.retry_or_fail(data=exc.result, message=exc)

        except signals.RETRY:
            # raising a retry signal always retries, no matter what "max retries" is set to
            logging.debug("RETRY signal raised.")
            return self.retry_or_fail(force_retry=True)

        except signals.SKIP as exc:
            logging.debug("SKIP signal raised.")
            return Skipped(data=exc.result, message=exc)

        except Exception as exc:
            logging.debug("Unexpected error while running task.")
            if raise_on_fail:
                raise exc
            return self.retry_or_fail(message=exc)

    return inner


class TaskRunner:
    def __init__(self, task: Task, logger_name: str = None) -> None:
        self.task = task
        self.logger = logging.getLogger(logger_name)

    @contextmanager
    def task_context(self, **kwargs: Any) -> Iterator[None]:
        with prefect.context(_task_name=self.task.name, **kwargs):
            yield

    def run(
        self,
        state: State = None,
        upstream_states: Dict[Task, State] = None,
        inputs: Dict[str, Any] = None,
        ignore_trigger: bool = False,
    ) -> State:
        state = state or Pending()

        checked_state = self._check_state(
            state=state,
            upstream_states=upstream_states or {},
            ignore_trigger=ignore_trigger,
        )
        if not checked_state:
            return state

        final_state = self._run_task(state=checked_state, inputs=inputs or {})
        if not final_state:
            return checked_state

        return final_state

    @handle_signals
    def _check_state(
        self,
        state: State,
        upstream_states: Dict[Task, State],
        ignore_trigger: bool = False,
    ) -> State:
        """
        Checks if a task is ready to run.

        This method accepts an initial state and returns the next state that the task
        should take. If it should not change state, it returns None.
        """
        with self.task_context():
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

            # triggers should return True or raise a signal, but just in case we raise
            # trigger failed here
            if not ignore_trigger and not self.task.trigger(upstream_states):
                return TriggerFailed(message="Trigger failed.")

            # ---------------------------------------------------------
            # check this task's state
            # ---------------------------------------------------------

            # state is missing
            if not state:
                raise signals.DONTRUN("Missing State.")

            # this task is already running
            elif state.is_running():
                raise signals.DONTRUN("Task is already running.")

            # this task is already finished
            elif state.is_finished():
                raise signals.DONTRUN("Task is already finished.")

            # this task is not pending
            elif not state.is_pending():
                raise signals.DONTRUN(
                    "Task is not ready to run (state is {}).".format(state)
                )

            # ---------------------------------------------------------
            # We can start!
            # ---------------------------------------------------------

            return Running()

    @handle_signals
    def _run_task(self, state: State, inputs: Dict[str, Any] = None) -> State:
        """
        Runs a task.

        This method accepts an initial state and returns the next state that the task
        should take. If it should not change state, it returns None.
        """

        if not state.is_running():
            raise signals.DONTRUN("Task is not in a running state.")

        try:
            self.logger.debug("Starting TaskRun")
            result = self.task.run(**inputs)  # type: ignore
        except signals.DONTRUN as exc:
            return Skipped(
                message="DONTRUN was raised inside a task and interpreted as SKIP. "
                "Message was: {}".format(str(exc))
            )

        return Success(data=result, message="Task run succeeded.")

    def retry_or_fail(
        self, data: Any = None, message: MessageType = None, force_retry: bool = False
    ) -> State:
        # TODO exponential backoff based on run_number
        # run_number = prefect.context.get('_task_run_number', 0)

        run_number = prefect.context.get("_task_run_number", 1)
        if force_retry or run_number <= self.task.max_retries:
            msg = "Retrying Task (after attempt {n} of {m})".format(
                n=run_number, m=self.task.max_retries + 1
            )
            self.logger.info(msg)
            retry_time = datetime.datetime.utcnow() + self.task.retry_delay
            return Retrying(
                data=dict(retry_time=retry_time, last_run_number=run_number),
                message=msg,
            )
        else:
            return Failed(data=data, message=message)

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
    Decorator that attempts to call a method that returns a State and traps any
    exceptions it raises, including Prefect signals. If a signal is raised, the
    decorator returns an appropriate State class.
    """

    def inner(self, *args, **kwargs) -> Union[State, None]:

        state = None
        raise_on_fail = prefect.context.get("_raise_on_fail", False)

        try:
            state = method(self, *args, **kwargs)

        except signals.DONTRUN as exc:
            logging.debug("DONTRUN signal raised: {}".format(exc))

        except signals.SUCCESS as exc:
            logging.debug("SUCCESS signal raised.")
            state = Success(data=exc.result, message=exc)

        except signals.TRIGGERFAIL as exc:
            logging.debug("TRIGGERFAIL signal raised.")
            state = TriggerFailed(data=exc.result, message=exc)
            if raise_on_fail:
                raise exc

        except signals.FAIL as exc:
            logging.debug("FAIL signal raised.")
            state = self.retry_or_fail(data=exc.result, message=exc)
            if raise_on_fail:
                raise exc

        except signals.RETRY:
            # raising a retry signal always retries, no matter what "max retries" is set to
            logging.debug("RETRY signal raised.")
            state = self.retry_or_fail(force_retry=True)

        except signals.SKIP as exc:
            logging.debug("SKIP signal raised.")
            state = Skipped(data=exc.result, message=exc)

        except Exception as exc:
            logging.debug("Unexpected error while running task.")
            state = self.retry_or_fail(message=exc)
            if raise_on_fail:
                raise exc

        return state

    return inner


class TaskRunner:
    def __init__(self, task: Task, logger_name: str = None) -> None:
        self.task = task
        self.logger = logging.getLogger(logger_name)

    def run(
        self,
        state: State = None,
        upstream_states: Dict[Task, State] = None,
        inputs: Dict[str, Any] = None,
        ignore_trigger: bool = False,
    ) -> State:
        initial_state = state or Pending()

        checked_state = self.check_task(
            state=initial_state,
            upstream_states=upstream_states or {},
            ignore_trigger=ignore_trigger,
        )

        if not checked_state:
            return initial_state

        final_state = self.run_task(state=checked_state, inputs=inputs or {})

        if not final_state:
            return checked_state

        return final_state

    @handle_signals
    def check_task(
        self,
        state: State,
        upstream_states: Dict[Task, State],
        ignore_trigger: bool = False,
    ) -> Union[State, None]:
        """
        Checks if a task is ready to run.

        Returns either a new state for the task or None if the state should not change.
        """

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
    def run_task(
        self, state: State, inputs: Dict[str, Any] = None
    ) -> Union[State, None]:
        """
        Runs a task.

        Returns either a new state for the task or None if the task state should not change.
        """

        if not state or not state.is_running():
            raise signals.DONTRUN("Task is not running.")

        self.logger.debug("Starting TaskRun")

        result = self.task.run(**inputs)  # type: ignore

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

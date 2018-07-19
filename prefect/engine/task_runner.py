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


class TaskRunner:
    def __init__(self, task: Task, logger_name: str = None) -> None:
        self.task = task
        self.logger = logging.getLogger(logger_name)

    @contextmanager
    def handle_signals(self, context: MutableMapping = None) -> Iterator[Callable]:
        """
        This context manager traps Prefect Signals and creates the appropriate state objects.

        However, context managers can't return objects that are created after the
        context manager yields. Therefore, this context manager yields a function that can
        be called after the context manager has been exited. The function will return any
        state objects created by the context manager (or None, in the case of no new state).
        """
        context_exited = False
        state = None

        def trapped_state_handler() -> Union[State, None]:
            """
            Returns the state object that is created in this context manager.
            """
            if not context_exited:
                raise ValueError(
                    'The state handler was called while the handle_signals() context was '
                    'still open. Wait to call this function until after the context has been '
                    'exited.')
            return state

        with prefect.context(context or {}):
            try:
                yield trapped_state_handler

            except signals.DONTRUN as e:
                logging.debug("DONTRUN signal raised: {}".format(e))

            except signals.SUCCESS as e:
                logging.debug("SUCCESS signal raised.")
                state = Success(data=e.result, message=e)

            except signals.TRIGGERFAIL as e:
                logging.debug("TRIGGERFAIL signal raised.")
                state = TriggerFailed(data=e.result, message=e)

            except signals.FAIL as e:
                logging.debug("FAIL signal raised.")
                state = self.retry_or_fail(data=e.result, message=e)

            except signals.RETRY:
                # raising a retry signal always retries, no matter what "max retries" is set to
                logging.debug("RETRY signal raised.")
                state = self.retry_or_fail(force_retry=True)

            except signals.SKIP:
                logging.debug("SKIP signal raised.")
                state = Skipped(data=e.result, message=e)

            except Exception as e:
                logging.debug("Unexpected error while running task.")
                state = self.retry_or_fail(message=e)

            finally:
                context_exited = True

    def check_task(
        self,
        state: State,
        upstream_states: Dict[Task, State],
        ignore_trigger: bool = False,
        context: Dict[str, Any] = None,
    ) -> Union[State, None]:
        """
        Checks if a task is ready to run.

        Returns either a new state for the task or None if the state should not change.
        """

        with self.handle_signals(context=context) as trapped_state_handler:

            # prepare context
            context.update(
                _task_name=self.task.name,
                _task_max_retries=self.task.max_retries,
                _task_run_upstream_states=upstream_states,
            )

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

            # this task is already running
            if state.is_running():
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

        # ---------------------------------------------------------
        # If we reach this point, it means a signal was raised and must be
        # retrieved from the handler function
        # ---------------------------------------------------------

        return trapped_state_handler()

    def run_task(
        self,
        state: State,
        inputs: Dict[str, Any] = None,
        context: Dict[str, Any] = None,
    ) -> State:

        if not state.is_running():
            return state

        with self.handle_signals(context=context) as trapped_state_handler:
            self.logger.debug("Starting TaskRun")

            result = self.task.run(**inputs) # type: ignore

            return Success(data=result, message="Task run succeeded.")

        # ---------------------------------------------------------
        # If we reach this point, it means a signal was caught and must be
        # retrieved from the handler function
        # ---------------------------------------------------------

        return trapped_state_handler()

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

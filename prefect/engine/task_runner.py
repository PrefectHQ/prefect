import datetime
import logging
import types
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List

import prefect
from prefect import signals
from prefect.core import Task
from prefect.engine.state import State


class TaskRunner:
    def __init__(
        self,
        task: Task,
        executor: "prefect.engine.executors.Executor" = None,
        logger_name: str = None,
    ) -> None:
        self.task = task
        if executor is None:
            executor = prefect.engine.executors.LocalExecutor()
        self.executor = executor
        self.logger = logging.getLogger(logger_name)

    def run(
        self,
        state: State = None,
        upstream_states: Dict[Task, State] = None,
        inputs: Dict[str, Any] = None,
        ignore_trigger: bool = False,
        context: Dict[str, Any] = None,
    ) -> State:
        if state is None:
            state = State()
        upstream_states = upstream_states or {}
        context = context or {}
        inputs = inputs or {}

        # prepare context
        context.update(
            task_name=self.task.name,
            task_max_retries=self.task.max_retries,
            task_run_upstream_states=upstream_states,
            task_run_inputs=inputs,
        )

        # set up context
        with prefect.context(context):

            # prepare executor
            with self.executor.start():

                try:
                    state = self._run(
                        state=state,
                        upstream_states=upstream_states,
                        inputs=inputs,
                        ignore_trigger=ignore_trigger,
                    )

                except signals.DONTRUN:
                    pass

                except signals.SUCCESS:
                    logging.info("SUCCESS")
                    state = self.executor.set_state(state, state.SUCCESS)

                except signals.FAIL as e:
                    state = self.handle_fail(state, data=dict(message=str(e)))

                except signals.RETRY:
                    state = self.handle_retry(state)

                except signals.SKIP:
                    logging.info("SKIP")
                    state = self.executor.set_state(state, state.SKIPPED)

                except Exception as e:
                    logging.info("Unexpected error while running task.")
                    state = self.handle_fail(state, data=dict(message=str(e)))

        return state

    def _run(
        self,
        state: State,
        upstream_states: Dict[Task, State],
        inputs: Dict[str, Any],
        ignore_trigger: bool,
    ):

        # -------------------------------------------------------------
        # check upstream tasks
        # -------------------------------------------------------------

        # make sure all upstream tasks are finished
        if not all(s.is_finished() for s in upstream_states.values()):
            raise signals.DONTRUN("Upstream tasks are not finished.")

        # -------------------------------------------------------------
        # check upstream skips and propogate if appropriate
        # -------------------------------------------------------------

        if self.task.propogate_skip and any(
            s.is_skipped() for s in upstream_states.values()
        ):
            raise signals.SKIP("Upstream tasks skipped.")

        # -------------------------------------------------------------
        # check trigger
        # -------------------------------------------------------------

        if not ignore_trigger and not self.task.trigger(upstream_states):
            raise signals.DONTRUN("Trigger failed")

        # -------------------------------------------------------------
        # check this task's state
        # -------------------------------------------------------------

        # this task is already running
        if state.is_running():
            raise signals.DONTRUN("Task is already running.")

        # this task is already finished
        elif state.is_finished():
            raise signals.DONTRUN("Task is already finished.")

        # this task is not pending
        elif not state.is_pending():
            raise signals.DONTRUN("Task is not ready to run (state {}).".format(state))

        # -------------------------------------------------------------
        # start!
        # -------------------------------------------------------------

        self.logger.info("Starting TaskRun.")
        state = self.executor.set_state(state, State.RUNNING)

        result = self.task.run(**inputs)

        # mark success
        state = self.executor.set_state(state, State.SUCCESS, data=result)

        return state

    def handle_fail(self, state, data=None):
        """
        Checks if a task is eligable for retry; otherwise marks it failed.
        """
        self.logger.info("Task FAILED")
        run_number = prefect.context.get("run_number", 1)
        if run_number and run_number <= self.task.max_retries:
            return self.handle_retry(state)
        else:
            return self.executor.set_state(state, State.FAILED, data=data)

    def handle_retry(self, state, retry_time=None):
        # TODO exponential backoff based on run_number
        # run_number = prefect.context.get('run_number', 0)

        self.logger.info("Task RETRYING")
        if retry_time is None:
            retry_time = datetime.datetime.utcnow() + self.task.retry_delay

        return self.executor.set_state(state, State.PENDING_RETRY, data=retry_time)

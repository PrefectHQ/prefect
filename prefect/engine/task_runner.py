import datetime
import logging
import types
import uuid
from contextlib import contextmanager

import prefect
from prefect import signals
from prefect.utilities.context import call_with_context_annotations
from prefect.engine.state import TaskState


class TaskRunner:
    def __init__(self, task, executor=None, logger_name=None):
        """
        Args:
            task (prefect.Task)

            executor (Prefect Executor)

            logger_name (str)
        """
        self.task = task
        if executor is None:
            executor = prefect.engine.executors.LocalExecutor()
        self.executor = executor
        self.logger = logging.getLogger(logger_name)

    @contextmanager
    def catch_signals(self, state):
        try:
            yield

        except signals.SUCCESS as s:
            s_name = type(s).__name__
            self.logger.info("Task {} {}: {}".format(self.task, s_name, s))
            self.handle_success(state=state, result=s.result)

        except signals.SKIP as s:
            s_name = type(s).__name__
            self.logger.info("Task {} {}: {}".format(self.task, s_name, s))
            self.executor.set_state(
                state=state, new_state=TaskState.SKIPPED, result=s.result
            )

        except signals.SKIP_DOWNSTREAM as s:
            s_name = type(s).__name__
            self.logger.info("Task {} {}: {}".format(self.task, s_name, s))
            self.executor.set_state(
                state=state, new_state=TaskState.SKIP_DOWNSTREAM, result=s.result
            )

        except signals.RETRY as s:
            s_name = type(s).__name__
            self.logger.info("Task {} {}: {}".format(self.task, s_name, s))
            self.handle_retry(
                state=state, new_state=TaskState.PENDING_RETRY, result=s.result
            )

        except signals.SHUTDOWN as s:
            s_name = type(s).__name__
            self.logger.info("Task {} {}: {}".format(self.task, s_name, s))
            self.executor.set_state(
                state=state, new_state=TaskState.SHUTDOWN, result=s.result
            )

        except signals.DONTRUN as s:
            s_name = type(s).__name__
            self.logger.info("Task {} {}: {}".format(self.task, s_name, s))

        except signals.FAIL as s:
            s_name = type(s).__name__
            self.logger.info("Task {} {}: {}".format(self.task, s_name, s))
            self.handle_fail(state=state, result=s.result)

        except Exception as e:
            if prefect.config.tests.test_mode:
                if prefect.config.tests.raise_run_errors:
                    raise
            self.logger.info(
                "Task {}: An unexpected error occurred".format(self.task), exc_info=1
            )
            self.handle_fail(state=state, result=str(e))

    def run(
        self,
        state=None,
        upstream_states=None,
        inputs=None,
        ignore_trigger=False,
        context=None,
    ):
        """
        Run a task

        Arguments
            state (TaskState): the task's current state

            upstream_states (dict): a dictionary of {task: TaskState}
                pairs containing the states of any upstream tasks

            upstream_kwargs (dict): a dictionary of {kwarg: task} pairs
                indicating that the specified keyword arguments of the task's
                run() method should come from the results of the provided
                tasks.

            ignore_trigger (bool): if True, the trigger function check will
                be skipped.

            context (dict): Prefect context
        """
        state = TaskState(state)
        upstream_states = upstream_states or {}
        inputs = inputs or {}
        context = context or {}

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
            with self.executor.execution_context():

                # catch signals
                with self.catch_signals(state):

                    self._check_state(
                        state=state,
                        upstream_states=upstream_states,
                        ignore_trigger=ignore_trigger,
                    )

                    self._run_task(state=state, inputs=inputs)

        return state

    def _check_state(self, state, upstream_states, ignore_trigger):

        # -------------------------------------------------------------
        # check upstream tasks
        # -------------------------------------------------------------

        # make sure all upstream tasks are finished
        if not all(s.is_finished() for s in upstream_states.values()):
            raise signals.DONTRUN("Upstream tasks are not finished.")

        # -------------------------------------------------------------
        # check trigger
        # -------------------------------------------------------------

        # run the task's trigger function and raise DONTRUN if it fails
        try:
            if not ignore_trigger:
                if not self.task.trigger(upstream_states):
                    raise signals.DONTRUN("Trigger failed")

        # check if a SKIP_DOWNSTREAM should be raised before raising any
        # other signals
        except signals.PrefectStateException:
            if any(s == TaskState.SKIP_DOWNSTREAM for s in upstream_states.values()):
                raise signals.SKIP_DOWNSTREAM("Received SKIP_DOWNSTREAM state")
            else:
                raise

        # -------------------------------------------------------------
        # check this task
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
        self.executor.set_state(state, TaskState.RUNNING)

    def _run_task(self, state, inputs):
        result = call_with_context_annotations(self.task.run, **inputs)

        # Begin generator clause -----------------------------------

        # tasks can yield progress
        if isinstance(result, types.GeneratorType):

            # use a sentinel to get the task's final result
            sentinel = str(uuid.uuid4())

            def sentinel_wrapper(task_generator):
                task_result = yield from task_generator
                yield {sentinel: task_result}

            for progress in sentinel_wrapper(result):

                # if we see a sentinel, this is the return value
                if isinstance(progress, dict) and sentinel in progress:
                    result = progress[sentinel]
                    break

                # self.record_progress(progress)

        # End generator clause -------------------------------------

        # mark success
        self.handle_success(state, result=result)

        return state

    def set_state(self, state, new_state, result=None):
        """
        Update a state object with a new state and optional result.
        """
        self.executor.set_state(state, new_state, result=result)

    def handle_fail(self, state, result=None):
        """
        Checks if a task is eligable for retry; otherwise marks it failed.
        """
        run_number = prefect.context.get("run_number", False)
        if run_number and run_number <= self.task.max_retries:
            self.logger.info(
                "Task has run {} time(s) and is allowed {} retries; " "retrying."
            )
            self.handle_retry(state)
        else:
            self.set_state(state, TaskState.FAILED, result=result)

    def handle_retry(self, state, retry_time=None):
        # TODO exponential backoff based on run_number
        # run_number = prefect.context.get('run_number', 0)

        if retry_time is None:
            retry_time = datetime.datetime.utcnow() + self.task.retry_delay

        self.executor.set_state(state, TaskState.PENDING_RETRY, result=retry_time)

    def handle_success(self, state, result=None):
        self.executor.set_state(state, TaskState.SUCCESS, result=result)

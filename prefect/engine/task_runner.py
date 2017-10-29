import datetime
import logging
import sys
import time
import traceback
import types
import uuid
from collections import namedtuple
from contextlib import contextmanager

import prefect
from prefect import signals
from prefect.context import Context, call_with_context_annotations
from prefect.state import TaskRunState


class TaskRunner:

    def __init__(self, task, executor_context=None, logger_name=None):
        """
        Args:
            flow (prefect.Flow)

            executor_context (contextmanager): A context manager that yields
                a Prefect Executor. Context managers are passed instead of
                Executors because Executors are often unserializable.

            logger_name (str)
        """
        self.task = task
        if executor_context is None:
            executor_context = prefect.engine.executors.LocalExecutor()
        self.executor_context = executor_context
        self.logger = logging.getLogger(logger_name or task.name)

    @contextmanager
    def catch_signals(self, executor, state):
        try:
            yield
        except signals.SUCCESS as s:
            self.logger.info('Task {}: {}'.format(type(s).__name__, s))
            self.handle_success(executor, state=state, result=s.result)
        except signals.SKIP as s:
            self.logger.info('Task {}: {}'.format(type(s).__name__, s))
            self.set_state(
                executor,
                state=state,
                new_state=TaskRunState.SKIPPED,
                result=s.result)
        except signals.SKIP_DOWNSTREAM as s:
            self.logger.info('Task {}: {}'.format(type(s).__name__, s))
            self.set_state(
                executor,
                state=state,
                new_state=TaskRunState.SKIP_DOWNSTREAM,
                result=s.result)
        except signals.RETRY as s:
            self.logger.info('Task {}: {}'.format(type(s).__name__, s))
            self.handle_retry(
                executor,
                state=state,
                new_state=TaskRunState.PENDING_RETRY,
                result=s.result)
        except signals.SHUTDOWN as s:
            self.logger.info('Task {}: {}'.format(type(s).__name__, s))
            self.set_state(
                executor,
                state=state,
                new_state=TaskRunState.SHUTDOWN,
                result=s.result)
        except signals.DONTRUN as s:
            self.logger.info('Task {}: {}'.format(type(s).__name__, s))
        except signals.FAIL as s:
            self.logger.info('Task {}: {}'.format(type(s).__name__, s))
            self.handle_fail(executor, state=state, result=s.result)
        except Exception as e:
            self.logger.error('Task: An unexpected error occurred', exc_info=1)
            self.handle_fail(executor, state=state)

    def run(self, state=None, upstream_states=None, inputs=None, context=None):
        """
        Run a task

        Arguments
            state (TaskRunState): the task's current state

            upstream_states (dict): a dictionary of {task.name: TaskRunState}
                pairs containing the states of any upstream tasks

            upstream_kwargs (dict): a dictionary of {kwarg: task.name} pairs
                indicating that the specified keyword arguments of the task's
                run() method should come from the results of the provided
                tasks.

            context (dict): Prefect context
        """
        state = TaskRunState(state)
        upstream_states = upstream_states or {}
        inputs = inputs or {}
        context = context or {}

        # prepare context
        context.update(
            dict(
                task_name=self.task.name,
                task_max_retries=self.task.max_retries,
                task_run_upstream_states=upstream_states,
                task_run_inputs=inputs))

        # set up context
        with prefect.context.Context(context):

            # prepare executor
            with self.executor_context(context=context) as executor:

                # catch signals
                with self.catch_signals(executor, state):

                    self._run(
                        executor=executor,
                        state=state,
                        upstream_states=upstream_states,
                        inputs=inputs)

        return state

    def _run(self, executor, state, upstream_states, inputs):

        # -------------------------------------------------------------
        # check upstream tasks
        # -------------------------------------------------------------

        # make sure all upstream tasks are finished
        if not all(s.is_finished() for s in upstream_states.values()):
            raise signals.DONTRUN('Upstream tasks are not finished.')

        # run the task's trigger function and raise DONTRUN if it fails
        try:
            if not self.task.trigger(upstream_states):
                raise signals.DONTRUN('Trigger failed')

        # check if a SKIP_DOWNSTREAM should be raised before raising any other
        # signals
        except signals.PrefectStateException:
            if any(s == TaskRunState.SKIP_DOWNSTREAM
                   for s in upstream_states.values()):
                raise signals.SKIP_DOWNSTREAM('Received SKIP_DOWNSTREAM state')
            else:
                raise

        # -------------------------------------------------------------
        # check this task
        # -------------------------------------------------------------

        # this task is already running
        if state.is_running():
            raise signals.DONTRUN('Task is already running.')

        # this task is already finished
        elif state.is_finished():
            raise signals.DONTRUN('Task is already finished.')

        # this task is not pending
        elif not state.is_pending():
            raise signals.DONTRUN(
                'Task is not ready to run (state {}).'.format(state))

        # -------------------------------------------------------------
        # start!
        # -------------------------------------------------------------

        self.logger.info('Starting TaskRun.')
        self.set_state(executor, state, TaskRunState.RUNNING)

        if self.task.loop:
            result = None
            while not result:
                result = call_with_context_annotations(self.task.run, **inputs)
                time.sleep(self.task.loop_delay)
        else:
            result = call_with_context_annotations(self.task.run, **inputs)

            # Begin generator clause -----------------------------------

            # tasks can yield progress
            if isinstance(result, types.GeneratorType):

                # use a sentinel to get the task's final result
                sentinel = uuid.uuid1().hex

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
        self.handle_success(executor, state, result=result)

    def set_state(self, executor, state, new_state, result=None):
        """
        Update a state object with a new state and optional result.
        """
        executor.set_state(state, new_state, result=result)

    def handle_fail(self, executor, state, result=None):
        """
        Checks if a task is eligable for retry; otherwise marks it failed.
        """
        run_number = prefect.context.Context.get('run_number', False)
        if run_number and run_number <= self.task.max_retries:
            self.logger.info(
                'Task has run {} time(s) and is allowed {} retries; '
                'retrying.')
            self.handle_retry(executor, state)
        else:
            self.set_state(executor, state, TaskRunState.FAILED, result=result)

    def handle_retry(self, executor, state, retry_time=None):
        run_number = prefect.context.Context.get('run_number', 0)

        if retry_time is None:
            retry_time = datetime.datetime.utcnow() + self.task.retry_delay(
                run_number)

        self.set_state(
            executor, state, TaskRunState.PENDING_RETRY, result=retry_time)

    def handle_success(self, executor, state, result=None):
        self.set_state(executor, state, TaskRunState.SUCCESS, result=result)

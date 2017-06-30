from collections import namedtuple
from contextlib import contextmanager
import logging
import prefect
from prefect import signals
from prefect.state import TaskRunState
from prefect.runners.results import RunResult, Progress
import sys
import types
import uuid


class TaskRunner:

    def __init__(self, task, executor, progress_fn=None):

        self.task = task
        self.executor = executor
        self.logger = logging.getLogger(repr(task))
        if progress_fn:
            self.record_progress = progress_fn

    def run(self, state=None, upstream_states=None, inputs=None, context=None):
        state = prefect.state.TaskRunState(state)
        upstream_states = upstream_states or {}
        inputs = inputs or {}

        with context.prefect_context(**context or {}):
            with self.catch_signals(state):
                self.check_state(state=state, upstream_states=upstream_states)
                result = self.run_task(inputs=inputs)
                result = self.process_result(result)
        return dict(state=state, result=result)

    @contextmanager
    def catch_signals(self, state):
        try:
            yield

        except signals.SUCCESS as s:
            self.logger.info(f'{type(s).__name__}: {s}')
            state.succeed()
        except signals.SKIP as s:
            self.logger.info(f'{type(s).__name__}: {s}')
            state.skip()
        except signals.RETRY as s:
            self.logger.info(f'{type(s).__name__}: {s}')
            state.fail()
        except signals.SHUTDOWN as s:
            self.logger.info(f'{type(s).__name__}: {s}')
            state.shutdown()
        except signals.DONTRUN as s:
            self.logger.info(f'{type(s).__name__}: {s}')
        except (signals.FAIL, Exception) as s:
            self.logger.info(f'{type(s).__name__}: {s}')
            state.fail()

    def check_state(self, state, upstream_states, context=None):
        """
        Check if a Task is ready to run
        """

        with prefect.context(**context or {}):

            # -------------------------------------------------------------
            # check upstream tasks
            # -------------------------------------------------------------

            # make sure all upstream tasks are finished
            if not all(s.is_finished() for s in upstream_states.values()):
                raise signals.DONTRUN('Upstream tasks are not finished.')

            # check the task trigger function
            elif not self.task.trigger(upstream_states):
                raise signals.DONTRUN('Trigger failed')

            # -------------------------------------------------------------
            # check this task
            # -------------------------------------------------------------

            # this task is already running
            if state.is_running():
                raise signals.DONTRUN('TaskRun is already running.')

            # this task is already finished
            elif state.is_finished():
                raise signals.DONTRUN('TaskRun is already finished.')

            # this task is not pending
            elif not state.is_pending():
                raise signals.DONTRUN(
                    f'TaskRun is not ready to run (state {state}).')

            # -------------------------------------------------------------
            # start!
            # -------------------------------------------------------------

            state.start()

        return state

    def run_task(self, inputs, context=None):
        """
        Execute a Task
        """

        with prefect.context(**context or {}):

            result = self.task.run(**inputs)

            # tasks can yield progress
            if isinstance(result, types.GeneratorType):

                # use a sentinel to get the task's final result
                sentinel = uuid.uuid1().hex

                def sentinel_wrapper(task_generator):
                    task_result = yield from task_generator
                    yield {sentinel: task_result}

                for progress in sentinel_wrapper(result):

                    # if we see the sentinel, this is the task's return value
                    if isinstance(progress, dict) and sentinel in progress:
                        result = progress[sentinel]
                        break

                    self.record_progress(progress)

        return result

    def process_result(self, result, context=None):
        """
        Process a Task's result by serializing it
        """
        with prefect.context(**context or {}):
            return self.task.serializer.encode(task, result)


    def record_progress(self, progress):
        self.logger.info(f'PROGRESS: {progress}')

# class TaskRunner:
#
#     def __init__(self, task, flowrun_id=None, executor=None, run_number=1):
#         """
#         Args:
#
#             task (Task): the Task to run
#
#             flowrun_id (str): the flow run id
#
#             executor (Executor)
#
#         """
#         self.task = task
#
#         if executor is None:
#             executor = prefect.runners.executors.default_executor()
#         self.executor = executor
#
#         if flowrun_id is None:
#             flowrun_id = uuid.uuid4().hex
#         self.flowrun_id = flowrun_id
#         self.id = f'{flowrun_id}/{task.name}'
#         self.run_number = run_number
#
#     def run(self, state=None, upstream_states=None, inputs=None, context=None):
#         """
#         Args:
#
#             state (TaskRunState): the initial state of the task
#
#             upstream_states (dict): a dict of {task.name: TaskRunState} pairs
#                 indicating the state and results of any upstream tasks. This is
#                 used to evaluate whether this task can run, as well as the
#                 value of any inputs this task requires.
#
#             inputs (dict): a dict of {kwarg: value} pairs
#                 indicating the inputs to the task's run() function.
#
#             context (dict): the Prefect context
#
#             progress (Progress): the initial Progress of the task
#         """
#
#         if state is None:
#             state = TaskRunState()
#
#         upstream_states = upstream_states or {}
#         inputs = inputs or {}
#
#         prefect_context = {
#             'task_name': self.task.name,
#             'update_progress': lambda p: print(f'Task Progress: {p}'),
#         }
#         prefect_context.update(context or {})
#
#         def log_task_state(msg, err):
#             logger = logging.getLogger(type(self).__name__)
#             logger.info('{}: {}'.format(msg.format(task=self.task), err))
#
#         # ---------------------------------------------------------------------
#         # Run the task
#         # ---------------------------------------------------------------------
#
#         result = None
#         try:
#             with self.executor.context(**prefect_context):
#
#                 # -------------------------------------------------------------
#                 # check that Task is runnable
#                 # -------------------------------------------------------------
#
#                 # any of the upstream tasks are not finished
#                 if not all(s.is_finished() for s in upstream_states.values()):
#                     raise signals.DONTRUN('Upstream tasks are not finished')
#
#                 # this task is already finished
#                 elif state.is_finished():
#                     raise signals.DONTRUN('Task is already finished')
#
#                 # this task is not pending (meaning already running or stopped)
#                 elif not state.is_pending():
#                     raise signals.DONTRUN(
#                         f'Task is not ready to run (state {state})')
#
#                 # -------------------------------------------------------------
#                 # TODO check that FlowRun is active
#                 # -------------------------------------------------------------
#
#                 # -------------------------------------------------------------
#                 # check task trigger
#                 # -------------------------------------------------------------
#
#                 if not self.task.trigger(upstream_states):
#                     raise signals.DONTRUN('Trigger failed')
#
#                 # -------------------------------------------------------------
#                 # start!
#                 # -------------------------------------------------------------
#
#                 state.start()
#                 # -------------------------------------------------------------
#                 # run the task
#                 # -------------------------------------------------------------
#
#                 result = self.executor._execute_task(
#                     execute_fn=self._execute_task,
#                     inputs=inputs,
#                     context=prefect_context)
#
#                 size = sys.getsizeof(result)
#                 if size > prefect.config.getint('tasks', 'max_result_size'):
#                     raise signals.FAIL(
#                         f'Task result is too large ({size}b); consider '
#                         'serializing it.')
#
#             state.succeed()
#         except signals.SKIP as e:
#             log_task_state('{task} was skipped', e)
#             state.skip()
#         except signals.RETRY as e:
#             log_task_state('{task} will be retried', e)
#             state.fail()
#         except signals.WAIT as e:
#             log_task_state('{task} is waiting', e)
#             state.wait()
#         except signals.SHUTDOWN as e:
#             log_task_state('{task} was shut down', e)
#             state.shutdown()
#         except signals.DONTRUN as e:
#             log_task_state('{task} was not run', e)
#         except (signals.FAIL, Exception) as e:
#             log_task_state('{task} failed', e)
#             state.fail()
#
#         return RunResult(state=state, result=result)
#
#     def _execute_task(self, inputs, context):
#
#         with prefect.context(**context):
#
#             result = self.task.run(**inputs)
#
#             # handle tasks that generate new tasks
#             if isinstance(result, types.GeneratorType):
#
#                 sentinel = uuid.uuid4().hex
#
#                 def generator_task_wrapper(result):
#                     task_result = yield from result
#                     yield {sentinel: task_result}
#
#                 for subtask in generator_task_wrapper(result):
#
#                     # if we see the sentinel, this is the task's return value
#                     if isinstance(subtask, dict) and sentinel in subtask:
#                         result = subtask[sentinel]
#                         break
#                     # submit flows
#                     elif isinstance(subtask, prefect.Flow):
#                         prefect.context.run_flow(subtask)
#                     # submit tasks
#                     elif isinstance(subtask, prefect.Task):
#                         prefect.context.run_task(subtask)
#                     # update progress
#                     else:
#                         prefect.context.update_progress(subtask)
#
#             result = self.task.serializer.encode(self.id, result)
#
#         return result

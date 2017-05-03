import logging
import prefect
from prefect import Flow, Task, signals
from prefect.context import prefect_context
import sys
import types
import uuid


def maybe_index(obj, index=None):
    if index is None:
        return obj
    else:
        return obj[index]


class TaskRunner:

    def __init__(self, task, run_id=None, executor=None):
        """
        Args:

            task (Task): the Task to run

            run_id (str): the flow run id

            executor (Executor)

        """
        self.task = task

        if executor is None:
            executor = getattr(
                prefect.runners.executors,
                prefect.config.get('prefect', 'default_executor'))()
        self.executor = executor
        if run_id is None:
            run_id = uuid.uuid4().hex
        self.run_id = run_id
        self.id = run_id + task.id

    def run(self, state=None, upstream_edges=None, context=None):

        if state is None:
            state = prefect.state.TaskRunState()

        upstream_edges = upstream_edges or []

        context = (context or {}).copy()
        context.update({
            'task_id': self.task.id,
            'task_name': self.task.name,
        })

        context['waiting'] = state.is_waiting()

        def log_task_state(msg, err):
            logger = logging.getLogger(type(self).__name__)
            logger.info('{}: {}'.format(msg.format(task=self.task), err))

        # run the task
        try:
            result = None
            with prefect_context(**context) as context:
                result = self._run_task(
                    context=context, upstream_edges=upstream_edges, state=state)
            state.succeed(result=result)
        except signals.SKIP as e:
            log_task_state('{task} was skipped', e)
            state.skip()
        except signals.RETRY as e:
            log_task_state('{task} will be retried', e)
            state.fail()
        except signals.WAIT as e:
            log_task_state('{task} is waiting', e)
            state.wait()
        except signals.SHUTDOWN as e:
            log_task_state('{task} was shut down', e)
            state.shutdown()
        except signals.DONTRUN as e:
            log_task_state('{task} was not run', e)
        except (signals.FAIL, Exception) as e:
            log_task_state('{task} failed', e)
            state.fail()

        # Deserialize the result
        if state.is_successful():
            if state.result['serialized'] is True:
                result = self.task.serializer.decode(result['value'])
            else:
                result = result['value']

        return prefect.state.TaskRunState(state, result=result)

    def _run_task(self, context, upstream_edges, state):

        upstream_states = {
            e['upstream_task']: e['state']
            for e in upstream_edges
        }

        upstream_inputs = {
            e['key']: maybe_index(e['state'].result, e['upstream_index'])
            for e in upstream_edges if e['key'] is not None
        }

        # ---------------------------------------------------------------------
        # check that Task is runnable
        # ---------------------------------------------------------------------

        # any of the upstream tasks are not finished
        if not all(s.is_finished() for s in upstream_states.values()):
            raise signals.DONTRUN('Upstream tasks are not finished')

        # this task is already finished
        elif state.is_finished():
            raise signals.DONTRUN('Task is already finished')

        # this task is not pending (meaning already running or stopped)
        elif not state.is_pending():
            raise signals.DONTRUN(
                'Task is not ready to run (state {})'.format(state))

        # ---------------------------------------------------------------------
        # TODO check that FlowRun is active
        # ---------------------------------------------------------------------

        # ---------------------------------------------------------------------
        # start!
        # ---------------------------------------------------------------------

        state.start()

        # ---------------------------------------------------------------------
        # check task trigger
        # ---------------------------------------------------------------------

        if not self.task.trigger(upstream_states):
            raise signals.FAIL('Trigger failed')

        # ---------------------------------------------------------------------
        # run the task
        # ---------------------------------------------------------------------

        result = self.task.run(**upstream_inputs)

        # ---------------------------------------------------------------------
        # handle tasks that generate new tasks
        # ---------------------------------------------------------------------

        if isinstance(result, types.GeneratorType):

            sentinel = uuid.uuid4().hex

            def generator_task_wrapper(result):
                task_result = yield from result
                yield {sentinel: task_result}

            with self.executor.executor_context() as executor:

                for subtask in generator_task_wrapper(result):

                    # if we see the sentinel, this is the task's return
                    # value
                    if isinstance(subtask, dict) and sentinel in subtask:
                        result = subtask[sentinel]
                        break

                    # coerce generated task to an iterable
                    if isinstance(subtask, (Task, Flow)):
                        subtask = [subtask]

                    # run generated tasks / flows
                    for st in subtask:
                        if isinstance(st, Flow):
                            flow_runner = prefect.runners.FlowRunner(
                                flow=st, executor=self.executor)
                            executor.run_flow(flow_runner)

                        elif isinstance(st, Task):
                            task_runner = TaskRunner(
                                task=st,
                                executor=self.executor,
                                run_id=self.run_id)
                            executor.run_task(
                                task_runner, upstream_tasks={}, context=context)
                        else:
                            raise TypeError(
                                'Task yielded an unexpected subtask '
                                'type: {}'.format(type(st).__name__))

        # ---------------------------------------------------------------------
        # serialize the result
        # ---------------------------------------------------------------------

        serialized = False
        result_size = sys.getsizeof(result)
        serialize_size = prefect.config.get('tasks', 'serialize_if_over')
        if result is not None and result_size >= int(serialize_size):
            result = self.task.serializer.encode(self.id, result)
            serialized = True
        result = {'value': result, 'serialized': serialized}

        return result

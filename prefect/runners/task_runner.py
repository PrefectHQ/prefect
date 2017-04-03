import datetime
from distributed import worker_client
import logging
import prefect.flow
from prefect import exceptions as ex
from prefect.runners.context import prefect_context
from prefect.state import State
import types
import uuid

#TODO handle timeouts
#TODO handle retries


class TaskRunner(prefect.utilities.logging.LoggingMixin):
    """
    The TaskRunner  that can be submitted to the Dask
    cluster.

    The function accepts a list of preceding task states and returns its own
    state.
    """

    def __init__(
            self, run_id, task, run_number=1, force=False,
            scheduled_start=None):
        self.task = task
        self.run_id = run_id
        self.force = force
        self.state = State()
        self.run_number = run_number
        self.scheduled_start = scheduled_start

        self._logger = logging.root.getChild(repr(self))

        self.created = datetime.datetime.utcnow()
        self.started = None
        self.finished = None
        self.heartbeat = None

        self._id = None

    @property
    def id(self):
        if self._id is None:
            raise ValueError(
                "This TaskRun hasn't been saved to the database yet.")
        return self._id

    def __repr__(self):
        return '{}(run_id={}, task={}, run={})'.format(
            type(self).__name__, self.run_id, self.task.id, self.run_number)

    def run(self, preceding_states, context, force=False):

        if self.state.is_successful():
            if force:
                self.state.clear()
                self.state.pending()
            else:
                return

        l, t = self.logger, self.task
        try:
            self._run(
                preceding_states=preceding_states, context=context, force=force)
        except ex.SUCCESS as e:
            l.debug('Task {} completed successfully: {}'.format(t, e))
            self.state.succeed()
        except ex.SKIP as e:
            l.debug('Task {} was skipped: {}'.format(t, e))
            self.state.skip()
        except ex.RETRY as e:
            l.debug('Task {} indicated it should be retried: {}'.format(t, e))
            self.state.fail()
        except (ex.FAIL, ex.PrefectError, Exception,) as e:
            l.debug('Task {} failed: {}'.format(t, e))
            self.state.fail()

        if self.state.is_failed() and self.run_number < self.task.max_retries:
            self.state.retry()
            retry_delay = self.task.retry_delay
            if callable(retry_delay):
                retry_delay = self.task.retry_delay(
                    self.run_number, self.task.max_retries)
            scheduled_start = datetime.datetime.utcnow() + retry_delay
            next_taskrun = TaskRunner(
                run_id=self.run_id,
                task=self.task,
                run_number=self.run_number + 1,
                scheduled_start=datetime.datetime.utcnow() + retry_delay)
            next_taskrun.save()
            run(preceding_states)
            # TODO
            # finish this by submitting the taskrun inside a worker thread
            # we can't exit this taskrun until we know its final state,
            # so we wait for the new taskrun (and possibly its descendents),
            # refreshing state when it finishes to find out what happened.

        self.save()
        return self.state

    def _run(self, preceding_states, context, force=False):
        """
        Run the task and return its state.

        preceding_states: a dict of {task_id: state} pairs for all tasks
            immediately preceding this one
        """

        # -------------------------------------------------------------------
        # TODO: take a lock on the TaskRunModel
        # -------------------------------------------------------------------
        self.save_or_reload()
        self.started = datetime.datetime.utcnow()
        self.finished = None
        self.save()

        # -------------------------------------------------------------------
        # check that Task is runnable
        # -------------------------------------------------------------------
        if not force:
            if not self.state.is_pending():
                raise ex.FAIL(
                    'The task is not ready to run (state {})'.format(
                        self.state))
                return

        # -------------------------------------------------------------------
        # check that FlowRun is still active
        # -------------------------------------------------------------------
        if not force:
            try:
                flow_run = prefect.models.FlowRunModel.objects.get(
                    _id=self.run_id)
                if not flow_run.state.is_running():
                    raise ex.SKIP('The FlowRun is no longer running.')
            except mongoengine.DoesNotExist:
                pass

        # -------------------------------------------------------------------
        # let's get started!
        # -------------------------------------------------------------------
        self.state.start()
        self.save()

        # -------------------------------------------------------------------
        # evaluate task trigger
        # -------------------------------------------------------------------
        if not force:
            # the trigger raises exceptions as necessary
            self.task.trigger(preceding_states)

        # -------------------------------------------------------------------
        # run downstream phase of any incoming edges
        # -------------------------------------------------------------------
        for edge in self.task.flow.edges_to(self.task):
            edge_result = edge.run_downstream(run_id=self.run_id)
            if edge_result:
                context['edges'].update(edge_result)

        # -------------------------------------------------------------------
        # run task
        # -------------------------------------------------------------------
        with prefect_context(**context):
            result = self.task.run(**context['edges'])
            # if the task returns a generator, it means it generates
            # subtasks that require special handling
            if isinstance(result, types.GeneratorType):
                self._run_generator_task(result)

        # -------------------------------------------------------------------
        # Finished!
        # -------------------------------------------------------------------
        self.finished = datetime.datetime.utcnow()
        raise ex.SUCCESS('TaskRun complete!')

    def _run_generator_task(self, generator):
        """
        Tasks can be generators, yielding new Flows and Tasks. If so, we
        iterate over the generator and submit each new task to the cluster.

        Tasks can also yield numbers. By convention, numbers between 0 and 1
        are treated as percentage complete and numbers > 1 as a count.
        """
        futures = set()
        with worker_client() as client:

            generated_futures = client.channel('generated_futures')

            # create a context for yielding tasks
            with self.task.flow:
                # iterate over the generator
                for result in generator:
                    #
                    if isinstance(result, (float, int)):
                        self.progress = result
                        self.save()
                        continue
                    if isinstance(
                            result, (prefect.task.Task, prefect.flow.Flow)):
                        result = [result]
                    for subtask in result:
                        # the subtask is a Flow
                        #   - create a Flow Runner and execute the Flow
                        if isinstance(subtask, prefect.flow.Flow):
                            runner = prefect.runners.FlowRunner(
                                flow=subtask,
                                run_id=self.id,
                                params=self.params,
                                generated_by=self.to_model())
                            future = client.submit(runner.run, pure=False)
                            futures.add(future)
                            generated_futures.append(future)

                        # the subtask is a Flow
                        #   - create a Flow Runner and execute the Flow
                        elif isinstance(subtask, prefect.task.Task):
                            runner = TaskRunner(task=subtask, run_id=self.id)
                            future = client.submit(
                                runner.run,
                                preceding_states={},
                                context=context,
                                pure=False)
                            futures.add(future)
                            generated_futures.append(future)

                        # raise an error if something unexpected happens
                        else:
                            raise ex.PrefectError(
                                'Tasks should only yield Flows and Tasks; '
                                'received {}'.format(type(subtask).__name__))
            self.state.wait_for_subtasks()
            self.save()
            client.gather(futures)
            self.state.resume()
            self.save()

    # ORM ----------------------------------------------------------

    def _get_model(self):
        kwargs = dict()

    def to_model(self):
        return prefect.models.TaskRunModel(
            _id=self.id,
            task=self.task.to_model(),
            run_id=self.run_id,
            state=str(self.state),
            run_number=self.run_number,
            scheduled_start=self.scheduled_start,
            progress=self.progress,
            created=self.created,
            started=self.started,
            finished=self.finished)

    def save(self):
        model = self.to_model()
        model.save()
        return model

    def save_or_reload(self):
        model = self.to_model()
        prefect.utilities.mongo.save_or_reload(model)
        return model


#     def reload(self):
#         model = self.to_model()
#         model.reload()
#         self.state = model.state
#         self.run_number = model.run_number
#         self.scheduled_start = model.scheduled_start
#         self.created = model.created
#         self.started = model.started
#         self.finished = model.finished
#
#
#
# class Timeout:
#     def __init__(self, timeout):
#         self.timeout = timeout
#
#     def __enter__(self):
#         self.start_time
#
#
#
#
# class PrefectRunContext:
#     def __init__(self, fn, max_retries=0)
#
#     def __enter__(self):
#         state = None
#         with concurrent.futures.ThreadPoolExecutor(1) as e:
#             for r in range(1 + self.max_retries):
#                 try:
#                     result = self.fn()
#                     state = prefect.state.SUCCESS
#                 except ex.SKIP:
#                     self.logger('Skip exception raised, skipping task.')
#                     break
#                 except (ex.RETRY, ex.PrefectError):
#                     continue

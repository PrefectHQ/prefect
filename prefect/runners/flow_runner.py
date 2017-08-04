from contextlib import contextmanager

# import datetime
import distributed

import prefect
import prefect.signals
from prefect.runners.runner import Runner
# from prefect.runners.task_runner import TaskRunner
from prefect.state import FlowRunState


# from prefect.runners.results import RunResult
# import uuid


class FlowRunner(Runner):

    def __init__(self, flow, executor=None, progress_fn=None):
        self.flow = flow
        super().__init__(
            executor=executor, logger_name=repr(flow), progress_fn=progress_fn)

    @contextmanager
    def flow_context(self, context, state):
        with prefect.context(context):
            try:
                yield

            except prefect.signals.SUCCESS as s:
                self.logger.info(f'Flow {type(s).__name__}: {s}')
                state.succeed()
            except prefect.signals.SKIP as s:
                self.logger.info(f'Flow {type(s).__name__}: {s}')
                state.skip()
            except prefect.signals.SHUTDOWN as s:
                self.logger.info(f'Flow {type(s).__name__}: {s}')
                state.shutdown()
            except prefect.signals.DONTRUN as s:
                self.logger.info(f'Flow {type(s).__name__}: {s}')
            except prefect.signals.FAIL as s:
                self.logger.info(f'Flow {type(s).__name__}: {s}', exc_info=True)
                state.fail()
            except Exception:
                if prefect.context.get('debug'):
                    raise
                self.logger.error(
                    'Flow: An unexpected error occurred', exc_info=True)
                state.fail()

    def run(
            self,
            state=None,
            task_states=None,
            task_results=None,
            start_tasks=None,
            context=None):
        """
        Arguments

            task_states (dict): a dictionary of { task.name: TaskState } pairs
                representing the initial states of the Flow.

            task_results (dict): a dictionary of { task.name: result } pairs
                representing the initial results of the Flow. These results
                should be serialized in a format that the Flow Executor
                understands.
        """

        state = prefect.state.FlowRunState(state)
        task_states = task_states or {}
        task_results = task_results or {}
        serialized_results = {}

        if not all(isinstance(t, str) for t in task_states):
            raise TypeError('task_states keys must be string Task names.')
        if not all(isinstance(t, str) for t in task_results):
            raise TypeError('task_results keys must be string Task names.')

        with self.flow_context(context, state):

            with self.executor.client() as client:

                # -------------------------------------------------------------
                # check this flow
                # -------------------------------------------------------------

                # this flow is already finished
                if state.is_finished():
                    raise prefect.signals.DONTRUN('Flow run is already finished.')

                # this flow is not pending or already running
                # Note: we allow multiple flowruns at the same time (state = RUNNING)
                elif not (state.is_pending() or state.is_running()):
                    raise prefect.signals.DONTRUN(
                        f'Flow is not ready to run (state {state}).')

                # -------------------------------------------------------------
                # start!
                # -------------------------------------------------------------

                state.start()

                # first deserialize any initial results that have been provided
                task_results = {
                    task: client.submit(
                        self.executor.deserialize_result,
                        result=result,
                        context=context)
                    for task, result in task_results.items()
                }

                # process each task in order
                for task in self.flow.sorted_tasks(root_tasks=start_tasks):

                    # in order to run, a task needs the states of all upstream
                    # tasks and any inputs
                    states = {}
                    inputs = {}

                    # iterate over any edges leading to the task
                    for edge in self.flow.edges_to(task):

                        upstream_task_name = edge.upstream_task
                        # get the upstream state
                        if upstream_task_name not in task_states:
                            raise ValueError(
                                f'Task state not found: {upstream_task_name}')
                        states[upstream_task_name] = task_states[upstream_task_name]

                        # if the edge has no key, then we're done
                        if edge.key is None:
                            continue

                        inputs[edge.key] = task_results[upstream_task_name]

                        # index the result, if necessary
                        if edge.upstream_index is not None:
                            inputs[edge.key] = client.submit(
                                lambda result, index: result[index],
                                result=inputs[edge.key],
                                index=edge.upstream_index)

                    # run the task
                    future = client.submit(
                        self.executor.run_task,
                        task=task,
                        state=task_states[task.name],
                        upstream_states=states,
                        inputs=inputs,
                        context=context,
                        pure=False)

                    # store the task's state
                    task_states[task.name] = client.submit(
                        lambda future: future['state'], future=future, pure=False)

                    # store the task's result
                    task_results[task.name] = client.submit(
                        lambda future: future['result'], future=future, pure=False)

                # once all tasks are done, collect their states
                # and collect their serialized results
                task_states = client.gather(task_states)
                serialized_results = client.gather(
                    {
                        task_name: client.submit(
                            self.executor.serialize_result,
                            result=result,
                            context=context,
                            pure=False)
                        for task_name, result in task_results.items()
                    })

            terminal_states = {
                task.name: task_states[task.name]
                for task in self.flow.terminal_tasks()
            }

            if any(s.is_failed() for s in terminal_states.values()):
                self.logger.info('Flow FAIL: Some terminal tasks failed.')
                state.fail()
            elif all(s.is_successful() for s in terminal_states.values()):
                self.logger.info('Flow SUCCESS: All terminal tasks succeeded.')
                state.succeed()

        return dict(
            state=state,
            task_states=task_states,
            task_results=serialized_results)

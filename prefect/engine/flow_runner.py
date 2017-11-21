import logging
from contextlib import contextmanager

import prefect
import prefect.signals
from prefect.state import FlowRunState, TaskRunState


class FlowRunner:

    def __init__(self, flow, executor=None, logger_name=None):
        """
        Args:
            flow (prefect.Flow)

            executor (Executor): a Prefect Executor

            logger_name (str)
        """
        self.flow = flow
        if executor is None:
            executor = prefect.engine.executors.LocalExecutor()
        self.executor = executor
        self.logger = logging.getLogger(logger_name or flow.name)

    @contextmanager
    def catch_signals(self, state):
        try:
            yield
        except prefect.signals.SUCCESS as s:
            self.logger.info('Flow {}: {}'.format(type(s).__name__, s))
            self.executor.set_state(
                state=state, new_state=FlowRunState.SUCCESS, result=s.state)
        except prefect.signals.SKIP as s:
            self.logger.info('Flow {}: {}'.format(type(s).__name__, s))
            self.executor.set_state(
                state=state, new_state=FlowRunState.SKIP, result=s.state)
        except prefect.signals.SHUTDOWN as s:
            self.logger.info('Flow {}: {}'.format(type(s).__name__, s))
            self.executor.set_state(
                state=state, new_state=FlowRunState.SHUTDOWN, result=s.state)
        except prefect.signals.DONTRUN as s:
            self.logger.info('Flow {}: {}'.format(type(s).__name__, s))
        except prefect.signals.FAIL as s:
            self.logger.info(
                'Flow {}: {}'.format(type(s).__name__, s), exc_info=True)
            self.executor.set_state(
                state=state, new_state=FlowRunState.FAILED, result=s.state)
        except Exception:
            self.logger.error(
                'Flow: An unexpected error occurred', exc_info=True)
            self.executor.set_state(state=state, new_state=FlowRunState.FAILED)

    def run(
            self,
            state: FlowRunState = None,
            task_states: dict = None,
            start_tasks: list = None,
            inputs: dict = None,
            context: dict = None,
            task_contexts: dict = None,
            return_all_task_states: bool = False,
    ):
        """
        Arguments

            task_states (dict): a dictionary of { task.name: TaskRunState } pairs
                representing the initial states of the FlowRun tasks.

        """

        state = FlowRunState(state)
        task_states = task_states or {}
        inputs = inputs or {}
        task_contexts = task_contexts or {}

        # prepare context
        with prefect.context.Context(context):

            # set up executor context
            with self.executor.execution_context():

                # catch any signals
                with self.catch_signals(state=state):

                    if not all(isinstance(t, str) for t in task_states):
                        raise TypeError(
                            'task_states keys must be string Task names.')

                    self._run(
                        state=state,
                        task_states=task_states,
                        start_tasks=start_tasks,
                        task_contexts=task_contexts,
                        return_all_task_states=return_all_task_states,
                        inputs=inputs)

        return state

    def _run(
            self,
            state,
            task_states,
            start_tasks,
            inputs,
            task_contexts,
            return_all_task_states=False):

        context = prefect.context.Context.as_dict()

        # ------------------------------------------------------------------
        # check this flow
        # ------------------------------------------------------------------

        # this flow is already finished
        if state.is_finished():
            raise prefect.signals.DONTRUN('Flow run is already finished.')

        # this flow isn't pending or already running
        elif not (state.is_pending() or state.is_running()):
            raise prefect.signals.DONTRUN(
                'Flow is not ready to run (state {}).'.format(state))

        # ------------------------------------------------------------------
        # Start!
        # ------------------------------------------------------------------

        self.logger.info('Starting FlowRun.')
        self.executor.set_state(state, FlowRunState.RUNNING)

        # ------------------------------------------------------------------
        # Process each task
        # ------------------------------------------------------------------

        # process each task in order
        for task in self.flow.sorted_tasks(root_tasks=start_tasks):
            self.logger.info('Running task: {}'.format(task.name))

            # if the task is unrecognized, create a placeholder State
            if task.name not in task_states:
                task_states[task.name] = TaskRunState()

            upstream_states = {}
            upstream_inputs = {}

            for edge in self.flow.edges_to(task):

                # gather upstream states
                upstream_states[edge.upstream_task] = (
                    task_states[edge.upstream_task])

                # extract upstream results if the edge indicates they are needed
                if edge.key is not None:
                    upstream_inputs[edge.key] = self.executor.submit(
                        lambda state: state.result,
                        task_states[edge.upstream_task])

            # override upstream_inputs with provided inputs
            upstream_inputs.update(inputs.get(task.name, {}))

            # run the task!
            with prefect.context.Context(task_contexts.get(task.name)):
                task_states[task.name] = self.executor.run_task(
                    task=task,
                    state=task_states[task.name],
                    upstream_states=upstream_states,
                    inputs=upstream_inputs,
                    ignore_trigger=(task.name in (start_tasks or [])),
                    context=context)

        # gather the terminal states and wait for them to complete
        terminal_states = {
            task.name: task_states[task.name]
            for task in self.flow.terminal_tasks()
        }
        self.logger.info('Waiting for tasks to complete...')
        terminal_states = self.executor.wait(terminal_states)

        # depending on the flag, we return all states or just terminal states
        if return_all_task_states:
            result_states = self.executor.wait(task_states)
        else:
            result_states = terminal_states

        if any(s.is_failed() for s in terminal_states.values()):
            self.logger.info('FlowRun FAIL: Some terminal tasks failed.')
            self.executor.set_state(state, FlowRunState.FAILED, result=result_states)
        elif all(s.is_successful() for s in terminal_states.values()):
            self.logger.info('FlowRun SUCCESS: All terminal tasks succeeded.')
            self.executor.set_state(
                state, FlowRunState.SUCCESS, result=result_states)
        elif all(s.is_finished() for s in terminal_states.values()):
            self.logger.info(
                'FlowRun SUCCESS: All terminal tasks finished and none failed.')
            self.executor.set_state(
                state, FlowRunState.SUCCESS, result=result_states)
        else:
            self.logger.info('FlowRun PENDING: Terminal tasks are incomplete.')
            self.executor.set_state(
                state, FlowRunState.PENDING, result=result_states)

        return state

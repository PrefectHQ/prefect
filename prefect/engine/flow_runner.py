import logging
from contextlib import contextmanager

import prefect
import prefect.signals
from prefect.state import FlowRunState, TaskRunState


class FlowRunner:

    def __init__(self, flow, executor_context=None, logger_name=None):
        """
        Args:
            flow (prefect.Flow)

            executor_context (contextmanager): A context manager that yields
                a Prefect Executor. Context managers are passed instead of
                Executors because Executors are often unserializable.

            logger_name (str)
        """
        self.flow = flow
        if executor_context is None:
            executor_context = prefect.engine.executors.LocalExecutor()
        self.executor_context = executor_context
        self.logger = logging.getLogger(logger_name or flow.name)

    @contextmanager
    def catch_signals(self, executor, state):
        try:
            yield
        except prefect.signals.SUCCESS as s:
            self.logger.info('Flow {}: {}'.format(type(s).__name__, s))
            self.set_state(
                executor,
                state=state,
                new_state=FlowRunState.SUCCESS,
                result=s.state)
        except prefect.signals.SKIP as s:
            self.logger.info('Flow {}: {}'.format(type(s).__name__, s))
            self.set_state(
                executor,
                state=state,
                new_state=FlowRunState.SKIP,
                result=s.state)
        except prefect.signals.SHUTDOWN as s:
            self.logger.info('Flow {}: {}'.format(type(s).__name__, s))
            self.set_state(
                executor,
                state=state,
                new_state=FlowRunState.SHUTDOWN,
                result=s.state)
        except prefect.signals.DONTRUN as s:
            self.logger.info('Flow {}: {}'.format(type(s).__name__, s))
        except prefect.signals.FAIL as s:
            self.logger.info(
                'Flow {}: {}'.format(type(s).__name__, s), exc_info=True)
            self.set_state(
                executor,
                state=state,
                new_state=FlowRunState.FAILED,
                result=s.state)
        except Exception:
            self.logger.error(
                'Flow: An unexpected error occurred', exc_info=True)
            self.set_state(executor, state=state, new_state=FlowRunState.FAILED)

    def run(
            self,
            state: FlowRunState = None,
            task_states: dict = None,
            start_tasks: list = None,
            inputs: dict = None,
            context: dict = None,
            return_all_task_states: bool = False,):
        """
        Arguments

            task_states (dict): a dictionary of { task.name: TaskRunState } pairs
                representing the initial states of the FlowRun tasks.

        """

        state = FlowRunState(state)
        task_states = task_states or {}
        inputs = inputs or {}

        # prepare context
        with prefect.context.Context(context):

            # create executor
            with self.executor_context(context=context) as executor:

                # catch any signals
                with self.catch_signals(executor=executor, state=state):

                    if not all(isinstance(t, str) for t in task_states):
                        raise TypeError(
                            'task_states keys must be string Task names.')

                    self._run(
                        executor=executor,
                        state=state,
                        task_states=task_states,
                        start_tasks=start_tasks,
                        return_all_task_states=return_all_task_states,
                        inputs=inputs)

        return state

    def _run(
            self,
            executor,
            state,
            task_states,
            start_tasks,
            inputs,
            return_all_task_states=False):

        context = prefect.context.Context

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
        self.set_state(executor, state, FlowRunState.RUNNING)

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
                    upstream_inputs[edge.key] = executor.submit(
                        lambda state: state.result,
                        task_states[edge.upstream_task])

            # override upstream_inputs with provided inputs
            upstream_inputs.update(inputs.get(task.name, {}))

            # run the task!
            task_states[task.name] = executor.run_task(
                task=task,
                executor_context=self.executor_context,
                state=task_states[task.name],
                upstream_states=upstream_states,
                inputs=upstream_inputs,
                context=context)

        # gather the terminal states and wait for them to complete
        terminal_states = {
            task.name: task_states[task.name]
            for task in self.flow.terminal_tasks()
        }
        self.logger.info('Waiting for tasks to complete...')
        terminal_states = executor.wait(terminal_states)

        # depending on the flag, we return all states or just terminal states
        if return_all_task_states:
            result_states = executor.wait(task_states)
        else:
            result_states = terminal_states

        if any(s.is_failed() for s in terminal_states.values()):
            self.logger.info('FlowRun FAIL: Some terminal tasks failed.')
            self.set_state(
                executor, state, FlowRunState.FAILED, result=result_states)
        elif all(s.is_successful() for s in terminal_states.values()):
            self.logger.info('FlowRun SUCCESS: All terminal tasks succeeded.')
            self.set_state(
                executor, state, FlowRunState.SUCCESS, result=result_states)
        elif all(s.is_finished() for s in terminal_states.values()):
            self.logger.info(
                'FlowRun SUCCESS: All terminal tasks finished and none failed.')
            self.set_state(
                executor, state, FlowRunState.SUCCESS, result=result_states)
        else:
            self.logger.info('FlowRun PENDING: Terminal tasks are incomplete.')
            self.set_state(
                executor, state, FlowRunState.PENDING, result=result_states)

        return state

    def set_state(self, executor, state, new_state, result=None):
        """
        Update a state object with a new state and optional result.
        """
        executor.set_state(state, new_state, result=result)

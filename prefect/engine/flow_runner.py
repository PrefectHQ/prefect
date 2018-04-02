import logging
from contextlib import contextmanager

import prefect
import prefect.signals
from prefect.engine.state import FlowRunState, TaskRunState


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
        self.logger = logging.getLogger(logger_name)

    @contextmanager
    def catch_signals(self, state):
        try:
            yield

        except prefect.signals.ParameterError as s:
            self.logger.info('Flow {}: {}'.format(type(s).__name__, s))
            self.executor.set_state(
                state=state, new_state=FlowRunState.FAILED, result=str(s))

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
            self.executor.set_state(
                state=state, new_state=FlowRunState.FAILED, result={})

    def run(
            self,
            state: FlowRunState = None,
            task_states: dict = None,
            start_tasks: list = None,
            parameters: dict = None,
            context: dict = None,
            task_contexts: dict = None,
            override_task_inputs: dict = None,
            return_all_task_states: bool = False,
    ):
        """
        Arguments

            task_states (dict): a dictionary of { task: TaskRunState }
                pairs representing the initial states of the FlowRun tasks.

            start_tasks (list): a list of task names indicating the tasks
                that should be run first. Only tasks downstream of these will
                be run.

            parameters (dict): a dictionary of { parameter_name: value } pairs
                indicating parameter values for the Flow run.

            override_task_inputs (dict): a dictionary of
                { task: {upstream_task: input_value } } pairs
                indicating that a given task's upstream task's reuslt should be
                overwritten with the supplied input

            task_contexts (dict): a dict of { task : context_dict } pairs
                that contains items that should be provided to each task's
                context.
        """

        state = FlowRunState(state)
        task_states = task_states or {}
        override_task_inputs = override_task_inputs or {}
        parameters = parameters or {}
        context = context or {}
        task_contexts = task_contexts or {}

        context.setdefault('parameters', {}).update(parameters)

        context.update(flow_name=self.flow.name, flow_version=self.flow.version)

        # prepare context
        with prefect.context(context) as ctx:

            # set up executor context
            with self.executor.execution_context():

                # catch any signals
                with self.catch_signals(state=state):

                    # check for parameters
                    required_params = {
                        name
                        for name, details in self.flow.parameters().items()
                        if details['required']
                    }
                    missing = set(required_params).difference(ctx.parameters)
                    if missing:
                        raise prefect.signals.ParameterError(
                            'Required parameters not provided: {}'.format(
                                missing))

                    self._check_flow_state(state)

                    state = self._run_flow(
                        state=state,
                        task_states=task_states,
                        start_tasks=start_tasks,
                        task_contexts=task_contexts,
                        override_task_inputs=override_task_inputs,
                        return_all_task_states=return_all_task_states)

        return state

    def _check_flow_state(self, state):
        """
        Check if the flow is ready to run.
        """

        # this flow is already finished
        if state.is_finished():
            raise prefect.signals.DONTRUN('Flow run is already finished.')

        # this flow isn't pending or already running
        elif not (state.is_pending() or state.is_running()):
            raise prefect.signals.DONTRUN(
                'Flow is not ready to run (state {}).'.format(state))

        # start!
        self.logger.info('Starting FlowRun.')
        self.executor.set_state(state, FlowRunState.RUNNING)

    def _run_flow(
            self,
            state,
            start_tasks,
            task_states,
            task_contexts,
            override_task_inputs,
            return_all_task_states,
    ):

        # process each task in order
        for task in self.flow.sorted_tasks(root_tasks=start_tasks):
            self.logger.info('Running task: {}'.format(task))

            # if the task is unrecognized, create a placeholder State
            if task not in task_states:
                task_states[task] = TaskRunState()

            upstream_states = {}
            upstream_inputs = {}

            # process each edge
            for edge in self.flow.edges_to(task):

                # gather upstream states
                upstream_states[edge.upstream_task] = task_states[
                    edge.upstream_task]

                # if the edge has a key, get the upstream result
                if edge.key is not None:
                    upstream_inputs[edge.key] = self.executor.submit(
                        lambda state: state.result,
                        task_states[edge.upstream_task])

            # override upstream_inputs with provided override_task_inputs
            upstream_inputs.update(override_task_inputs.get(task, {}))

            # run the task!
            with prefect.context(task_contexts.get(task, {})) as context:
                task_states[task] = self.executor.run_task(
                    task=task,
                    state=task_states[task],
                    upstream_states=upstream_states,
                    inputs=upstream_inputs,
                    ignore_trigger=(task in (start_tasks or [])),
                    context=context)

        # gather the results for all tasks
        self.logger.info('Waiting for tasks to complete...')
        results = self.executor.wait(task_states)

        # gather the results for terminal tasks
        terminal = {task: results[task] for task in self.flow.terminal_tasks()}

        # depending on the flag, we return all states or just
        # terminal/failed states
        if not return_all_task_states:
            results = {t: s for t, s in results.items() if s.is_failed()}
            results.update(terminal)

        # handle flow state
        if any(s.is_failed() for s in terminal.values()):
            self.logger.info('FlowRun FAILED: Some terminal tasks failed.')
            self.executor.set_state(state, FlowRunState.FAILED, result=results)
        elif all(s.is_successful() for s in terminal.values()):
            self.logger.info('FlowRun SUCCESS: All terminal tasks succeeded.')
            self.executor.set_state(state, FlowRunState.SUCCESS, result=results)
        elif all(s.is_finished() for s in terminal.values()):
            self.logger.info(
                'FlowRun SUCCESS: All terminal tasks finished and none failed.')
            self.executor.set_state(state, FlowRunState.SUCCESS, result=results)
        else:
            self.logger.info('FlowRun PENDING: Terminal tasks are incomplete.')
            self.executor.set_state(state, FlowRunState.PENDING, result=results)

        return state

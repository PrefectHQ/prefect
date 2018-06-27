import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Union

import prefect
import prefect.signals
from prefect.core import Flow, Task
from prefect.engine.state import State


class FlowRunner:
    def __init__(
        self,
        flow: Flow,
        executor: "prefect.engine.executors.Executor" = None,
        logger_name: str = None,
    ) -> None:
        self.flow = flow
        self.executor = executor or prefect.engine.executors.LocalExecutor()
        self.logger = logging.getLogger(logger_name)

    def run(
        self,
        state: State = None,
        task_states: Dict[Task, State] = None,
        start_tasks: Iterable[Task] = None,
        return_tasks: Iterable[Task] = None,
        parameters: Dict[str, Any] = None,
        context: Dict[str, Any] = None,
    ) -> State:

        if state is None:
            state = State()
        parameters = parameters or {}
        task_states = task_states or {}
        start_tasks = start_tasks or []
        context = context or {}
        return_tasks = set(return_tasks or [])

        context.update(
            flow_name=self.flow.name,
            flow_version=self.flow.version,
            parameters=parameters,
        )

        # if the run fails for any reason,
        return_task_states = {t: task_states.get(t, State()) for t in return_tasks}

        with prefect.context(context):

            with self.executor.start():

                try:
                    state = self._run(
                        state=state,
                        task_states=task_states,
                        start_tasks=start_tasks,
                        return_tasks=return_tasks,
                        parameters=parameters,
                    )
                except prefect.signals.DONTRUN:
                    self.logger.info("Flow run DONTRUN")
                    # set state but no need to go through the executor
                    state = State(state.state, data=return_task_states)
                except Exception:
                    self.logger.info("Flow run FAIL")
                    # set state through executor
                    state = self.executor.set_state(
                        state, State.FAILED, data=return_task_states
                    )

        return state

    def _run(
        self,
        state: State,
        task_states: Dict[Task, State],
        start_tasks: Iterable[Task],
        return_tasks: Iterable[Task],
        parameters: Dict[str, Any],
    ) -> State:

        # ---------------------------------------------
        # Check for required parameters
        # ---------------------------------------------

        required_params = self.flow.parameters(only_required=True)
        missing = set(required_params).difference(prefect.context.get("parameters", []))
        if missing:
            raise ValueError("Required parameters not provided: {}".format(missing))

        # ---------------------------------------------
        # Check if the flow run is ready to run
        # ---------------------------------------------

        # this flow run is already finished
        if state.is_finished():
            raise prefect.signals.DONTRUN("Flow run has already finished.")

        # this must be pending or running
        elif not (state.is_pending() or state.is_running()):
            raise prefect.signals.DONTRUN("Flow is not ready to run.")

        # ---------------------------------------------
        # Start!
        # ---------------------------------------------

        # update state
        state = self.executor.set_state(state, state=State.RUNNING)

        # -- process each task in order
        for task in self.flow.sorted_tasks(root_tasks=start_tasks):

            upstream_states = {}
            upstream_inputs = {}

            # -- process each edge to the task
            for edge in self.flow.edges_to(task):

                # extract upstream state to pass to the task trigger
                upstream_states[edge.upstream_task] = self.executor.submit(
                    lambda s: State(s.state), task_states[edge.upstream_task]
                )

                # if the upstream task is supposed to pass data, then extract the data
                # into the inputs dict -- but only if the task was successful (otherwise the
                # data attribute may contain information for an error state)
                # TODO add a test for this
                if edge.key:
                    upstream_inputs[edge.key] = self.executor.submit(
                        lambda s: s.data if s.state == State.SUCCESS else None,
                        task_states[edge.upstream_task],
                    )

            # -- run the task
            task_states[task] = self.executor.run_task(
                task=task,
                state=task_states.get(task),
                upstream_states=upstream_states,
                inputs=upstream_inputs,
                ignore_trigger=(task in start_tasks),
            )

        # ---------------------------------------------
        # Collect results
        # ---------------------------------------------

        terminal_states = self.executor.wait(
            {task_states[t] for t in self.flow.terminal_tasks()}
        )
        return_states = self.executor.wait({t: task_states[t] for t in return_tasks})

        if any(s.is_failed() for s in terminal_states):
            self.logger.info("Flow run FAILED: some terminal tasks failed.")
            state = self.executor.set_state(
                state, state=State.FAILED, data=return_states
            )

        elif all(s.is_successful() for s in terminal_states):
            self.logger.info("Flow run SUCCESS: all terminal tasks succeeded")
            state = self.executor.set_state(
                state, state=State.SUCCESS, data=return_states
            )

        elif all(s.is_finished() for s in terminal_states):
            self.logger.info("Flow run SUCCESS: all terminal tasks done; none failed.")
            state = self.executor.set_state(
                state, state=State.SUCCESS, data=return_states
            )

        else:
            self.logger.info("Flow run PENDING: terminal tasks are incomplete.")
            state = self.executor.set_state(
                state, state=State.PENDING, data=return_states
            )

        return state

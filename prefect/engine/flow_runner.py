import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Union, Iterator, Callable

import prefect
from prefect import signals
from prefect.core import Flow, Task
from prefect.engine.state import State, Failed, Pending, Running, Success


def handle_signals(method: Callable) -> Callable:
    """
    This handler is used to decorate methods that return States but might raise
    Prefect signals.

    The handler attempts to run the method, and if a signal is raised, the appropriate
    state is returned.

    If DONTRUN is raised, it is re-raised because no new state should be set in that case.
    """

    def inner(self, *args, **kwargs) -> State:

        raise_on_fail = prefect.context.get("_raise_on_fail", False)

        try:
            return method(self, *args, **kwargs)

        # DONTRUN is re-raised to be caught elsewhere
        except signals.DONTRUN as exc:
            logging.debug("DONTRUN signal raised: {}".format(exc))
            raise exc

        except signals.FAIL as exc:
            logging.debug("FAIL signal raised.")
            if raise_on_fail:
                raise exc
            return Failed(data=exc.result, message=exc)

        except Exception as exc:
            logging.debug("Unexpected error while running flow.")
            if raise_on_fail:
                raise exc
            return Failed(message=exc)

    return inner


class FlowRunner:
    def __init__(self, flow: Flow, logger_name: str = None) -> None:
        self.flow = flow
        self.logger = logging.getLogger(logger_name)

    @contextmanager
    def flow_context(self, **kwargs: Any) -> Iterator[None]:
        with prefect.context(
            _flow_name=self.flow.name, _flow_version=self.flow.version, **kwargs
        ):
            yield

    def run(
        self,
        state: State = None,
        task_states: Dict[Task, State] = None,
        start_tasks: Iterable[Task] = None,
        return_tasks: Iterable[Task] = None,
        parameters: Dict[str, Any] = None,
        executor: "prefect.engine.executors.Executor" = None,
    ) -> State:

        state = state or Pending()

        try:
            checked_state = self._check_state(state=state, parameters=parameters)
            return self._run_flow(
                state=checked_state,
                task_states=task_states or {},
                start_tasks=start_tasks or {},
                return_tasks=set(return_tasks or []),
                parameters=parameters or {},
                executor=executor or prefect.engine.executors.LocalExecutor(),
            )
        except signals.DONTRUN:
            return state


    @handle_signals
    def _check_state(self, state: State, parameters: Dict[str, Any]):

        with self.flow_context():
            # ---------------------------------------------
            # Check for required parameters
            # ---------------------------------------------

            required_parameters = self.flow.parameters(only_required=True)
            missing = set(required_parameters).difference(parameters)
            if missing:
                return Failed(
                    message="Required parameters were not provided: {}".format(missing)
                )

            # ---------------------------------------------
            # Check if the flow run is ready to run
            # ---------------------------------------------

            # the flow run is already finished
            if state.is_finished():
                raise signals.DONTRUN("Flow run has already finished.")

            # the flow run must be either pending or running (possibly redundant with above)
            elif not (state.is_pending() or state.is_running()):
                raise signals.DONTRUN("Flow is not ready to run.")

            # ---------------------------------------------
            # Start!
            # ---------------------------------------------
            return Running()

    @handle_signals
    def _run_flow(
        self,
        state: State,
        task_states: Dict[Task, State],
        start_tasks: Iterable[Task],
        return_tasks: Iterable[Task],
        parameters: Dict[str, Any] = None,
        executor: "prefect.engine.executors.Executor" = None,
    ) -> State:

        with self.flow_context(_parameters=parameters):

            # -- process each task in order
            for task in self.flow.sorted_tasks(root_tasks=start_tasks):

                upstream_states = {}
                upstream_inputs = {}

                # -- process each edge to the task
                for edge in self.flow.edges_to(task):

                    # upstream states to pass to the task trigger
                    upstream_states[edge.upstream_task] = task_states[
                        edge.upstream_task
                    ]

                    # extract data from upstream states that pass data
                    # note this will extract data even if the upstream state wasn't successful
                    if edge.key:
                        upstream_inputs[edge.key] = executor.submit(
                            lambda s: s.data, task_states[edge.upstream_task]
                        )

                # -- run the task
                task_states[task] = executor.run_task(
                    task=task,
                    state=task_states.get(task),
                    upstream_states=upstream_states,
                    inputs=upstream_inputs,
                    ignore_trigger=(task in start_tasks),
                )

            # ---------------------------------------------
            # Collect results
            # ---------------------------------------------

            terminal_states = executor.wait(
                {task_states[t] for t in self.flow.terminal_tasks()}
            )
            return_states = executor.wait({t: task_states[t] for t in return_tasks})

            if any(s.is_failed() for s in terminal_states):
                self.logger.info("Flow run FAILED: some terminal tasks failed.")
                state = Failed(
                    message="Some terminal tasks failed.", data=return_states
                )

            elif all(s.is_successful() for s in terminal_states):
                self.logger.info("Flow run SUCCESS: all terminal tasks succeeded")
                state = Success(
                    message="All terminal tasks succeeded.", data=return_states
                )

            else:
                self.logger.info("Flow run PENDING: terminal tasks are incomplete.")
                state = Pending(
                    message="Some terminal tasks are still pending.", data=return_states
                )

            return state

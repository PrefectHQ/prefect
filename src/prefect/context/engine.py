from contextvars import ContextVar
from typing import (
    Any,
    Dict,
    Optional,
)

from pydantic import Field

from prefect.client.schemas import FlowRun
from prefect.events.worker import EventsWorker
from prefect.flows import Flow
from prefect.results import ResultFactory
from prefect.states import State
from prefect.task_runners import TaskRunner

from .run import RunContext


class EngineContext(RunContext):
    """
    The context for a flow run. Data in this context is only available from within a
    flow run function.

    Attributes:
        flow: The flow instance associated with the run
        flow_run: The API metadata for the flow run
        task_runner: The task runner instance being used for the flow run
        task_run_futures: A list of futures for task runs submitted within this flow run
        task_run_states: A list of states for task runs created within this flow run
        task_run_results: A mapping of result ids to task run states for this flow run
        flow_run_states: A list of states for flow runs created within this flow run
    """

    flow: Optional["Flow"] = None
    flow_run: Optional[FlowRun] = None
    task_runner: TaskRunner
    log_prints: bool = False
    parameters: Optional[Dict[str, Any]] = None

    # Flag signaling if the flow run context has been serialized and sent
    # to remote infrastructure.
    detached: bool = False

    # Result handling
    result_factory: ResultFactory

    # Counter for task calls allowing unique
    task_run_dynamic_keys: Dict[str, int] = Field(default_factory=dict)

    # Counter for flow pauses
    observed_flow_pauses: Dict[str, int] = Field(default_factory=dict)

    # Tracking for result from task runs in this flow run
    task_run_results: Dict[int, State] = Field(default_factory=dict)

    # Events worker to emit events to Prefect Cloud
    events: Optional[EventsWorker] = None

    __var__: ContextVar = ContextVar("flow_run")

    def serialize(self):
        return self.model_dump(
            include={
                "flow_run",
                "flow",
                "parameters",
                "log_prints",
                "start_time",
                "input_keyset",
            },
            exclude_unset=True,
        )


FlowRunContext = EngineContext  # for backwards compatibility

from enum import Enum
from typing import Any, Optional, Callable
from uuid import UUID

from prefect.client import OrionClient
from prefect.orion.schemas.core import State, StateType
from prefect.orion.schemas.responses import SetStateResponse


class RunType(Enum):
    FlowRun = "FlowRun"
    TaskRun = "TaskRun"


class PrefectFuture:
    def __init__(
        self,
        run_id: UUID,
        run_type: RunType,
        client: OrionClient,
        wait_callback: Callable[[float], Optional[State]],
    ) -> None:
        self.run_id = run_id
        self.run_type = run_type
        self._client = client
        self._result: Any = None
        self._exception: Optional[Exception] = None
        self._wait_callback = wait_callback

        self.set_state(State(type=StateType.PENDING))

    @property
    def is_flow_run(self):
        self.run_type == RunType.FlowRun

    @property
    def is_task_run(self):
        self.run_type == RunType.TaskRun

    def result(self, timeout: float = None) -> State:
        """
        Return the state of the run the future represents
        """
        state = self.get_state()
        if state.is_done():
            return state

        result = self._wait_callback(timeout)

        return result

    def set_state(self, state: State) -> SetStateResponse:
        method = (
            self._client.set_flow_run_state
            if self.is_flow_run
            else self._client.set_task_run_state
        )
        return method(self.run_id, state)

    def get_state(self) -> State:
        method = (
            self._client.read_flow_run_states
            if self.is_flow_run
            else self._client.read_task_run_states
        )
        states = method(self.run_id)
        if not states:
            raise RuntimeError("Future has no associated state in the server.")
        return states[-1]

    def __hash__(self) -> int:
        return hash(self.run_id)

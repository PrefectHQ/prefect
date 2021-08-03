from typing import Any, Optional, Callable
from uuid import UUID

from prefect.client import OrionClient
from prefect.orion.schemas.states import State


class PrefectFuture:
    def __init__(
        self,
        flow_run_id: UUID,
        client: OrionClient,
        wait_callback: Callable[[float], Optional[State]],
        task_run_id: UUID = None,
    ) -> None:
        self.flow_run_id = flow_run_id
        self.task_run_id = task_run_id
        self.run_id = self.task_run_id or self.flow_run_id
        self._client = client
        self._result: Any = None
        self._exception: Optional[Exception] = None
        self._wait_callback = wait_callback

    def result(self, timeout: float = None) -> State:
        """
        Return the state of the run the future represents
        """
        # TODO: Since states in the backend don't have data attached yet this will
        # return a state without data
        # state = self.get_state()
        # if state.is_done():
        #     return state

        result = self._wait_callback(timeout)

        return result

    def get_state(self) -> State:
        method = (
            self._client.read_task_run_states
            if self.task_run_id
            else self._client.read_flow_run_states
        )
        states = method(self.run_id)
        if not states:
            raise RuntimeError("Future has no associated state in the server.")
        return states[-1]

    def __hash__(self) -> int:
        return hash(self.run_id)

import threading
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from prefect.client import OrionClient
from prefect.orion.schemas.core import State, StateType
from prefect.orion.schemas.responses import SetStateResponse


class RunType(Enum):
    FlowRun = "FlowRun"
    TaskRun = "TaskRun"


class PrefectFuture:
    def __init__(self, run_id: UUID, run_type: RunType, client: OrionClient) -> None:
        self.run_id = run_id
        self.run_type = run_type
        self._client = client
        self._result: Any = None
        self._exception: Optional[Exception] = None
        self._condition = threading.Condition()

        self.__set_state(State(type=StateType.PENDING))

    @property
    def is_flow_run(self):
        self.run_type == RunType.FlowRun

    @property
    def is_task_run(self):
        self.run_type == RunType.TaskRun

    def state(self) -> State:
        with self._condition:
            return self.__get_state()

    def result(self, timeout: float = None) -> Any:
        """
        Return the result of the run the future represents

        Raises an exception if the run failed with an exception
        """
        with self._condition:
            if self.__get_state().is_done():
                return self.__get_result()

            self._condition.wait(timeout)

            if self.__get_state().is_done():
                return self.__get_result()
            else:
                raise TimeoutError()

    def exception(self, timeout: float = None) -> Optional[Exception]:
        """
        Return the exception raised by the run the future represents

        Returns None if the run completed successfully
        """
        with self._condition:
            if self.__get_state().is_done():
                return self._exception

            self._condition.wait(timeout)

            if self.__get_state().is_done():
                return self._exception
            else:
                raise TimeoutError()

    def set_running(self) -> None:
        with self._condition:
            self.__set_state(State(type=StateType.RUNNING))

    def set_result(self, result: Any) -> None:
        with self._condition:
            self._result = result
            self.__set_state(State(type=StateType.COMPLETED))
            self._condition.notify_all()

    def set_exception(self, exception: Exception) -> None:
        with self._condition:
            self._exception = exception
            self.__set_state(State(type=StateType.FAILED))
            self._condition.notify_all()

    def __hash__(self) -> int:
        # Ensure this is a hashable type
        return hash(self.run_id)

    # Unsafe methods -------------------------------------------------------------------
    # These methods do not use the lock and must be called from a locked context

    def __get_result(self) -> Any:
        if self._exception:
            raise self._exception
        else:
            return self._result

    def __set_state(self, state: State) -> SetStateResponse:
        method = (
            self._client.set_flow_run_state
            if self.is_flow_run
            else self._client.set_task_run_state
        )
        # TODO: Perhaps do some unwrapping of the `SetStateResponse`
        print(f"Setting state for {self.run_id} to {state.name!r}")
        return method(self.run_id, state)

    def __get_state(self) -> State:
        method = (
            self._client.read_flow_run_states
            if self.is_flow_run
            else self._client.read_task_run_states
        )
        states = method(self.run_id)
        if not states:
            raise RuntimeError("Future has no associated state in the server.")
        return states[-1]

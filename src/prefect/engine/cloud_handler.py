# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any, Optional

from prefect import config
from prefect.engine.state import State


class CloudHandler:
    def __init__(self) -> None:
        if config.get("prefect_cloud", None):
            self.load_prefect_client()

    def load_prefect_client(self) -> None:
        client = Client()
        client.login(email=config.email, password=config.password)

        self.flow_runs_gql = FlowRuns(client=client)
        self.task_runs_gql = TaskRuns(client=client)

        self.flow_run_id = config.get("flow_run_id")

    def setFlowRunState(self, version: int, state: State) -> None:
        self.flow_runs_gql.set_state(
            flow_run_id=self.flow_run_id, state=state, version=version
        )

    def getFlowRunVersion(self) -> int:
        gql_output = self.flow_runs_gql.query(flow_run_id=self.flow_run_id)
        return gql_output.flowRuns[0].version  # type: ignore

    def setTaskRunState(self, task_run_id: str, version: int, state: State) -> None:
        self.task_runs_gql.set_state(
            task_run_id=task_run_id, state=state, version=version
        )

    def getTaskRunIdAndVersion(self, task_id: Optional[str]) -> Any:
        gql_output = self.task_runs_gql.query(
            flow_run_id=self.flow_run_id, task_id=task_id
        )
        return gql_output.taskRuns[0]  # type: ignore

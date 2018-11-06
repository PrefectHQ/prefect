import os
import toml
from pathlib import Path
from typing import Any, Optional

from prefect import config
from prefect.client import Client, States
from prefect.engine.state import State


class CloudHandler:
    def __init__(self) -> None:
        if config.get("prefect_cloud", None):
            self.load_prefect_client()

    def load_prefect_client(self) -> None:
        client = Client(  # type: ignore
            config.api_url, os.path.join(config.api_url, "graphql/")
        )
        client.login(email=config.email, password=config.password)

        self.states_gql = States(client=client)

        self.flow_run_id = config.get("flow_run_id", None)

    def setFlowRunState(self, version: int, state: State) -> None:
        self.states_gql.set_flow_run_from_serialized_state(
            self.flow_run_id, version, state
        )

    def getFlowRunVersion(self) -> int:
        gql_output = self.states_gql.query_flow_run_version(self.flow_run_id)
        return gql_output.flowRuns[0].version  # type: ignore

    def setTaskRunState(self, task_run_id: str, version: int, state: State) -> None:
        self.states_gql.set_task_run_from_serialized_state(task_run_id, version, state)

    def getTaskRunIdAndVersion(self, task_id: Optional[str]) -> Any:
        gql_output = self.states_gql.query_task_run_id_and_version(
            self.flow_run_id, task_id
        )
        return gql_output.taskRuns[0]  # type: ignore

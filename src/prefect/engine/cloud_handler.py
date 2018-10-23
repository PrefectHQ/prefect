import os
from pathlib import Path
import toml

from prefect import config
from prefect.client import Client, States
from prefect.engine.state import State


class CloudHandler:
    def __init__(self):
        self.client = None
        self.states_gql = None
        self.flow_run_id = None

    def load_prefect_config(self):
        path = os.path.join(os.getenv("HOME"), ".prefect/config.toml")

        if Path(path).is_file():
            config_data = toml.load(path)

        if not config_data:
            raise Exception(
                "Prefect Cloud not configured. Run 'prefect configure init'"
            )

        self.client = Client(
            config_data["API_URL"], os.path.join(config_data["API_URL"], "graphql/")
        )
        self.client.login(email=config_data["EMAIL"], password=config_data["PASSWORD"])

        self.states_gql = States(client=self.client)

        self.flow_run_id = config.get("flow_run_id", None)

    def setFlowRunState(self, version, state: State):
        self.states_gql.set_flow_run_from_serialized_state(
            self.flow_run_id, version, state
        )

    def getFlowRunVersion(self):
        gql_output = self.states_gql.query_flow_run_version(self.flow_run_id)
        return gql_output.flowRuns[0].version

    def setTaskRunState(self, task_run_id, version, state):
        self.states_gql.set_task_run_from_serialized_state(task_run_id, version, state)

    def getTaskRunIdAndVersion(self, task_id):
        gql_output = self.states_gql.query_task_run_id_and_version(
            self.flow_run_id, task_id
        )
        return gql_output.taskRuns[0]

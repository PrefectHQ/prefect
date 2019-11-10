import os
from subprocess import PIPE, STDOUT, Popen
from typing import Iterable

from prefect import config, context
from prefect.agent import Agent
from prefect.environments.storage import Local
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class LocalAgent(Agent):
    """
    Agent which deploys flow runs locally as Docker containers. Information on using the
    Docker Agent can be found at https://docs.prefect.io/cloud/agent/docker.html

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
    """

    def __init__(self, name: str = None, labels: Iterable[str] = None,) -> None:
        self.processes = []
        super().__init__(name=name, labels=labels)

    def heartbeat(self) -> None:
        for idx, process in enumerate(self.processes):
            if process.poll() is not None:
                self.processes.pop(idx)
        super().heartbeat()

    def deploy_flows(self, flow_runs: list) -> None:
        """
        Deploy flow runs on your local machine as Docker containers

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        for flow_run in flow_runs:
            self.logger.info(
                "Deploying flow run {}".format(flow_run.id)  # type: ignore
            )

            storage = StorageSchema().load(flow_run.flow.storage)
            if not isinstance(StorageSchema().load(flow_run.flow.storage), Local):
                self.logger.error(
                    "Storage for flow run {} is not of type Local.".format(flow_run.id)
                )
                continue

            env_vars = self.populate_env_vars(flow_run=flow_run)
            current_env = os.environ.copy()
            current_env.update(env_vars)

            p = Popen(
                ["prefect", "execute", "cloud-flow"],
                stdout=PIPE,
                stderr=STDOUT,
                env=current_env,
            )
            self.processes.append(p)

    def populate_env_vars(self, flow_run: GraphQLResult) -> dict:
        """
        Populate metadata and variables in the environment variables for a flow run

        Args:
            - flow_run (GraphQLResult): A flow run object

        Returns:
            - dict: a dictionary representing the populated environment variables
        """
        return {
            "PREFECT__CLOUD__API": config.cloud.api,
            "PREFECT__CLOUD__AUTH_TOKEN": config.cloud.agent.auth_token,
            "PREFECT__CLOUD__AGENT__LABELS": str(self.labels),
            "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,  # type: ignore
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }


if __name__ == "__main__":
    LocalAgent().start()

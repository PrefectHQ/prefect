from sys import platform
from typing import Iterable

import docker

from prefect import config, context
from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class LocalAgent(Agent):
    """
    Agent which deploys flow runs locally. Information on using the
    Local Agent can be found at https://docs.prefect.io/cloud/agent/local.html

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
    """

    def __init__(self, name: str = None, labels: Iterable[str] = None,) -> None:
        super().__init__(name=name, labels=labels)

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
            if not isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
                self.logger.error(
                    "Storage for flow run {} is not of type Docker.".format(flow_run.id)
                )
                continue

            env_vars = self.populate_env_vars(flow_run=flow_run)

            if not self.no_pull and storage.registry_url:
                self.logger.info("Pulling image {}...".format(storage.name))
                try:
                    pull_output = self.docker_client.pull(
                        storage.name, stream=True, decode=True
                    )
                    for line in pull_output:
                        self.logger.debug(line)
                    self.logger.info(
                        "Successfully pulled image {}...".format(storage.name)
                    )
                except docker.errors.APIError as exc:
                    self.logger.error("Issue pulling image {}".format(storage.name))

            # Create a container
            self.logger.debug("Creating Docker container {}".format(storage.name))
            container = self.docker_client.create_container(
                storage.name, command="prefect execute cloud-flow", environment=env_vars
            )

            # Start the container
            self.logger.debug(
                "Starting Docker container with ID {}".format(container.get("Id"))
            )
            self.docker_client.start(container=container.get("Id"))


if __name__ == "__main__":
    LocalAgent().start()

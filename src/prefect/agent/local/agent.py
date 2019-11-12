from sys import platform
from typing import Iterable

import docker

from prefect import config, context
from prefect.agent import Agent
from prefect.engine.state import Failed
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class LocalAgent(Agent):
    """
    Agent which deploys flow runs locally as Docker containers. Information on using the
    Local Agent can be found at https://docs.prefect.io/cloud/agent/local.html

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - base_url (str, optional): URL for a Docker daemon server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as
            `tcp://0.0.0.0:2375` can be provided
        - no_pull (bool, optional): Flag on whether or not to pull flow images.
            Defaults to `False` if not provided here or in context.
    """

    def __init__(
        self,
        name: str = None,
        labels: Iterable[str] = None,
        base_url: str = None,
        no_pull: bool = None,
    ) -> None:
        super().__init__(name=name, labels=labels)

        if platform == "win32":
            default_url = "npipe:////./pipe/docker_engine"
        else:
            default_url = "unix://var/run/docker.sock"
        self.logger.debug(
            "Platform {} and default docker daemon {}".format(platform, default_url)
        )

        # Determine Daemon URL
        self.base_url = base_url or context.get("base_url", default_url)
        self.logger.debug("Base docker daemon url {}".format(self.base_url))

        # Determine pull specification
        self.no_pull = no_pull or context.get("no_pull", False)
        self.logger.debug("no_pull set to {}".format(self.no_pull))

        self.docker_client = docker.APIClient(base_url=self.base_url, version="auto")

        # Ping Docker daemon for connection issues
        try:
            self.logger.debug("Pinging docker daemon")
            self.docker_client.ping()
        except Exception as exc:
            self.logger.exception(
                "Issue connecting to the Docker daemon. Make sure it is running."
            )
            raise exc

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
                msg = "Storage for flow run {} is not of type Docker.".format(
                    flow_run.id
                )
                state_msg = "Agent {} failed to run flow: ".format(self.name) + msg
                self.client.set_flow_run_state(
                    flow_run.id, version=flow_run.version, state=Failed(state_msg)
                )
                self.logger.error(msg)
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
                    msg = "Issue pulling image {}".format(storage.name)
                    state_msg = (
                        "Agent {} failed to pull image for flow: ".format(self.name)
                        + msg
                    )
                    self.client.set_flow_run_state(
                        flow_run.id, version=flow_run.version, state=Failed(msg)
                    )
                    self.logger.error(msg)

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

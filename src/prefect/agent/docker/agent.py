from sys import platform
from typing import Iterable, List
import multiprocessing

import docker

from prefect import config, context
from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class DockerAgent(Agent):
    """
    Agent which deploys flow runs locally as Docker containers. Information on using the
    Docker Agent can be found at https://docs.prefect.io/cloud/agent/docker.html

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - env_vars (dict, optional): a dictionary of environment variables and values that will be set
            on each flow run that this agent submits for execution
        - base_url (str, optional): URL for a Docker daemon server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as
            `tcp://0.0.0.0:2375` can be provided
        - no_pull (bool, optional): Flag on whether or not to pull flow images.
            Defaults to `False` if not provided here or in context.
        - show_flow_logs (bool, optional): a boolean specifying whether the agent should re-route Flow run logs
            to stdout; defaults to `False`
    """

    def __init__(
        self,
        name: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        base_url: str = None,
        no_pull: bool = None,
        show_flow_logs: bool = False,
    ) -> None:
        super().__init__(name=name, labels=labels, env_vars=env_vars)

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

        self.failed_connections = 0
        self.docker_client = docker.APIClient(base_url=self.base_url, version="auto")
        self.show_flow_logs = show_flow_logs
        self.processes = []  # type: List[multiprocessing.Process]

        # Ping Docker daemon for connection issues
        try:
            self.logger.debug("Pinging docker daemon")
            self.docker_client.ping()
        except Exception as exc:
            self.logger.exception(
                "Issue connecting to the Docker daemon. Make sure it is running."
            )
            raise exc

    def heartbeat(self) -> None:
        try:
            if not self.docker_client.ping():
                raise RuntimeError("Unexpected Docker ping result")
            if self.failed_connections > 0:
                self.logger.info("Reconnected to Docker daemon")
            self.failed_connections = 0
        except Exception as exc:
            self.logger.warning("Failed heartbeat: {}".format(repr(exc)))
            self.failed_connections += 1

        if self.failed_connections >= 6:
            self.logger.error(
                "Cannot reconnect to Docker daemon. Agent is shutting down."
            )
            raise SystemExit()

    def on_shutdown(self) -> None:
        """
        Cleanup any child processes created for streaming logs. This is to prevent
        logs from displaying on the terminal after the agent exits.
        """
        for proc in self.processes:
            if proc.is_alive():
                proc.terminate()

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy flow runs on your local machine as Docker containers

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment

        Raises:
            - ValueError: if deployment attempted on unsupported Storage type
        """
        self.logger.info(
            "Deploying flow run {}".format(flow_run.id)  # type: ignore
        )

        storage = StorageSchema().load(flow_run.flow.storage)
        if not isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
            self.logger.error(
                "Storage for flow run {} is not of type Docker.".format(flow_run.id)
            )
            raise ValueError("Unsupported Storage type")

        env_vars = self.populate_env_vars(flow_run=flow_run)

        if not self.no_pull and storage.registry_url:
            self.logger.info("Pulling image {}...".format(storage.name))

            pull_output = self.docker_client.pull(
                storage.name, stream=True, decode=True
            )
            for line in pull_output:
                self.logger.debug(line)
            self.logger.info("Successfully pulled image {}...".format(storage.name))

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

        if self.show_flow_logs:
            proc = multiprocessing.Process(
                target=self.stream_container_logs,
                kwargs={"container_id": container.get("Id")},
            )

            proc.start()
            self.processes.append(proc)

        self.logger.debug("Docker container {} started".format(container.get("Id")))

        return "Container ID: {}".format(container.get("Id"))

    def stream_container_logs(self, container_id: str) -> None:
        for log in self.docker_client.logs(
            container=container_id, stream=True, follow=True
        ):
            print(str(log, "utf-8").rstrip())

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
            "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.log_to_cloud).lower(),
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
            **self.env_vars,
        }


if __name__ == "__main__":
    DockerAgent().start()

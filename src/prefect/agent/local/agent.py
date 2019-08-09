import docker

from prefect import config
from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class LocalAgent(Agent):
    """
    Agent which deploys flow runs locally as Docker containers.

    Args:
        - base_url (str, optional): URL for a Docker daemon server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as
            `tcp://0.0.0.0:2375` can be provided
    """

    def __init__(self, base_url: str = None) -> None:
        super().__init__()

        base_url = base_url or "unix://var/run/docker.sock"
        self.docker_client = docker.APIClient(base_url=base_url, version="auto")

        # Ping Docker daemon for connection issues
        try:
            self.docker_client.ping()
        except Exception as exc:
            self.logger.error(
                "Issue connecting to the Docker daemon. Make sure it is running."
            )
            raise exc

    def deploy_flows(self, flow_runs: list) -> None:
        """
        Deploy flow runs on to a k8s cluster as jobs

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        for flow_run in flow_runs:

            storage = StorageSchema().load(flow_run.flow.storage)
            if not isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
                self.logger.error(
                    f"Storage for flow run {flow_run.id} is not of type Docker."
                )
                continue

            env_vars = self.populate_env_vars(flow_run=flow_run)

            # Pull image if it doesn't exist locally
            self.docker_client.pull(storage.name)

            # Create a container
            container = self.docker_client.create_container(
                storage.name, command="prefect execute cloud-flow", environment=env_vars
            )

            # Start the container
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
            "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,  # type: ignore
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }


if __name__ == "__main__":
    LocalAgent().start()

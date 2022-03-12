from typing import Any, Dict, Iterable, List

import slugify

from prefect import config
from prefect.agent import Agent
from prefect.run_configs import VertexRun
from prefect.utilities.agent import get_flow_image, get_flow_run_command
from prefect.utilities.graphql import GraphQLResult


def get_client(client_options: dict) -> Any:
    from google.cloud import aiplatform

    return aiplatform.gapic.JobServiceClient(client_options=client_options)


class VertexAgent(Agent):
    """
    Agent which deploys flow runs as Vertex Training tasks.

    Args:
        - project (str): The project in which to submit the Vertex Jobs
            This does not necessarily need to be the same project as the where
            this agent is running, but the service account running the agent
            needs permissions to start Vertex Job in this project.
        - region_name (str, optional): Region the job is running in for the endpoint
        - service_account (str, optional): Service account to submit jobs as on Vertex
        - agent_config_id (str, optional): An optional agent configuration ID
            that can be used to set configuration based on an agent from a
            backend API. If set all configuration values will be pulled from
            the backend agent configuration.
        - name (str, optional): An optional name to give this agent. Can also
            be set through the environment variable `PREFECT__CLOUD__AGENT__NAME`.
            Defaults to "agent".
        - labels (List[str], optional): A list of labels, which are arbitrary
            string identifiers used by Prefect Agents when polling for work.
        - env_vars (dict, optional): A dictionary of environment variables and
            values that will be set on each flow run that this agent submits
            for execution.
        - max_polls (int, optional): Maximum number of times the agent will
            poll Prefect Cloud for flow runs; defaults to infinite.
        - agent_address (str, optional):  Address to serve internal api at.
            Currently this is just health checks for use by an orchestration
            layer. Leave blank for no api server (default).
        - no_cloud_logs (bool, optional): Disable logging to a Prefect backend
            for this agent and all deployed flow runs. Defaults to `False`.
    """

    def __init__(  # type: ignore
        self,
        project: str = None,
        region_name: str = None,
        service_account: str = None,
        agent_config_id: str = None,
        name: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        max_polls: int = None,
        agent_address: str = None,
        no_cloud_logs: bool = None,
    ) -> None:
        super().__init__(
            agent_config_id=agent_config_id,
            name=name,
            labels=labels,
            env_vars=env_vars,
            max_polls=max_polls,
            agent_address=agent_address,
            no_cloud_logs=no_cloud_logs,
        )
        if not project:
            import google.auth

            _, project = google.auth.default()
            if project is None:
                # protect against any edge cases where project cannot be determined via auth default
                raise google.auth.exceptions.DefaultCredentialsError(
                    "Project could not be determined from environment"
                )

        self.project = project

        if not region_name:
            region_name = "us-central1"

        self.region_name = region_name
        self.service_account = service_account

        # Initialize client that will be used to create and send requests.
        # This client only needs to be created once, and can be reused for multiple requests.
        self.client_options = {
            "api_endpoint": f"{self.region_name}-aiplatform.googleapis.com"
        }
        self.vertex_client = get_client(self.client_options)

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy a flow run as an Vertex task.

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment
        """
        taskdef = self.generate_task_definition(flow_run)
        parent = f"projects/{self.project}/locations/{self.region_name}"

        self.logger.debug(
            "Created task definition for flow %s",
            flow_run.flow.id,
        )

        resp = self.vertex_client.create_custom_job(parent=parent, custom_job=taskdef)
        self.logger.info(f"Created vertex job: {resp}")
        # The full name includes a projects key, to form the url we exclude it
        path = "/".join(resp.name.split("/")[2:]).replace("customJobs", "training")
        # return a url to navigate to the submitted flow
        url = f"https://console.cloud.google.com/vertex-ai/{path}"
        return url

    def generate_task_definition(self, flow_run: GraphQLResult) -> Dict[str, Any]:
        """Generate an Vertex task definition from a flow run

        Args:
            - flow_run (GraphQLResult): A flow run object

        Returns:
            - dict: a dictionary representation of an Vertex task definition
        """

        run_config = self._get_run_config(flow_run, VertexRun)
        assert isinstance(run_config, VertexRun)  # mypy

        image = get_flow_image(flow_run)
        job_name = slugify.slugify(
            flow_run.flow.name + "-" + flow_run.name,
            max_length=255,
            word_boundary=True,
            save_order=True,
        )
        machine_type = run_config.machine_type

        command = get_flow_run_command(flow_run)
        env = self.populate_env_vars(flow_run)
        env_list = self._to_env_list(env)

        # Start with a default taskdef
        taskdef = {
            "display_name": job_name,
            "job_spec": {
                "worker_pool_specs": [
                    {"machine_spec": {"machine_type": machine_type}, "replica_count": 1}
                ]
            },
        }  # type: Dict[str, Any]

        if run_config.worker_pool_specs is not None:
            taskdef["job_spec"]["worker_pool_specs"] = run_config.worker_pool_specs

        if run_config.network is not None:
            taskdef["job_spec"]["network"] = run_config.network

        if run_config.service_account is not None:
            taskdef["job_spec"]["service_account"] = run_config.service_account
        else:
            taskdef["job_spec"]["service_account"] = self.service_account

        if run_config.scheduling is not None:
            taskdef["job_spec"]["scheduling"] = run_config.scheduling

        # We always set the container spec on the zeroth pool spec to ensure it will run the flow
        taskdef["job_spec"]["worker_pool_specs"][0]["container_spec"] = {
            "image_uri": image,
            "command": command.split(),
            "args": [],
            "env": env_list,
        }

        return taskdef

    def populate_env_vars(self, flow_run: GraphQLResult) -> dict:
        """
        Populate metadata and variables in the environment variables for a flow run
        Args:
            - flow_run (GraphQLResult): A flow run object
            - image (str): The image for this flow
            - run_config (VertexRun, optional): The `run_config` for the flow, if any.
        Returns:
            - dict: a dictionary representing the populated environment variables
        """

        run_config = self._get_run_config(flow_run, VertexRun)

        env = {}
        # Populate environment variables, later sources overriding

        # 1. Logging level from config
        # Default to the config logging level, allowing it to be overriden
        # by later config soruces
        env.update({"PREFECT__LOGGING__LEVEL": config.logging.level})

        # 2. Values set on the agent via `--env`
        env.update(self.env_vars)

        # 3. Values set on a RunConfig (if present)
        if run_config is not None and run_config.env is not None:
            env.update(run_config.env)

        # 4. Non-overrideable required env vars
        env.update(
            {
                "PREFECT__BACKEND": config.backend,
                "PREFECT__CLOUD__API": config.cloud.api,
                "PREFECT__CLOUD__API_KEY": self.flow_run_api_key or "",
                "PREFECT__CLOUD__TENANT_ID": (
                    # Providing a tenant id is only necessary when authenticating
                    self.client.tenant_id
                    if self.flow_run_api_key
                    else ""
                ),
                "PREFECT__CLOUD__AGENT__LABELS": str(self.labels),
                "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": str(self.log_to_cloud).lower(),
                "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,  # type: ignore
                "PREFECT__CONTEXT__FLOW_ID": flow_run.flow.id,  # type: ignore
                "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
                "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
                "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
                # Backwards compatibility variable for containers on Prefect <0.15.0
                "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.log_to_cloud).lower(),
                # Backwards compatibility variable for containers on Prefect <1.0.0
                "PREFECT__CLOUD__AUTH_TOKEN": self.flow_run_api_key or "",
            }
        )
        return env

    def _to_env_list(self, env: dict) -> List[dict]:
        """Convert from dictionary to the expected vertex env list format"""
        env_list = []
        for k, v in env.items():
            env_list.append({"name": k, "value": v})
        return env_list

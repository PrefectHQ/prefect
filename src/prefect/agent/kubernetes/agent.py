import os
import sys
import uuid
from os import path

import pendulum
import yaml

import prefect
from prefect import config
from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult

AGENT_DIRECTORY = path.expanduser("~/.prefect/agent")


def check_heartbeat() -> None:
    """
    Check the agent's heartbeat by verifying heartbeat file has been recently modified
    """
    current_timestamp = pendulum.now().timestamp()
    last_modified_timestamp = path.getmtime("{}/heartbeat".format(AGENT_DIRECTORY))

    # If file has not been modified in the last 40 seconds then raise an exit code of 1
    if current_timestamp - last_modified_timestamp > 40:
        sys.exit(1)


class KubernetesAgent(Agent):
    """
    Agent which deploys flow runs as Kubernetes jobs. Currently this is required to either
    run on a k8s cluster or on a local machine where the kube_config is pointing at the
    desired cluster. Information on using the Kubernetes Agent can be found at
    https://docs.prefect.io/cloud/agent/kubernetes.html

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
    """

    def __init__(self, name: str = None) -> None:
        super().__init__(name=name)

        from kubernetes import client, config

        try:
            self.logger.debug("Loading incluster configuration")
            config.load_incluster_config()
        except config.config_exception.ConfigException as exc:
            self.logger.warning(
                "{} Using out of cluster configuration option.".format(exc)
            )
            self.logger.debug("Loading out of cluster configuration")
            config.load_kube_config()

        self.batch_client = client.BatchV1Api()

    def deploy_flows(self, flow_runs: list) -> None:
        """
        Deploy flow runs on to a k8s cluster as jobs

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        for flow_run in flow_runs:
            self.logger.debug(
                "Deploying flow run {}".format(flow_run.id)  # type: ignore
            )

            # Require Docker storage
            if not isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
                self.logger.error(
                    "Storage for flow run {} is not of type Docker.".format(flow_run.id)
                )
                continue

            job_spec = self.replace_job_spec_yaml(flow_run)

            self.logger.debug(
                "Creating namespaced job {}".format(job_spec["metadata"]["name"])
            )
            self.batch_client.create_namespaced_job(
                namespace=os.getenv("NAMESPACE", "default"), body=job_spec
            )

    def replace_job_spec_yaml(self, flow_run: GraphQLResult) -> dict:
        """
        Populate metadata and variables in the job_spec.yaml file for flow runs

        Args:
            - flow_run (GraphQLResult): A flow run object

        Returns:
            - dict: a dictionary representing the populated yaml object
        """
        with open(path.join(path.dirname(__file__), "job_spec.yaml"), "r") as job_file:
            job = yaml.safe_load(job_file)

        identifier = str(uuid.uuid4())[:8]
        job_name = "prefect-job-{}".format(identifier)

        # Populate job metadata for identification
        job["metadata"]["name"] = job_name
        job["metadata"]["labels"]["app"] = job_name
        job["metadata"]["labels"]["identifier"] = identifier
        job["metadata"]["labels"]["flow_run_id"] = flow_run.id  # type: ignore
        job["metadata"]["labels"]["flow_id"] = flow_run.flow.id  # type: ignore
        job["spec"]["template"]["metadata"]["labels"]["app"] = job_name
        job["spec"]["template"]["metadata"]["labels"][
            "flow_run_id"
        ] = flow_run.id  # type: ignore
        job["spec"]["template"]["metadata"]["labels"]["identifier"] = identifier

        # Use flow storage image for job
        job["spec"]["template"]["spec"]["containers"][0]["image"] = (
            StorageSchema().load(flow_run.flow.storage).name  # type: ignore
        )

        self.logger.debug(
            "Using image {} for job".format(
                StorageSchema().load(flow_run.flow.storage).name  # type: ignore
            )
        )

        # Populate environment variables for flow run execution
        env = job["spec"]["template"]["spec"]["containers"][0]["env"]

        env[0]["value"] = config.cloud.api or "https://api.prefect.io"
        env[1]["value"] = config.cloud.agent.auth_token
        env[2]["value"] = flow_run.id  # type: ignore
        env[3]["value"] = os.getenv("NAMESPACE", "default")

        # Use image pull secrets if provided
        job["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"] = os.getenv(
            "IMAGE_PULL_SECRETS", ""
        )

        return job

    @staticmethod
    def generate_deployment_yaml(
        token: str = None,
        api: str = None,
        namespace: str = None,
        image_pull_secrets: str = None,
        resource_manager_enabled: bool = False,
    ) -> str:
        """
        Generate and output an installable YAML spec for the agent.

        Args:
            - token (str, optional): A `RUNNER` token to give the agent
            - api (str, optional): A URL pointing to the Prefect API. Defaults to
                `https://api.prefect.io`
            - namespace (str, optional): The namespace to create Prefect jobs in. Defaults
                to `default`
            - image_pull_secrets (str, optional): The name of an image pull secret to use
                for Prefect jobs
            - resource_manager_enabled (bool, optional): Whether to include the resource
                manager as part of the YAML. Defaults to `False`

        Returns:
            - str: A string representation of the generated YAML
        """

        # Use defaults if not provided
        token = token or ""
        api = api or "https://api.prefect.io"
        namespace = namespace or "default"

        version = prefect.__version__.split("+")
        image_version = "latest" if len(version) > 1 else version[0]

        with open(
            path.join(path.dirname(__file__), "deployment.yaml"), "r"
        ) as deployment_file:
            deployment = yaml.safe_load(deployment_file)

        agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

        agent_env[0]["value"] = token
        agent_env[1]["value"] = api
        agent_env[2]["value"] = namespace

        # Use local prefect version for image
        deployment["spec"]["template"]["spec"]["containers"][0][
            "image"
        ] = "prefecthq/prefect:{}".format(image_version)

        # Populate resource manager if requested
        if resource_manager_enabled:
            resource_manager_env = deployment["spec"]["template"]["spec"]["containers"][
                1
            ]["env"]

            resource_manager_env[0]["value"] = token
            resource_manager_env[1]["value"] = api
            resource_manager_env[3]["value"] = namespace

            # Use local prefect version for image
            deployment["spec"]["template"]["spec"]["containers"][1][
                "image"
            ] = "prefecthq/prefect:{}".format(image_version)
        else:
            del deployment["spec"]["template"]["spec"]["containers"][1]

        # Populate image pull secrets if provided
        if image_pull_secrets:
            agent_env = deployment["spec"]["template"]["spec"]["imagePullSecrets"][0][
                "name"
            ] = image_pull_secrets
        else:
            del deployment["spec"]["template"]["spec"]["imagePullSecrets"]

        return yaml.safe_dump(deployment)

    def heartbeat(self) -> None:
        """
        Write agent heartbeat by opening and closing a heartbeat file. This allows
        liveness probes to check the agent's main process activity based on the
        heartbeat file's last modified time.
        """
        os.makedirs(AGENT_DIRECTORY, exist_ok=True)

        open("{}/heartbeat".format(AGENT_DIRECTORY), "w").close()


if __name__ == "__main__":
    KubernetesAgent().start()

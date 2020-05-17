import os
import uuid
from os import path
from typing import Iterable

import yaml

import prefect
from prefect import config
from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult

AGENT_DIRECTORY = path.expanduser("~/.prefect/agent")


class KubernetesAgent(Agent):
    """
    Agent which deploys flow runs as Kubernetes jobs. Currently this is required to either
    run on a k8s cluster or on a local machine where the kube_config is pointing at the
    desired cluster. Information on using the Kubernetes Agent can be found at
    https://docs.prefect.io/orchestration/agents/kubernetes.html

    Environment variables may be set on the agent to be provided to each flow run's job:
    ```
    prefect agent start kubernetes --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR
    ```

    Specifying a namespace for the agent will create flow run jobs in that namespace:
    ```
    prefect agent start kubernetes --namespace dev
    ```

    Args:
        - namespace (str, optional): A Kubernetes namespace to create jobs in. Defaults
            to the environment variable `NAMESPACE` or `default`.
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - env_vars (dict, optional): a dictionary of environment variables and values that will be set
            on each flow run that this agent submits for execution
        - max_polls (int, optional): maximum number of times the agent will poll Prefect Cloud for flow runs;
            defaults to infinite
        - agent_address (str, optional):  Address to serve internal api at. Currently this is
            just health checks for use by an orchestration layer. Leave blank for no api server (default).
        - no_cloud_logs (bool, optional): Disable logging to a Prefect backend for this agent and all deployed flow runs
    """

    def __init__(
        self,
        namespace: str = None,
        name: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        max_polls: int = None,
        agent_address: str = None,
        no_cloud_logs: bool = False,
    ) -> None:
        super().__init__(
            name=name,
            labels=labels,
            env_vars=env_vars,
            max_polls=max_polls,
            agent_address=agent_address,
            no_cloud_logs=no_cloud_logs,
        )

        self.namespace = namespace

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

        self.logger.debug(f"Namespace: {self.namespace}")

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy flow runs on to a k8s cluster as jobs

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

        # Require Docker storage
        if not isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
            self.logger.error(
                "Storage for flow run {} is not of type Docker.".format(flow_run.id)
            )
            raise ValueError("Unsupported Storage type")

        job_spec = self.replace_job_spec_yaml(flow_run)

        self.logger.debug(
            "Creating namespaced job {}".format(job_spec["metadata"]["name"])
        )
        job = self.batch_client.create_namespaced_job(
            namespace=self.namespace or os.getenv("NAMESPACE", "default"), body=job_spec
        )

        self.logger.debug("Job {} created".format(job.metadata.name))

        return "Job {}".format(job.metadata.name)

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
        env[3]["value"] = flow_run.flow.id  # type: ignore
        env[4]["value"] = os.getenv("NAMESPACE", "default")
        env[5]["value"] = str(self.labels)
        env[6]["value"] = str(self.log_to_cloud).lower()

        # append all user provided values
        for key, value in self.env_vars.items():
            env.append(dict(name=key, value=value))

        # Use image pull secrets if provided
        job["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"] = os.getenv(
            "IMAGE_PULL_SECRETS", ""
        )

        # Set resource requirements if provided
        resources = job["spec"]["template"]["spec"]["containers"][0]["resources"]
        if os.getenv("JOB_MEM_REQUEST"):
            resources["requests"]["memory"] = os.getenv("JOB_MEM_REQUEST")
        if os.getenv("JOB_MEM_LIMIT"):
            resources["limits"]["memory"] = os.getenv("JOB_MEM_LIMIT")
        if os.getenv("JOB_CPU_REQUEST"):
            resources["requests"]["cpu"] = os.getenv("JOB_CPU_REQUEST")
        if os.getenv("JOB_CPU_LIMIT"):
            resources["limits"]["cpu"] = os.getenv("JOB_CPU_LIMIT")

        return job

    @staticmethod
    def generate_deployment_yaml(
        token: str = None,
        api: str = None,
        namespace: str = None,
        image_pull_secrets: str = None,
        resource_manager_enabled: bool = False,
        rbac: bool = False,
        latest: bool = False,
        mem_request: str = None,
        mem_limit: str = None,
        cpu_request: str = None,
        cpu_limit: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        backend: str = None,
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
            - rbac (bool, optional): Whether to include default RBAC configuration as
                part of the YAML. Defaults to `False`
            - latest (bool, optional): Whether to use the `latest` Prefect image.
                Defaults to `False`
            - mem_request (str, optional): Requested memory for Prefect init job.
            - mem_limit (str, optional): Limit memory for Prefect init job.
            - cpu_request (str, optional): Requested CPU for Prefect init job.
            - cpu_limit (str, optional): Limit CPU for Prefect init job.
            - labels (List[str], optional): a list of labels, which are arbitrary string
                identifiers used by Prefect Agents when polling for work
            - env_vars (dict, optional): additional environment variables to attach to all
                jobs created by this agent
            - backend (str, optional): toggle which backend to use for this agent.
                Defaults to backend currently set in config.

        Returns:
            - str: A string representation of the generated YAML
        """

        # Use defaults if not provided
        token = token or ""
        api = api or "https://api.prefect.io"
        namespace = namespace or "default"
        labels = labels or []
        mem_request = mem_request or ""
        mem_limit = mem_limit or ""
        cpu_request = cpu_request or ""
        cpu_limit = cpu_limit or ""
        backend = backend or config.backend

        version = prefect.__version__.split("+")
        image_version = (
            "latest" if len(version) > 1 or latest else (version[0] + "-python3.6")
        )

        with open(
            path.join(path.dirname(__file__), "deployment.yaml"), "r"
        ) as deployment_file:
            deployment = yaml.safe_load(deployment_file)

        agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

        # Populate env vars
        agent_env[0]["value"] = token
        agent_env[1]["value"] = api
        agent_env[2]["value"] = namespace
        agent_env[3]["value"] = image_pull_secrets or ""
        agent_env[4]["value"] = str(labels)
        agent_env[9]["value"] = backend

        # Populate job resource env vars
        agent_env[5]["value"] = mem_request
        agent_env[6]["value"] = mem_limit
        agent_env[7]["value"] = cpu_request
        agent_env[8]["value"] = cpu_limit

        if env_vars:
            for k, v in env_vars.items():
                agent_env.append(
                    {"name": f"PREFECT__CLOUD__AGENT__ENV_VARS__{k}", "value": v}
                )

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

        # Load RBAC if specified
        rbac_yaml = []
        if rbac:
            with open(path.join(path.dirname(__file__), "rbac.yaml"), "r") as rbac_file:
                rbac_generator = yaml.safe_load_all(rbac_file)

                for document in rbac_generator:
                    document["metadata"]["namespace"] = namespace
                    rbac_yaml.append(document)

        output_yaml = [deployment]
        output_yaml.extend(rbac_yaml)
        return yaml.safe_dump_all(output_yaml, explicit_start=True)


if __name__ == "__main__":
    KubernetesAgent().start()

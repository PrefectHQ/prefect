import os
from os import path
import uuid
from typing import Iterable, List

import json
import yaml

import prefect
from prefect import config
from prefect.agent import Agent
from prefect.engine.state import Failed
from prefect.utilities.agent import get_flow_image, get_flow_run_command
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

    These can also be used to control the k8s job spec that describes the flow run jobs.
    For example, to set the k8s secret used to pull images from a non-public registry:
    ```
    prefect agent start kubernetes --env IMAGE_PULL_SECRETS=my-img-pull-secret
    ```

    For details on the available environment variables for customizing the job spec,
    see `help(KubernetesAgent.replace_job_spec_yaml)`.

    Specifying a namespace for the agent will create flow run jobs in that namespace:
    ```
    prefect agent start kubernetes --namespace dev
    ```

    Args:
        - namespace (str, optional): A Kubernetes namespace to create jobs in. Defaults
            to the environment variable `NAMESPACE` or `default`.
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
        - env_vars (dict, optional): a dictionary of environment variables and values that will
            be set on each flow run that this agent submits for execution and in the agent's
            own environment
        - max_polls (int, optional): maximum number of times the agent will poll Prefect Cloud
            for flow runs; defaults to infinite
        - agent_address (str, optional):  Address to serve internal API at. Currently this is
            just health checks for use by an orchestration layer. Leave blank for no API server
            (default).
        - no_cloud_logs (bool, optional): Disable logging to a Prefect backend for this agent
            and all deployed flow runs
        - volume_mounts (list, optional): A list of volumeMounts to mount when a job is
            run. The volumeMounts in the list should be specified as dicts
            i.e `[{"name": "my-vol", "mountPath": "/mnt/my-mount"}]`
        - volumes (list, optional): A list of volumes to make available to be mounted when a
            job is run. The volumes in the list should be specified as nested dicts.
            i.e `[{"name": "my-vol", "csi": {"driver": "secrets-store.csi.k8s.io"}}]`
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
        volume_mounts: List[dict] = None,
        volumes: List[dict] = None,
    ) -> None:
        super().__init__(
            name=name,
            labels=labels,
            env_vars=env_vars,
            max_polls=max_polls,
            agent_address=agent_address,
            no_cloud_logs=no_cloud_logs,
        )

        self.namespace = namespace or os.getenv("NAMESPACE", "default")
        self.volume_mounts = volume_mounts
        self.volumes = volumes

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
        self.core_client = client.CoreV1Api()
        self.k8s_client = client

        self.logger.debug(f"Namespace: {self.namespace}")

    def manage_jobs(self) -> None:
        """
        This function checks if jobs are `Failed` or `Succeeded` and if they are then the jobs are
        deleted from the namespace. If one of the job's pods happen to run into image pulling errors
        then the flow run is failed and the job is still deleted.
        """
        self.logger.debug(
            "Retrieving information of jobs that are currently in the cluster..."
        )

        more = True
        _continue = ""
        while more:
            try:
                jobs = self.batch_client.list_namespaced_job(
                    namespace=self.namespace,
                    label_selector="prefect.io/identifier",
                    limit=20,
                    _continue=_continue,
                )
                _continue = jobs.metadata._continue
                more = bool(_continue)

                for job in jobs.items:
                    delete_job = job.status.failed or job.status.succeeded
                    job_name = job.metadata.name
                    flow_run_id = job.metadata.labels.get("prefect.io/flow_run_id")

                    if not delete_job:
                        pods = self.core_client.list_namespaced_pod(
                            namespace=self.namespace,
                            label_selector="prefect.io/identifier={}".format(
                                job.metadata.labels.get("prefect.io/identifier")
                            ),
                        )

                        for pod in pods.items:
                            if pod.status.container_statuses:
                                for container_status in pod.status.container_statuses:
                                    waiting = container_status.state.waiting
                                    if waiting and (
                                        waiting.reason == "ErrImagePull"
                                        or waiting.reason == "ImagePullBackOff"
                                    ):
                                        self.logger.debug(
                                            f"Failing flow run {flow_run_id} due to pod {waiting.reason}"
                                        )
                                        self.client.set_flow_run_state(
                                            flow_run_id=flow_run_id,
                                            state=Failed(
                                                message="Kubernetes Error: {}".format(
                                                    container_status.state.waiting.message
                                                )
                                            ),
                                        )

                                        delete_job = True
                                        break

                    if delete_job:
                        self.logger.debug(f"Deleting job {job_name}")
                        try:
                            self.batch_client.delete_namespaced_job(
                                name=job_name,
                                namespace=self.namespace,
                                body=self.k8s_client.V1DeleteOptions(
                                    propagation_policy="Foreground"
                                ),
                            )
                        except self.k8s_client.rest.ApiException as exc:
                            if exc.status != 404:
                                self.logger.error(
                                    f"{exc.status} error attempting to delete job {job_name}"
                                )
            except self.k8s_client.rest.ApiException as exc:
                if exc.status == 410:
                    self.logger.debug("Refreshing job listing token...")
                    _continue = ""
                    continue
                else:
                    self.logger.debug(exc)

    def heartbeat(self) -> None:
        """
        Check status of jobs created by this agent, delete completed jobs and failed containers.
        """
        self.manage_jobs()
        super().heartbeat()

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy flow runs on to a k8s cluster as jobs

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment
        """
        self.logger.info("Deploying flow run {}".format(flow_run.id))  # type: ignore

        image = get_flow_image(flow_run=flow_run)

        identifier = str(uuid.uuid4())[:8]
        job_spec = self.replace_job_spec_yaml(
            flow_run=flow_run, image=image, identifier=identifier
        )

        self.logger.debug(
            "Creating namespaced job {}".format(job_spec["metadata"]["name"])
        )
        job = self.batch_client.create_namespaced_job(
            namespace=self.namespace, body=job_spec
        )

        self.logger.debug("Job {} created".format(job.metadata.name))

        return "Job {}".format(job.metadata.name)

    def replace_job_spec_yaml(
        self, flow_run: GraphQLResult, image: str, identifier: str
    ) -> dict:
        """
        Populate a k8s job spec. This spec defines a k8s job that handles
        executing a flow. This method runs each time the agent receives
        a flow to run.

        That job spec can optionally be customized by setting the
        following environment variables on the agent.

        - `NAMESPACE`: the k8s namespace the job will run in, defaults to `"default"`
        - `JOB_MEM_REQUEST`: memory requested, for example, `256Mi` for 256 MB. If this
                environment variable is not set, the cluster's defaults will be used.
        - `JOB_MEM_LIMIT`: memory limit, for example, `512Mi` For 512 MB. If this
                environment variable is not set, the cluster's defaults will be used.
        - `JOB_CPU_REQUEST`: CPU requested, defaults to `"100m"`
        - `JOB_CPU_LIMIT`: CPU limit, defaults to `"100m"`
        - `IMAGE_PULL_POLICY`: policy for pulling images. Defaults to `"IfNotPresent"`.
        - `IMAGE_PULL_SECRETS`: name of an existing k8s secret that can be used to pull
                images. This is necessary if your flow uses an image that is in a non-public
                container registry, such as Amazon ECR.
        - `SERVICE_ACCOUNT_NAME`: name of a service account to run the job as.
                By default, none is specified.
        - `YAML_TEMPLATE`: a path to where the YAML template should be loaded from. defaults
                to the embedded `job_spec.yaml`.

        Args:
            - flow_run (GraphQLResult): A flow run object
            - image (str): The full name of an image to use for the job
            - identifier (str): A unique identifier to identify this job

        Returns:
            - dict: a dictionary representation of a k8s job for flow execution
        """
        yaml_path = os.getenv(
            "YAML_TEMPLATE", path.join(path.dirname(__file__), "job_spec.yaml")
        )
        with open(yaml_path, "r") as job_file:
            job = yaml.safe_load(job_file)

        job_name = "prefect-job-{}".format(identifier)

        # Populate job metadata for identification
        k8s_labels = {
            "prefect.io/identifier": identifier,
            "prefect.io/flow_run_id": flow_run.id,  # type: ignore
            "prefect.io/flow_id": flow_run.flow.id,  # type: ignore
        }
        job["metadata"]["name"] = job_name
        job["metadata"]["labels"].update(**k8s_labels)
        job["spec"]["template"]["metadata"]["labels"].update(**k8s_labels)

        # Use provided image for job
        job["spec"]["template"]["spec"]["containers"][0]["image"] = image

        self.logger.debug("Using image {} for job".format(image))

        # Datermine flow run command
        job["spec"]["template"]["spec"]["containers"][0]["args"] = [
            get_flow_run_command(flow_run)
        ]

        # Populate environment variables for flow run execution
        env = job["spec"]["template"]["spec"]["containers"][0]["env"]

        env[0]["value"] = config.cloud.api or "https://api.prefect.io"
        env[1]["value"] = config.cloud.agent.auth_token
        env[2]["value"] = flow_run.id  # type: ignore
        env[3]["value"] = flow_run.flow.id  # type: ignore
        env[4]["value"] = os.getenv("NAMESPACE", "default")
        env[5]["value"] = str(self.labels)
        env[6]["value"] = str(self.log_to_cloud).lower()
        env[7]["value"] = config.logging.level

        # append all user provided values
        for key, value in self.env_vars.items():
            env.append(dict(name=key, value=value))

        # Use image pull secrets if provided
        image_pull_secrets = os.getenv("IMAGE_PULL_SECRETS")
        if image_pull_secrets:
            job["spec"]["template"]["spec"]["imagePullSecrets"][0][
                "name"
            ] = image_pull_secrets
        else:
            del job["spec"]["template"]["spec"]["imagePullSecrets"]

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
        if self.volume_mounts:
            job["spec"]["template"]["spec"]["containers"][0][
                "volumeMounts"
            ] = self.volume_mounts
        else:
            del job["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]
        if self.volumes:
            job["spec"]["template"]["spec"]["volumes"] = self.volumes
        else:
            del job["spec"]["template"]["spec"]["volumes"]
        if os.getenv("IMAGE_PULL_POLICY"):
            job["spec"]["template"]["spec"]["containers"][0][
                "imagePullPolicy"
            ] = os.getenv("IMAGE_PULL_POLICY")
        if os.getenv("SERVICE_ACCOUNT_NAME"):
            job["spec"]["template"]["spec"]["serviceAccountName"] = os.getenv(
                "SERVICE_ACCOUNT_NAME"
            )

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
        image_pull_policy: str = None,
        service_account_name: str = None,
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
            - image_pull_policy (str, optional): imagePullPolicy to use for Prefect init job.
                Job defaults to `IfNotPresent`.
            - service_account_name (str, optional): Name of a service account to use for
                Prefect init job. Job defaults to using `default` service account.
            - labels (List[str], optional): a list of labels, which are arbitrary string
                identifiers used by Prefect Agents when polling for work
            - env_vars (dict, optional): additional environment variables to attach to all
                jobs created by this agent and to set in the agent's own environment
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
        image_pull_policy = image_pull_policy or ""
        service_account_name = service_account_name or ""
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
        agent_env[11]["value"] = backend

        # Populate job resource env vars
        agent_env[5]["value"] = mem_request
        agent_env[6]["value"] = mem_limit
        agent_env[7]["value"] = cpu_request
        agent_env[8]["value"] = cpu_limit
        agent_env[9]["value"] = image_pull_policy
        agent_env[10]["value"] = service_account_name

        if env_vars:
            agent_env.append(
                {
                    "name": "PREFECT__CLOUD__AGENT__ENV_VARS",
                    "value": json.dumps(env_vars),
                }
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

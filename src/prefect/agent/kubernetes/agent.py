from collections import defaultdict
from datetime import datetime
import os
import pytz
import time
import uuid
from typing import Optional, Iterable, List, Any

import json
import pendulum
import yaml

try:
    import kubernetes
except ImportError:
    pass

import prefect
from prefect import config
from prefect.agent import Agent
from prefect.engine.state import Failed
from prefect.run_configs import KubernetesRun
from prefect.utilities.agent import get_flow_image, get_flow_run_command
from prefect.exceptions import ClientError, ObjectNotFoundError
from prefect.utilities.filesystems import read_bytes_from_path
from prefect.utilities.graphql import GraphQLResult


DEFAULT_JOB_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "job_template.yaml")


def _get_or_create(d: dict, key: str, val: Any = None) -> Any:
    """Get a (possibly nested) field from a dict, creating intermediate values
    if needed."""
    if val is None:
        val = {}
    path = key.split(".")
    for k in path[:-1]:
        d = d.setdefault(k, {})
    return d.setdefault(path[-1], val)


class KubernetesAgent(Agent):
    """
    Agent which deploys flow runs as Kubernetes jobs. Currently this is required to either
    run on a k8s cluster or on a local machine where the kube_config is pointing at the
    desired cluster. Information on using the Kubernetes Agent can be found at
    https://docs.prefect.io/orchestration/agents/kubernetes.html

    Args:
        - agent_config_id (str, optional): An optional agent configuration ID that can be used to set
            configuration based on an agent from a backend API. If set all configuration values will be
            pulled from backend agent configuration.
        - namespace (str, optional): A Kubernetes namespace to create jobs in. Defaults
            to the environment variable `NAMESPACE` or `default`.
        - service_account_name (str, optional): A kubernetes service account name to use by
            default for created jobs. May be overridden per-flow by specifying
            on a flow's `KubernetesRun` run config.
        - image_pull_secrets (list, optional): A list of image pull secrets to use by default
            for created jobs. May be overridden per-flow by specifying on a flow's
            `KubernetesRun` run config.
        - job_template_path (str, optional): A path to a job template file to use instead
            of the default.
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
        - delete_finished_jobs (bool, optional): A boolean to toggle if finished Prefect jobs
            in the agent's namespace should be deleted. Defaults to the environment variable
            `DELETE_FINISHED_JOBS` or `True`.
    """

    def __init__(
        self,
        agent_config_id: str = None,
        namespace: str = None,
        service_account_name: str = None,
        image_pull_secrets: Iterable[str] = None,
        job_template_path: str = None,
        name: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        max_polls: int = None,
        agent_address: str = None,
        no_cloud_logs: bool = None,
        volume_mounts: List[dict] = None,
        volumes: List[dict] = None,
        delete_finished_jobs: bool = True,
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

        self.namespace = namespace or os.getenv("NAMESPACE", "default")
        self.service_account_name = service_account_name or os.getenv(
            "SERVICE_ACCOUNT_NAME"
        )
        if not image_pull_secrets:
            image_pull_secrets_env = os.getenv("IMAGE_PULL_SECRETS")
            if image_pull_secrets_env:
                image_pull_secrets = [
                    s.strip() for s in image_pull_secrets_env.split(",")
                ]
            else:
                image_pull_secrets = None
        self.image_pull_secrets = image_pull_secrets
        self.job_template_path = job_template_path or DEFAULT_JOB_TEMPLATE_PATH
        self.volume_mounts = volume_mounts
        self.volumes = volumes
        self.delete_finished_jobs = delete_finished_jobs and (
            os.getenv("DELETE_FINISHED_JOBS", "True") == "True"
        )

        from prefect.utilities.kubernetes import get_kubernetes_client

        # Explicitly do not attempt to load the client from a secret
        self.batch_client = get_kubernetes_client("job", kubernetes_api_key_secret=None)
        self.core_client = get_kubernetes_client(
            "service", kubernetes_api_key_secret=None
        )

        min_datetime = datetime.min.replace(tzinfo=pytz.UTC)
        self.job_pod_event_timestamps = defaultdict(  # type: ignore
            lambda: defaultdict(lambda: min_datetime)
        )

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

                    if not flow_run_id:
                        # Do not attempt to process a job without a flow run id; we need
                        # the id to manage the flow run state
                        self.logger.warning(
                            f"Cannot manage job {job_name!r}, it is missing a "
                            "'prefect.io/flow_run_id' label."
                        )
                        continue

                    try:
                        # Do not attempt to process a job with an invalid flow run id
                        flow_run_state = self.client.get_flow_run_state(flow_run_id)
                    except ObjectNotFoundError:
                        self.logger.warning(
                            f"Job {job.metadata.name!r} is for flow run {flow_run_id!r} "
                            "which does not exist. It will be ignored."
                        )
                        continue

                    # Check for pods that are stuck with image pull errors
                    if not delete_job:
                        pods = self.core_client.list_namespaced_pod(
                            namespace=self.namespace,
                            label_selector="prefect.io/identifier={}".format(
                                job.metadata.labels.get("prefect.io/identifier")
                            ),
                        )

                        for pod in pods.items:
                            pod_name = pod.metadata.name
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
                                        try:
                                            self.client.set_flow_run_state(
                                                flow_run_id=flow_run_id,
                                                state=Failed(
                                                    message="Kubernetes Error: {}".format(
                                                        container_status.state.waiting.message
                                                    )
                                                ),
                                            )
                                        except ClientError as exc:
                                            self.logger.error(
                                                "Error attempting to set flow run state for "
                                                f"{flow_run_id}: "
                                                f"{exc}"
                                            )

                                        delete_job = True
                                        break

                            # Report recent events for pending pods to flow run logs
                            if pod.status.phase == "Pending":
                                pod_events = self.core_client.list_namespaced_event(
                                    namespace=self.namespace,
                                    field_selector="involvedObject.name={}".format(
                                        pod_name
                                    ),
                                    timeout_seconds=30,
                                )

                                for event in sorted(
                                    pod_events.items,
                                    key=lambda e: (
                                        # Some events are missing timestamp attrs and
                                        # `None` is not sortable vs datetimes so we
                                        # default to 'now'
                                        getattr(e, "last_timestamp", None)
                                        or pendulum.now()
                                    ),
                                ):

                                    # Skip events without timestamps
                                    if not getattr(event, "last_timestamp", None):
                                        self.logger.debug(
                                            f"Encountered K8s event on pod {pod_name!r}"
                                            f" with no timestamp: {event!r}"
                                        )
                                        continue

                                    # Skip old events
                                    if (
                                        event.last_timestamp
                                        < self.job_pod_event_timestamps[job_name][
                                            pod_name
                                        ]
                                    ):
                                        continue

                                    self.job_pod_event_timestamps[job_name][
                                        pod_name
                                    ] = event.last_timestamp

                                    log_msg = (
                                        f"Event: {event.reason!r} on pod {pod_name!r}\n"
                                        f"\tMessage: {event.message}"
                                    )

                                    # Send pod failure information to flow run logs
                                    self.client.write_run_logs(
                                        [
                                            dict(
                                                flow_run_id=flow_run_id,
                                                name="k8s-infra",
                                                message=log_msg,
                                                level="DEBUG",
                                                timestamp=event.last_timestamp.isoformat(),
                                            )
                                        ]
                                    )

                    # Report failed pods
                    if job.status.failed:
                        pods = self.core_client.list_namespaced_pod(
                            namespace=self.namespace,
                            label_selector="prefect.io/identifier={}".format(
                                job.metadata.labels.get("prefect.io/identifier")
                            ),
                        )

                        failed_pods = []
                        for pod in pods.items:
                            if pod.status.phase != "Failed":
                                continue

                            # Format pod failure error message
                            failed_pods.append(pod.metadata.name)
                            pod_status_logs = [f"Pod {pod.metadata.name} failed."]
                            if not pod.status.container_statuses:
                                pod_status_logs.append(
                                    "\tNo container statuses found for pod"
                                )
                            else:
                                for status in pod.status.container_statuses:
                                    state = (
                                        "running"
                                        if status.state.running
                                        else "waiting"
                                        if status.state.waiting
                                        else "terminated"
                                        if status.state.terminated
                                        else "Not Found"
                                    )
                                    pod_status_logs.append(
                                        f"\tContainer '{status.name}' state: {state}"
                                    )

                                    if status.state.terminated:
                                        pod_status_logs.append(
                                            f"\t\tExit Code:: {status.state.terminated.exit_code}"
                                        )
                                        if status.state.terminated.message:
                                            pod_status_logs.append(
                                                f"\t\tMessage: {status.state.terminated.message}"
                                            )
                                        if status.state.terminated.reason:
                                            pod_status_logs.append(
                                                f"\t\tReason: {status.state.terminated.reason}"
                                            )
                                        if status.state.terminated.signal:
                                            pod_status_logs.append(
                                                f"\t\tSignal: {status.state.terminated.signal}"
                                            )

                            # Send pod failure information to flow run logs
                            self.client.write_run_logs(
                                [
                                    dict(
                                        flow_run_id=flow_run_id,
                                        name="k8s-infra",
                                        message="\n".join(pod_status_logs),
                                        level="ERROR",
                                    )
                                ]
                            )

                        # If there are failed pods and the run is not finished, fail the run
                        if failed_pods and not flow_run_state.is_finished():
                            self.logger.debug(
                                f"Failing flow run {flow_run_id} due to the failed pods {failed_pods}"
                            )
                            try:
                                self.client.set_flow_run_state(
                                    flow_run_id=flow_run_id,
                                    state=Failed(
                                        message="Kubernetes Error: pods {} failed for this job".format(
                                            failed_pods
                                        )
                                    ),
                                )
                            except ClientError as exc:
                                self.logger.error(
                                    f"Error attempting to set flow run state for {flow_run_id}: "
                                    f"{exc}"
                                )

                    # Delete job if it is successful or failed
                    if delete_job and self.delete_finished_jobs:
                        self.logger.debug(f"Deleting job {job_name}")
                        try:
                            self.job_pod_event_timestamps.pop(job_name, None)
                            self.batch_client.delete_namespaced_job(
                                name=job_name,
                                namespace=self.namespace,
                                body=kubernetes.client.V1DeleteOptions(
                                    propagation_policy="Foreground"
                                ),
                            )
                        except kubernetes.client.rest.ApiException as exc:
                            if exc.status != 404:
                                self.logger.error(
                                    f"{exc.status} error attempting to delete job {job_name}"
                                )
            except kubernetes.client.rest.ApiException as exc:
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
        try:
            self.manage_jobs()
        except Exception:
            self.logger.error("Error while managing existing k8s jobs", exc_info=True)
        super().heartbeat()

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy flow runs on to a k8s cluster as jobs

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment
        """
        import urllib3.exceptions

        job_spec = self.generate_job_spec(flow_run=flow_run)
        job_name = job_spec["metadata"]["name"]

        self.logger.debug("Creating namespaced job {}".format(job_name))
        attempts = 3
        while True:
            try:
                self.batch_client.create_namespaced_job(
                    namespace=self.namespace, body=job_spec
                )
                break
            except kubernetes.client.rest.ApiException as exc:
                if exc.status == 409:
                    # object already exists, previous submission was successful
                    # even though it errored
                    break
                raise
            except urllib3.exceptions.HTTPError:
                attempts -= 1
                if attempts == 0:
                    raise
                self.logger.warning(
                    "Error submitting job %s, retrying...", job_name, exc_info=True
                )
                time.sleep(1)

        self.logger.debug("Job {} created".format(job_name))

        return "Job {}".format(job_name)

    def generate_job_spec(self, flow_run: GraphQLResult) -> dict:
        """Generate a k8s job spec for a flow run

        Args:
            - flow_run (GraphQLResult): A flow run object

        Returns:
            - dict: a dictionary representation of a k8s job for flow execution
        """
        run_config = self._get_run_config(flow_run, KubernetesRun)
        assert run_config is None or isinstance(run_config, KubernetesRun)  # mypy

        if run_config.job_template:
            job = run_config.job_template
        else:
            job_template_path = run_config.job_template_path or self.job_template_path
            self.logger.debug("Loading job template from %r", job_template_path)
            template_bytes = read_bytes_from_path(job_template_path)
            job = yaml.safe_load(template_bytes)

        identifier = uuid.uuid4().hex[:8]

        job_name = f"prefect-job-{identifier}"

        # Populate job metadata for identification
        k8s_labels = {
            "prefect.io/identifier": identifier,
            "prefect.io/flow_run_id": flow_run.id,  # type: ignore
            "prefect.io/flow_id": flow_run.flow.id,  # type: ignore
        }
        _get_or_create(job, "metadata.labels")
        _get_or_create(job, "spec.template.metadata.labels")
        job["metadata"]["name"] = job_name
        job["metadata"]["labels"].update(**k8s_labels)
        job["spec"]["template"]["metadata"]["labels"].update(**k8s_labels)
        pod_spec = job["spec"]["template"]["spec"]

        # Configure `service_account_name` if specified
        if run_config.service_account_name is not None:
            # On run-config, always override
            service_account_name = (
                run_config.service_account_name
            )  # type: Optional[str]
        elif "serviceAccountName" in pod_spec and (
            run_config.job_template or run_config.job_template_path
        ):
            # On run-config job-template, no override
            service_account_name = None
        else:
            # Use agent value, if provided
            service_account_name = self.service_account_name
        if service_account_name is not None:
            pod_spec["serviceAccountName"] = service_account_name

        # Configure `image_pull_secrets` if specified
        if run_config.image_pull_secrets:
            # On run-config, always override
            image_pull_secrets = (
                run_config.image_pull_secrets
            )  # type: Optional[Iterable[str]]
        elif "imagePullSecrets" in pod_spec and (
            run_config.job_template or run_config.job_template_path
        ):
            # On run-config job template, no override
            image_pull_secrets = None
        else:
            # Use agent, if provided
            image_pull_secrets = self.image_pull_secrets
        if image_pull_secrets is not None:
            pod_spec["imagePullSecrets"] = [{"name": s} for s in image_pull_secrets]

        # Default restartPolicy to Never
        _get_or_create(job, "spec.template.spec.restartPolicy", "Never")

        # Get the first container, which is used for the prefect job
        containers = _get_or_create(job, "spec.template.spec.containers", [])
        if not containers:
            containers.append({})
        container = containers[0]

        # Set container image
        container["image"] = image = get_flow_image(
            flow_run, default=container.get("image")
        )

        # set the the kubernetes imagePullPolicy, if image_pull_policy was specified
        if run_config.image_pull_policy is not None:
            container["imagePullPolicy"] = run_config.image_pull_policy

        # Set flow run command
        container["args"] = get_flow_run_command(flow_run).split()

        # Populate environment variables from the following sources,
        # with precedence:
        # - Values required for flow execution, hardcoded below
        # - Values set on the KubernetesRun object
        # - Values set using the `--env` CLI flag on the agent
        # - Values in the job template
        env = {"PREFECT__LOGGING__LEVEL": config.logging.level}
        env.update(self.env_vars)
        if run_config.env:
            env.update(run_config.env)
        env.update(
            {
                "PREFECT__BACKEND": config.backend,
                "PREFECT__CLOUD__AGENT__LABELS": str(self.labels),
                "PREFECT__CLOUD__API": config.cloud.api,
                "PREFECT__CLOUD__API_KEY": self.flow_run_api_key or "",
                "PREFECT__CLOUD__TENANT_ID": (
                    # A tenant id is only required when authenticating
                    self.client.tenant_id
                    if self.flow_run_api_key
                    else ""
                ),
                "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
                "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": str(self.log_to_cloud).lower(),
                "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,
                "PREFECT__CONTEXT__FLOW_ID": flow_run.flow.id,
                "PREFECT__CONTEXT__IMAGE": image,
                "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
                "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
                # Backwards compatibility variable for containers on Prefect <0.15.0
                "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.log_to_cloud).lower(),
                # Backwards compatibility variable for containers on Prefect <1.0.0
                "PREFECT__CLOUD__AUTH_TOKEN": self.flow_run_api_key or "",
            }
        )
        container_env = [{"name": k, "value": v} for k, v in env.items()]
        for entry in container.get("env", []):
            if entry["name"] not in env:
                container_env.append(entry)
        container["env"] = container_env

        # Set resource requirements if provided
        _get_or_create(container, "resources.requests")
        _get_or_create(container, "resources.limits")
        resources = container["resources"]
        if run_config.memory_request:
            resources["requests"]["memory"] = run_config.memory_request
        if run_config.memory_limit:
            resources["limits"]["memory"] = run_config.memory_limit
        if run_config.cpu_request:
            resources["requests"]["cpu"] = run_config.cpu_request
        if run_config.cpu_limit:
            resources["limits"]["cpu"] = run_config.cpu_limit

        return job

    @staticmethod
    def generate_deployment_yaml(
        api: str = None,
        namespace: str = None,
        image_pull_secrets: str = None,
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
        key: str = None,
        tenant_id: str = None,
        agent_config_id: str = None,
    ) -> str:
        """
        Generate and output an installable YAML spec for the agent.

        Args:
            - api (str, optional): A URL pointing to the Prefect API. Defaults to
                `https://api.prefect.io`
            - namespace (str, optional): The namespace to create Prefect jobs in. Defaults
                to `default`
            - image_pull_secrets (str, optional): The name of an image pull secret to use
                for Prefect jobs
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
            - key (str, optional): An API key for the agent to use for authentication
                with Prefect Cloud
            - tenant_id (str, optional): A tenant ID for the agent to connect to. If not
                set, the default tenant associated with the API key will be used.
            - agent_config_id (str, optional): An agent config id to link to for health
                check automations

        Returns:
            - str: A string representation of the generated YAML
        """

        # Use defaults if not provided
        key = key or ""
        tenant_id = tenant_id or ""
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
            "latest" if len(version) > 1 or latest else (version[0] + "-python3.7")
        )

        with open(
            os.path.join(os.path.dirname(__file__), "deployment.yaml"), "r"
        ) as deployment_file:
            deployment = yaml.safe_load(deployment_file)

        cmd_args = deployment["spec"]["template"]["spec"]["containers"][0]["args"]
        if agent_config_id:
            cmd_args[0] += f" --agent-config-id {agent_config_id}"

        agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

        # Populate env vars
        agent_env[0]["value"] = key  # Pass API keys as auth tokens for backwards compat
        agent_env[1]["value"] = api
        agent_env[2]["value"] = namespace
        agent_env[3]["value"] = image_pull_secrets or ""
        agent_env[4]["value"] = str(labels)
        agent_env[11]["value"] = backend
        agent_env[13]["value"] = key
        agent_env[14]["value"] = tenant_id

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
            with open(
                os.path.join(os.path.dirname(__file__), "rbac.yaml"), "r"
            ) as rbac_file:
                rbac_generator = yaml.safe_load_all(rbac_file)

                for document in rbac_generator:
                    document["metadata"]["namespace"] = namespace
                    rbac_yaml.append(document)

        output_yaml = [deployment]
        output_yaml.extend(rbac_yaml)
        return yaml.safe_dump_all(output_yaml, explicit_start=True)


if __name__ == "__main__":
    KubernetesAgent().start()

import os
import uuid
from typing import Iterable

import yaml

from prefect import config
from prefect.agent import Agent
from prefect.engine.state import Failed
from prefect.utilities.agent import get_flow_run_command
from prefect.utilities.graphql import GraphQLResult
from prefect.serialization.environment import EnvironmentSchema

DEFAULT_JOB_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "job_template.yaml")


def _get_or_create(d, key, val=None):
    if val is None:
        val = {}
    path = key.split(".")
    for k in path[:-1]:
        d = d.setdefault(k, {})
    return d.setdefault(path[-1], val)


class KubernetesAgent(Agent):
    """
    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
        - max_polls (int, optional): maximum number of times the agent will poll Prefect Cloud
            for flow runs; defaults to infinite
        - agent_address (str, optional):  Address to serve internal API at. Currently this is
            just health checks for use by an orchestration layer. Leave blank for no API server
            (default).
        - namespace (str, optional): A Kubernetes namespace to create jobs in.
    """

    def __init__(
        self,
        name: str = None,
        labels: Iterable[str] = None,
        max_polls: int = None,
        agent_address: str = None,
        env_vars: dict = None,
        no_cloud_logs: bool = False,
        namespace: str = None,
        job_template_path: str = None,
    ) -> None:
        super().__init__(
            name=name,
            labels=labels,
            max_polls=max_polls,
            agent_address=agent_address,
            no_cloud_logs=no_cloud_logs,
            env_vars=env_vars,
        )
        self.namespace = namespace or "default"
        self.job_template_path = job_template_path or DEFAULT_JOB_TEMPLATE_PATH

        from kubernetes import client, config

        try:
            self.logger.debug("Loading incluster configuration...")
            config.load_incluster_config()
        except config.config_exception.ConfigException as exc:
            self.logger.debug("Failed to load incluster configuration: {}", exc)
            self.logger.debug("Loading out of cluster configuration...")
            config.load_kube_config()

        self.batch_client = client.BatchV1Api()
        self.core_client = client.CoreV1Api()
        self.k8s_client = client

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

        job_spec = self.generate_job_spec(flow_run)

        self.logger.debug("Creating job %r ...", job_spec["metadata"]["name"])
        job = self.batch_client.create_namespaced_job(
            namespace=self.namespace, body=job_spec
        )
        self.logger.debug("Job %r created", job.metadata.name)

        return "Job {}".format(job.metadata.name)

    def load_job_template(self, path):
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def generate_job_spec(self, flow_run: GraphQLResult) -> dict:
        environment = EnvironmentSchema().load(flow_run.flow.environment).metadata

        if environment.job_template:
            job = environment.job_template
        else:
            job = self.load_job_template(
                environment.job_template_path or self.job_template_path
            )

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

        # Get the first container, which is used for the prefect job
        containers = _get_or_create(job, "spec.template.spec.containers", [])
        if not containers:
            containers.append({})
        container = containers[0]

        # Set image if specified
        if environment.image:
            container["image"] = environment.image

        # Set flow run command
        container["args"] = [get_flow_run_command(flow_run)]

        # Populate environment variables from the following sources:
        # - Values set using the `--env` CLI flag on the agent
        # - Values set on the job configuration
        # - Hardcoded values below, provided they're not already set
        env = self.env_vars.copy()
        if environment.env:
            env.update(environment.env)
        env.update(
            {
                "PREFECT__CLOUD__API": config.cloud.api,
                "PREFECT__CLOUD__AUTH_TOKEN": config.cloud.agent.auth_token,
                "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
                "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,
                "PREFECT__CONTEXT__FLOW_ID": flow_run.flow.id,
                "PREFECT__LOGGING__LEVEL": config.logging.level,
                "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.log_to_cloud).lower(),
                "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
                "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
            }
        )
        container_env = _get_or_create(container, "env", [])
        existing = {e["name"] for e in container_env}
        for k, v in env.items():
            if k not in existing:
                container_env.append({"name": k, "value": v})

        # Set resource requirements if provided
        _get_or_create(container, "resources.requests")
        _get_or_create(container, "resources.limits")
        resources = container["resources"]
        if environment.memory_request:
            resources["requests"]["memory"] = environment.memory_request
        if environment.memory_limit:
            resources["limits"]["memory"] = environment.memory_limit
        if environment.cpu_request:
            resources["requests"]["cpu"] = environment.cpu_request
        if environment.cpu_limit:
            resources["limits"]["cpu"] = environment.cpu_limit

        return job


if __name__ == "__main__":
    KubernetesAgent().start()

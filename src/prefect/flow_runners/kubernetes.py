import enum
from types import ModuleType
from typing import TYPE_CHECKING, Dict, List, Optional

from anyio.abc import TaskStatus
from pydantic import Field, PrivateAttr
from slugify import slugify
from typing_extensions import Literal

from prefect.orion.schemas.core import FlowRun
from prefect.settings import PREFECT_API_URL
from prefect.utilities.asyncio import run_sync_in_worker_thread

if TYPE_CHECKING:
    import kubernetes
    from kubernetes.client import BatchV1Api, Configuration, CoreV1Api, V1Job, V1Pod
else:
    kubernetes = None

from .base import (
    UniversalFlowRunner,
    base_flow_run_environment,
    get_prefect_image_name,
    register_flow_runner,
)


class KubernetesImagePullPolicy(enum.Enum):
    IF_NOT_PRESENT = "IfNotPresent"
    ALWAYS = "Always"
    NEVER = "Never"


class KubernetesRestartPolicy(enum.Enum):
    ON_FAILURE = "OnFailure"
    NEVER = "Never"


@register_flow_runner
class KubernetesFlowRunner(UniversalFlowRunner):
    """
    Executes flow runs in a Kubernetes job.

    Requires a Kubernetes cluster to be connectable.

    Attributes:
        image: An optional string specifying the tag of a Docker image to use for the job.
        namespace: An optional string signifying the Kubernetes namespace to use.
        service_account_name: An optional string specifying which Kubernetes service account to use.
        labels: An optional dictionary of labels to add to the job.
        image_pull_policy: The Kubernetes image pull policy to use for job containers.
        restart_policy: The Kubernetes restart policy to use for jobs.
        stream_output: If set, stream output from the container to local standard output.
    """

    typename: Literal["kubernetes"] = "kubernetes"

    image: str = Field(default_factory=get_prefect_image_name)
    namespace: str = "default"
    service_account_name: str = None
    labels: Dict[str, str] = None
    image_pull_policy: KubernetesImagePullPolicy = None
    restart_policy: KubernetesRestartPolicy = KubernetesRestartPolicy.NEVER
    stream_output: bool = True

    _client: "CoreV1Api" = PrivateAttr(None)
    _batch_client: "BatchV1Api" = PrivateAttr(None)
    _k8s_config: "Configuration" = PrivateAttr(None)

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:
        self.logger.info("RUNNING")

        # Throw an error immediately if the flow run won't be able to contact the API
        self._assert_orion_settings_are_compatible()

        # Python won't let us use self._k8s.config.ConfigException, it seems
        from kubernetes.config import ConfigException

        # Try to load Kubernetes configuration within a cluster first. If that doesn't
        # work, try to load the configuration from the local environment, allowing
        # any further ConfigExceptions to bubble up.
        try:
            self._k8s.config.incluster_config.load_incluster_config()
        except ConfigException:
            self._k8s.config.load_kube_config()

        job_name = await run_sync_in_worker_thread(self._create_and_start_job, flow_run)

        # Mark as started
        task_status.started()

        # Monitor the job
        return await run_sync_in_worker_thread(self._watch_job, job_name)

    @property
    def batch_client(self) -> "BatchV1Api":
        if self._batch_client is None:
            self._batch_client = self._k8s.client.BatchV1Api()
        return self._batch_client

    @property
    def client(self) -> "CoreV1Api":
        if self._client is None:
            self._client = self._k8s.client.CoreV1Api(self._k8s.client.ApiClient())
        return self._client

    def _assert_orion_settings_are_compatible(self):
        """See note in DockerFlowRunner."""
        api_url = self.env.get("PREFECT_API_URL", PREFECT_API_URL.value())

        if not api_url:
            raise RuntimeError(
                "The Kubernetes flow runner cannot be used with an ephemeral server. "
                "Provide `PREFECT_API_URL` to connect to an Orion server."
            )

    def _get_job(self, job_id: str) -> Optional["V1Job"]:
        try:
            job = self.batch_client.read_namespaced_job(job_id, self.namespace)
        except self._k8s.client.ApiException:
            self.logger.error(f"Flow run job {job_id!r} was removed.", exc_info=True)
            return None
        return job

    def _get_job_pod(self, job_name: str) -> "V1Pod":
        """Get the first running pod for a job."""

        # Wait until we find a running pod for the job
        watch = self._k8s.watch.Watch()
        self.logger.info(f"Starting watch for pod to start. Job: {job_name}")
        for event in watch.stream(
            func=self.client.list_namespaced_pod,
            namespace=self.namespace,
            label_selector=f"job-name={job_name}",
            timeout_seconds=5,  # TODO: Make configurable?
        ):
            if event["object"].status.phase == "Running":
                watch.stop()
                return event["object"]
        self.logger.error(f"Pod never started. Job: {job_name}")

    def _watch_job(self, job_name: str) -> bool:
        job = self._get_job(job_name)
        if not job:
            return False

        self.logger.info(
            f"Flow run job {job.metadata.name!r} has status {job.status!r}"
        )

        pod = self._get_job_pod(job_name)
        if not pod:
            return False

        if self.stream_output:
            for log in self.client.read_namespaced_pod_log(
                pod.metadata.name, self.namespace, follow=True, _preload_content=False
            ).stream():
                print(log.decode().rstrip())

        # Wait for job to complete
        self.logger.info(f"Starting watch for job completion: {job_name}")
        watch = self._k8s.watch.Watch()
        for event in watch.stream(
            func=self.batch_client.list_namespaced_job,
            field_selector=f"metadata.name={job_name}",
            namespace=self.namespace,
            timeout_seconds=5,  # TODO: Make configurable?
        ):
            if event["object"].status.completion_time:
                watch.stop()
                break
        else:
            self.logger.error(f"Job {job_name!r} never completed.")
            return False

        pod_status = self.client.read_namespaced_pod_status(
            namespace=self.namespace, name=pod.metadata.name
        )
        return pod_status.status.container_statuses[0].state.terminated.exit_code == 0

    def _get_start_command(self, flow_run: FlowRun) -> List[str]:
        return [
            "python",
            "-m",
            "prefect.engine",
            f"{flow_run.id}",
        ]

    def _slugify_flow_run_name(self, flow_run: FlowRun):
        """
        Slugify a flow run name for use as a Kubernetes label or name.

        Keeps only alphanumeric characters and dashes, and caps the length
        of the slug at 45 chars.

        The 45 character length allows room for the k8s utility
        "generateName" to generate a unique name from the slug while
        keeping the total length of a name below 63 characters, which is
        the limit for e.g. label names that follow RFC 1123 (hostnames) and
        RFC 1035 (domain names).

        Args:
            flow_run: The flow run

        Returns:
            the slugified flow name
        """
        slug = slugify(
            flow_run.name,
            max_length=45,  # Leave enough space for generateName
            regex_pattern=r"[^a-zA-Z0-9-]+",
        )
        if not slug:
            return str(flow_run.id)
        return slug

    def _get_labels(self, flow_run: FlowRun):
        labels = self.labels.copy() if self.labels else {}
        flow_run_name_slug = self._slugify_flow_run_name(flow_run)
        labels.update(
            {
                "io.prefect.flow-run-id": str(flow_run.id),
                "io.prefect.flow-run-name": flow_run_name_slug,
                "app": "orion",
            }
        )
        return labels

    def _get_environment_variables(self):
        return {**base_flow_run_environment(), **self.env}

    def _create_and_start_job(self, flow_run: FlowRun) -> str:
        k8s_env = [
            {"name": k, "value": v}
            for k, v in self._get_environment_variables().items()
        ]

        job_settings = dict(
            metadata={
                "generateName": self._slugify_flow_run_name(flow_run),
                "namespace": self.namespace,
                "labels": self._get_labels(flow_run),
            },
            spec={
                "template": {
                    "spec": {
                        "restartPolicy": self.restart_policy.value,
                        "containers": [
                            {
                                "name": "job",
                                "image": self.image,
                                "command": self._get_start_command(flow_run),
                                "env": k8s_env,
                            }
                        ],
                    }
                },
                "backoff_limit": 4,
            },
        )

        if self.service_account_name:
            job_settings["spec"]["template"]["spec"][
                "serviceAccountName"
            ] = self.service_account_name

        if self.image_pull_policy:
            job_settings["spec"]["template"]["spec"]["containers"][0][
                "imagePullPolicy"
            ] = self.image_pull_policy.value

        self.logger.info(
            f"Flow run {flow_run.name!r} has job settings = {job_settings}"
        )
        job = self.batch_client.create_namespaced_job(self.namespace, job_settings)

        return job.metadata.name

    @property
    def _k8s(self) -> ModuleType("kubernetes"):
        """
        Delayed import of `kubernetes` allowing configuration of the flow runner without
        the extra installed and improves `prefect` import times.
        """
        global kubernetes

        if kubernetes is None:
            try:
                import kubernetes
            except ImportError as exc:
                raise RuntimeError(
                    "Using the `KubernetesFlowRunner` requires `kubernetes` to be "
                    "installed."
                ) from exc

        return kubernetes

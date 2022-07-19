import copy
import enum
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Union

import yaml
from anyio.abc import TaskStatus
from jsonpatch import JsonPatch
from pydantic import Field, PrivateAttr, validator
from slugify import slugify
from typing_extensions import Literal

from prefect.blocks.kubernetes import KubernetesClusterConfig
from prefect.flow_runners.base import (
    UniversalFlowRunner,
    base_flow_run_environment,
    get_prefect_image_name,
    register_flow_runner,
)
from prefect.orion.schemas.core import FlowRun
from prefect.settings import PREFECT_API_URL
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.importtools import lazy_import

if TYPE_CHECKING:
    import kubernetes
    import kubernetes.client
    import kubernetes.config
    import kubernetes.watch
    from kubernetes.client import BatchV1Api, CoreV1Api, V1Job, V1Pod
else:
    kubernetes = lazy_import("kubernetes")


class KubernetesImagePullPolicy(enum.Enum):
    IF_NOT_PRESENT = "IfNotPresent"
    ALWAYS = "Always"
    NEVER = "Never"


class KubernetesRestartPolicy(enum.Enum):
    ON_FAILURE = "OnFailure"
    NEVER = "Never"


KubernetesManifest = Dict[str, Any]


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
        job: The base manifest for the Kubernetes Job.
        customizations: A list of JSON 6902 patches to apply to the base Job manifest.
        job_watch_timeout_seconds: Number of seconds to watch for job creation before timing out (default 5).
        pod_watch_timeout_seconds: Number of seconds to watch for pod creation before timing out (default 5).
        stream_output: If set, stream output from the container to local standard output.
    """

    typename: Literal["kubernetes"] = "kubernetes"

    # shortcuts for the most common user-serviceable settings
    image: str = Field(default_factory=get_prefect_image_name)
    namespace: str = "default"
    service_account_name: str = None
    labels: Dict[str, str] = Field(default_factory=dict)
    image_pull_policy: Optional[KubernetesImagePullPolicy] = None

    # settings allowing full customization of the Job
    job: KubernetesManifest = Field(
        default_factory=lambda: KubernetesFlowRunner.base_job_manifest()
    )
    customizations: JsonPatch = Field(default_factory=lambda: JsonPatch([]))

    # controls the behavior of the FlowRunner
    job_watch_timeout_seconds: int = 5
    pod_watch_timeout_seconds: int = 60
    stream_output: bool = True
    cluster_config: KubernetesClusterConfig = None

    _client: "CoreV1Api" = PrivateAttr(None)
    _batch_client: "BatchV1Api" = PrivateAttr(None)
    _k8s_config: "Configuration" = PrivateAttr(None)

    class Config:
        arbitrary_types_allowed = True

        json_encoders = {JsonPatch: lambda p: p.patch}

    def dict(self, *args, **kwargs) -> Dict:
        d = super().dict(*args, **kwargs)
        d["customizations"] = self.customizations.patch
        return d

    @validator("job")
    def ensure_job_includes_all_required_components(cls, value: KubernetesManifest):
        patch = JsonPatch.from_diff(value, cls.base_job_manifest())
        missing_paths = sorted([op["path"] for op in patch if op["op"] == "add"])
        if missing_paths:
            raise ValueError(
                "Job is missing required attributes at the following paths: "
                f"{', '.join(missing_paths)}"
            )
        return value

    @validator("job")
    def ensure_job_has_compatible_values(cls, value: KubernetesManifest):
        patch = JsonPatch.from_diff(value, cls.base_job_manifest())
        incompatible = sorted(
            [
                f"{op['path']} must have value {op['value']!r}"
                for op in patch
                if op["op"] == "replace"
            ]
        )
        if incompatible:
            raise ValueError(
                "Job has incompatble values for the following attributes: "
                f"{', '.join(incompatible)}"
            )
        return value

    @validator("customizations", pre=True)
    def cast_customizations_to_a_json_patch(
        cls, value: Union[List[Dict], JsonPatch]
    ) -> JsonPatch:
        if isinstance(value, list):
            return JsonPatch(value)
        return value

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:
        # Throw an error immediately if the flow run won't be able to contact the API
        self._assert_orion_settings_are_compatible()

        # if a k8s cluster block is provided to the flow runner, use that
        if self.cluster_config:
            self.cluster_config.configure_client()
        else:
            # If no block specified, try to load Kubernetes configuration within a cluster. If that doesn't
            # work, try to load the configuration from the local environment, allowing
            # any further ConfigExceptions to bubble up.
            try:
                kubernetes.config.load_incluster_config()
            except kubernetes.config.ConfigException:
                kubernetes.config.load_kube_config()

        manifest = self.build_job(flow_run)
        job_name = await run_sync_in_worker_thread(self._create_job, flow_run, manifest)

        # Mark as started
        task_status.started()

        # Monitor the job
        return await run_sync_in_worker_thread(self._watch_job, job_name)

    @contextmanager
    def get_batch_client(self) -> Generator["BatchV1Api", None, None]:
        with kubernetes.client.ApiClient() as client:
            try:
                yield kubernetes.client.BatchV1Api(api_client=client)
            finally:
                client.rest_client.pool_manager.clear()

    @contextmanager
    def get_client(self) -> Generator["CoreV1Api", None, None]:
        with kubernetes.client.ApiClient() as client:
            try:
                yield kubernetes.client.CoreV1Api(api_client=client)
            finally:
                client.rest_client.pool_manager.clear()

    def _assert_orion_settings_are_compatible(self):
        """See note in DockerFlowRunner."""
        api_url = self.env.get("PREFECT_API_URL", PREFECT_API_URL.value())

        if not api_url:
            raise RuntimeError(
                "The Kubernetes flow runner cannot be used with an ephemeral server. "
                "Provide `PREFECT_API_URL` to connect to an Orion server."
            )

    def _get_job(self, job_id: str) -> Optional["V1Job"]:
        with self.get_batch_client() as batch_client:
            try:
                job = batch_client.read_namespaced_job(job_id, self.namespace)
            except kubernetes.ApiException:
                self.logger.error(
                    f"Flow run job {job_id!r} was removed.", exc_info=True
                )
                return None
            return job

    def _get_job_pod(self, job_name: str) -> "V1Pod":
        """Get the first running pod for a job."""

        # Wait until we find a running pod for the job
        watch = kubernetes.watch.Watch()
        self.logger.info(f"Starting watch for pod to start. Job: {job_name}")
        with self.get_client() as client:
            for event in watch.stream(
                func=client.list_namespaced_pod,
                namespace=self.namespace,
                label_selector=f"job-name={job_name}",
                timeout_seconds=self.pod_watch_timeout_seconds,
            ):
                if event["object"].status.phase == "Running":
                    watch.stop()
                    return event["object"]
        raise RuntimeError(
            f"Pod for job {job_name!r} did not start after "
            f"{self.pod_watch_timeout_seconds} seconds. "
            f"Consider increasing the value of `pod_watch_timeout_seconds`."
        )

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
            with self.get_client() as client:
                logs = client.read_namespaced_pod_log(
                    pod.metadata.name,
                    self.namespace,
                    follow=True,
                    _preload_content=False,
                )
                for log in logs.stream():
                    print(log.decode().rstrip())

        # Wait for job to complete
        self.logger.info(f"Starting watch for job completion: {job_name}")
        watch = kubernetes.watch.Watch()
        with self.get_batch_client() as batch_client:
            for event in watch.stream(
                func=batch_client.list_namespaced_job,
                field_selector=f"metadata.name={job_name}",
                namespace=self.namespace,
                timeout_seconds=self.job_watch_timeout_seconds,
            ):
                if event["object"].status.completion_time:
                    watch.stop()
                    break
            else:
                self.logger.error(f"Job {job_name!r} never completed.")
                return False

        with self.get_client() as client:
            pod_status = client.read_namespaced_pod_status(
                namespace=self.namespace, name=pod.metadata.name
            )
        return pod_status.status.container_statuses[0].state.terminated.exit_code == 0

    def _create_job(self, flow_run: FlowRun, job_manifest: KubernetesManifest) -> str:
        """Given a FlowRun and Kubernetes Job Manifest, create the Job on the configured
        Kubernetes cluster and return its name."""
        with self.get_batch_client() as batch_client:
            job = batch_client.create_namespaced_job(self.namespace, job_manifest)
        return job.metadata.name

    def build_job(self, flow_run: FlowRun) -> KubernetesManifest:
        """Builds the Kubernetes Job Manifest to execute the given FlowRun"""
        job_manifest = copy.copy(self.job)

        # First, apply Prefect's customizations to build up the job
        job_manifest = self._environment_variables().apply(job_manifest)
        job_manifest = self._job_identification(flow_run).apply(job_manifest)
        job_manifest = self._job_orchestration(flow_run).apply(job_manifest)

        # Then, apply user-provided customizations last, so that power users have
        # full control and the appopriate "steam valve" to make Jobs work well in their
        # environment
        job_manifest = self._shortcut_customizations().apply(job_manifest)
        job_manifest = self.customizations.apply(job_manifest)

        return job_manifest

    async def preview(self, flow_run: FlowRun) -> str:
        """
        Produce a textual preview of the given FlowRun.

        For the KubernetesFlowRunner, this produces a serialized YAML representation
        of the Job that would be sent to Kubernetes.

        Args:
            flow_run: The flow run

        Returns:
            A YAML string
        """
        return yaml.dump(self.build_job(flow_run))

    def _slugify_flow_run_name(self, flow_run: FlowRun) -> str:
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

    @classmethod
    def base_job_manifest(cls) -> KubernetesManifest:
        """Produces the bare minimum allowed Job manifest"""
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"labels": {}},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "prefect-job",
                                "env": [],
                            }
                        ]
                    }
                }
            },
        }

    # Note that we're using the yaml package to load both YAML and JSON files below.
    # This works because YAML is a strict superset of JSON:
    #
    #   > The YAML 1.23 specification was published in 2009. Its primary focus was
    #   > making YAML a strict superset of JSON. It also removed many of the problematic
    #   > implicit typing recommendations.
    #
    #   https://yaml.org/spec/1.2.2/#12-yaml-history

    @classmethod
    def job_from_file(cls, filename: str) -> KubernetesManifest:
        """Load a Kubernetes Job manifest from a YAML or JSON file."""
        with open(filename, "r", encoding="utf-8") as f:
            return yaml.load(f, yaml.SafeLoader)

    @classmethod
    def customize_from_file(cls, filename: str) -> JsonPatch:
        """Load an RFC 6902 JSON patch from a YAML or JSON file."""
        with open(filename, "r", encoding="utf-8") as f:
            return JsonPatch(yaml.load(f, yaml.SafeLoader))

    def _shortcut_customizations(self) -> JsonPatch:
        """Produces the JSON 6902 patch for the most commonly used customizations, like
        image and namespace, which we offer as top-level parameters (with sensible
        default values)"""
        shortcuts = [
            {
                "op": "add",
                "path": "/metadata/namespace",
                "value": self.namespace,
            },
            {
                "op": "add",
                "path": "/spec/template/spec/containers/0/image",
                "value": self.image,
            },
        ]

        shortcuts += [
            {
                "op": "add",
                "path": f"/metadata/labels/{key}",
                "value": value,
            }
            for key, value in self.labels.items()
        ]

        if self.image_pull_policy:
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/spec/template/spec/containers/0/imagePullPolicy",
                    "value": self.image_pull_policy.value,
                }
            )

        if self.service_account_name:
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/spec/template/spec/serviceAccountName",
                    "value": self.service_account_name,
                }
            )

        return JsonPatch(shortcuts)

    def _environment_variables(self) -> JsonPatch:
        """Produces the JSON 6902 patch to inject the current Prefect configuration as
        environment variables"""
        # Also consider any environment variables that the user wishes to inject
        # via the customizations patches
        variables = {**base_flow_run_environment(), **self.env}
        return JsonPatch(
            [
                {
                    "op": "add",
                    "path": "/spec/template/spec/containers/0/env/-",
                    "value": {"name": key, "value": value},
                }
                for key, value in variables.items()
            ]
        )

    def _job_identification(self, flow_run: FlowRun) -> JsonPatch:
        """Produces the JSON 6902 patch for identifying attributes and labels
        for Prefect Kubernetes Jobs"""
        return JsonPatch(
            [
                {
                    "op": "add",
                    "path": "/metadata/labels/prefect.io~1flow-run-id",
                    "value": str(flow_run.id),
                },
                {
                    "op": "add",
                    "path": "/metadata/labels/prefect.io~1flow-run-name",
                    "value": self._slugify_flow_run_name(flow_run),
                },
                {
                    "op": "add",
                    "path": "/metadata/generateName",
                    "value": self._slugify_flow_run_name(flow_run),
                },
            ]
        )

    def _job_orchestration(self, flow_run: FlowRun) -> JsonPatch:
        """Produces the JSON 6902 patch controlling how the Flow Run Job will use
        Kubernetes orchestration features"""
        return JsonPatch(
            [
                {
                    "op": "add",
                    "path": "/spec/template/spec/parallelism",
                    "value": 1,
                },
                {
                    "op": "add",
                    "path": "/spec/template/spec/completions",
                    "value": 1,
                },
                {
                    "op": "add",
                    "path": "/spec/template/spec/restartPolicy",
                    "value": "Never",
                },
                {
                    "op": "add",
                    "path": "/spec/template/spec/containers/0/command",
                    "value": [
                        "python",
                        "-m",
                        "prefect.engine",
                        f"{flow_run.id}",
                    ],
                },
            ]
        )

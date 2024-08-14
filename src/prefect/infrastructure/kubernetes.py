"""
DEPRECATION WARNING:

This module is deprecated as of March 2024 and will not be available after September 2024.
It has been replaced by the Kubernetes worker from the prefect-kubernetes package, which offers enhanced functionality and better performance.

For upgrade instructions, see https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.
"""
import copy
import enum
import math
import os
import shlex
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Tuple, Union

import anyio.abc
import yaml

from prefect._internal.compatibility.deprecated import (
    deprecated_class,
)
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.schemas.validators import (
    cast_k8s_job_customizations,
    set_default_image,
    set_default_namespace,
    validate_k8s_job_compatible_values,
    validate_k8s_job_required_components,
)

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, root_validator, validator
else:
    from pydantic import Field, root_validator, validator

from typing_extensions import Literal

from prefect.blocks.kubernetes import KubernetesClusterConfig
from prefect.exceptions import InfrastructureNotAvailable, InfrastructureNotFound
from prefect.infrastructure.base import Infrastructure, InfrastructureResult
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible
from prefect.utilities.hashing import stable_hash
from prefect.utilities.importtools import lazy_import
from prefect.utilities.pydantic import JsonPatch
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    import kubernetes
    import kubernetes.client
    import kubernetes.client.exceptions
    import kubernetes.config
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


class KubernetesJobResult(InfrastructureResult):
    """Contains information about the final state of a completed Kubernetes Job"""


@deprecated_class(
    start_date="Mar 2024",
    help="Use the Kubernetes worker from prefect-kubernetes instead."
    " Refer to the upgrade guide for more information:"
    " https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.",
)
class KubernetesJob(Infrastructure):
    """
    Runs a command as a Kubernetes Job.

    For a guided tutorial, see [How to use Kubernetes with Prefect](https://medium.com/the-prefect-blog/how-to-use-kubernetes-with-prefect-419b2e8b8cb2/).
    For more information, including examples for customizing the resulting manifest, see [`KubernetesJob` infrastructure concepts](https://docs.prefect.io/concepts/infrastructure/#kubernetesjob).

    Attributes:
        cluster_config: An optional Kubernetes cluster config to use for this job.
        command: A list of strings specifying the command to run in the container to
            start the flow run. In most cases you should not override this.
        customizations: A list of JSON 6902 patches to apply to the base Job manifest.
        env: Environment variables to set for the container.
        finished_job_ttl: The number of seconds to retain jobs after completion. If set, finished jobs will
            be cleaned up by Kubernetes after the given delay. If None (default), jobs will need to be
            manually removed.
        image: An optional string specifying the image reference of a container image
            to use for the job, for example, docker.io/prefecthq/prefect:2-latest. The
            behavior is as described in https://kubernetes.io/docs/concepts/containers/images/#image-names.
            Defaults to the Prefect image.
        image_pull_policy: The Kubernetes image pull policy to use for job containers.
        job: The base manifest for the Kubernetes Job.
        job_watch_timeout_seconds: Number of seconds to wait for the job to complete
            before marking it as crashed. Defaults to `None`, which means no timeout will be enforced.
        labels: An optional dictionary of labels to add to the job.
        name: An optional name for the job.
        namespace: An optional string signifying the Kubernetes namespace to use.
        pod_watch_timeout_seconds: Number of seconds to watch for pod creation before timing out (default 60).
        service_account_name: An optional string specifying which Kubernetes service account to use.
        stream_output: If set, stream output from the job to local standard output.
    """

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/2d0b896006ad463b49c28aaac14f31e00e32cfab-250x250.png"
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/infrastructure/#prefect.infrastructure.KubernetesJob"

    type: Literal["kubernetes-job"] = Field(
        default="kubernetes-job", description="The type of infrastructure."
    )
    # shortcuts for the most common user-serviceable settings
    image: Optional[str] = Field(
        default=None,
        description=(
            "The image reference of a container image to use for the job, for example,"
            " `docker.io/prefecthq/prefect:2-latest`.The behavior is as described in"
            " the Kubernetes documentation and uses the latest version of Prefect by"
            " default, unless an image is already present in a provided job manifest."
        ),
    )
    namespace: Optional[str] = Field(
        default=None,
        description=(
            "The Kubernetes namespace to use for this job. Defaults to 'default' "
            "unless a namespace is already present in a provided job manifest."
        ),
    )
    service_account_name: Optional[str] = Field(
        default=None, description="The Kubernetes service account to use for this job."
    )
    image_pull_policy: Optional[KubernetesImagePullPolicy] = Field(
        default=None,
        description="The Kubernetes image pull policy to use for job containers.",
    )

    # connection to a cluster
    cluster_config: Optional[KubernetesClusterConfig] = Field(
        default=None, description="The Kubernetes cluster config to use for this job."
    )

    # settings allowing full customization of the Job
    job: KubernetesManifest = Field(
        default_factory=lambda: KubernetesJob.base_job_manifest(),
        description="The base manifest for the Kubernetes Job.",
        title="Base Job Manifest",
    )
    customizations: JsonPatch = Field(
        default_factory=lambda: JsonPatch([]),
        description="A list of JSON 6902 patches to apply to the base Job manifest.",
    )

    # controls the behavior of execution
    job_watch_timeout_seconds: Optional[int] = Field(
        default=None,
        description=(
            "Number of seconds to wait for the job to complete before marking it as"
            " crashed. Defaults to `None`, which means no timeout will be enforced."
        ),
    )
    pod_watch_timeout_seconds: int = Field(
        default=60,
        description="Number of seconds to watch for pod creation before timing out.",
    )
    stream_output: bool = Field(
        default=True,
        description=(
            "If set, output will be streamed from the job to local standard output."
        ),
    )
    finished_job_ttl: Optional[int] = Field(
        default=None,
        description=(
            "The number of seconds to retain jobs after completion. If set, finished"
            " jobs will be cleaned up by Kubernetes after the given delay. If None"
            " (default), jobs will need to be manually removed."
        ),
    )

    # internal-use only right now
    _api_dns_name: Optional[str] = None  # Replaces 'localhost' in API URL

    _block_type_name = "Kubernetes Job"

    @validator("job")
    def ensure_job_includes_all_required_components(cls, value: KubernetesManifest):
        return validate_k8s_job_required_components(cls, value)

    @validator("job")
    def ensure_job_has_compatible_values(cls, value: KubernetesManifest):
        return validate_k8s_job_compatible_values(cls, value)

    @validator("customizations", pre=True)
    def cast_customizations_to_a_json_patch(
        cls, value: Union[List[Dict], JsonPatch, str]
    ) -> JsonPatch:
        return cast_k8s_job_customizations(cls, value)

    @root_validator
    def default_namespace(cls, values):
        return set_default_namespace(values)

    @root_validator
    def default_image(cls, values):
        return set_default_image(values)

    # Support serialization of the 'JsonPatch' type
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {JsonPatch: lambda p: p.patch}

    def dict(self, *args, **kwargs) -> Dict:
        d = super().dict(*args, **kwargs)
        d["customizations"] = self.customizations.patch
        return d

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
                        "parallelism": 1,
                        "completions": 1,
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "prefect-job",
                                "env": [],
                            }
                        ],
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

    @sync_compatible
    async def run(
        self,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ) -> KubernetesJobResult:
        if not self.command:
            raise ValueError("Kubernetes job cannot be run with empty command.")

        self._configure_kubernetes_library_client()
        manifest = self.build_job()
        job = await run_sync_in_worker_thread(self._create_job, manifest)

        pid = await run_sync_in_worker_thread(self._get_infrastructure_pid, job)
        # Indicate that the job has started
        if task_status is not None:
            task_status.started(pid)

        # Monitor the job until completion
        status_code = await run_sync_in_worker_thread(
            self._watch_job, job.metadata.name
        )
        return KubernetesJobResult(identifier=pid, status_code=status_code)

    async def kill(self, infrastructure_pid: str, grace_seconds: int = 30):
        self._configure_kubernetes_library_client()
        job_cluster_uid, job_namespace, job_name = self._parse_infrastructure_pid(
            infrastructure_pid
        )

        if not job_namespace == self.namespace:
            raise InfrastructureNotAvailable(
                f"Unable to kill job {job_name!r}: The job is running in namespace "
                f"{job_namespace!r} but this block is configured to use "
                f"{self.namespace!r}."
            )

        current_cluster_uid = self._get_cluster_uid()
        if job_cluster_uid != current_cluster_uid:
            raise InfrastructureNotAvailable(
                f"Unable to kill job {job_name!r}: The job is running on another "
                "cluster."
            )

        with self.get_batch_client() as batch_client:
            try:
                batch_client.delete_namespaced_job(
                    name=job_name,
                    namespace=job_namespace,
                    grace_period_seconds=grace_seconds,
                    # Foreground propagation deletes dependent objects before deleting owner objects.
                    # This ensures that the pods are cleaned up before the job is marked as deleted.
                    # See: https://kubernetes.io/docs/concepts/architecture/garbage-collection/#foreground-deletion
                    propagation_policy="Foreground",
                )
            except kubernetes.client.exceptions.ApiException as exc:
                if exc.status == 404:
                    raise InfrastructureNotFound(
                        f"Unable to kill job {job_name!r}: The job was not found."
                    ) from exc
                else:
                    raise

    def preview(self):
        return yaml.dump(self.build_job())

    def get_corresponding_worker_type(self):
        return "kubernetes"

    async def generate_work_pool_base_job_template(self):
        from prefect.workers.utilities import (
            get_default_base_job_template_for_infrastructure_type,
        )

        base_job_template = await get_default_base_job_template_for_infrastructure_type(
            self.get_corresponding_worker_type()
        )
        assert (
            base_job_template is not None
        ), "Failed to retrieve default base job template."
        for key, value in self.dict(exclude_unset=True, exclude_defaults=True).items():
            if key == "command":
                base_job_template["variables"]["properties"]["command"][
                    "default"
                ] = shlex.join(value)
            elif key in [
                "type",
                "block_type_slug",
                "_block_document_id",
                "_block_document_name",
                "_is_anonymous",
                "job",
                "customizations",
            ]:
                continue
            elif key == "image_pull_policy":
                base_job_template["variables"]["properties"]["image_pull_policy"][
                    "default"
                ] = value.value
            elif key == "cluster_config":
                base_job_template["variables"]["properties"]["cluster_config"][
                    "default"
                ] = {
                    "$ref": {
                        "block_document_id": str(self.cluster_config._block_document_id)
                    }
                }
            elif key in base_job_template["variables"]["properties"]:
                base_job_template["variables"]["properties"][key]["default"] = value
            else:
                self.logger.warning(
                    f"Variable {key!r} is not supported by Kubernetes work pools."
                    " Skipping."
                )

        custom_job_manifest = self.dict(exclude_unset=True, exclude_defaults=True).get(
            "job"
        )
        if custom_job_manifest:
            job_manifest = self.build_job()
        else:
            job_manifest = copy.deepcopy(
                base_job_template["job_configuration"]["job_manifest"]
            )
            job_manifest = self.customizations.apply(job_manifest)
        base_job_template["job_configuration"]["job_manifest"] = job_manifest

        return base_job_template

    def build_job(self) -> KubernetesManifest:
        """Builds the Kubernetes Job Manifest"""
        job_manifest = copy.copy(self.job)
        job_manifest = self._shortcut_customizations().apply(job_manifest)
        job_manifest = self.customizations.apply(job_manifest)
        return job_manifest

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

    def _get_infrastructure_pid(self, job: "V1Job") -> str:
        """
        Generates a Kubernetes infrastructure PID.

        The PID is in the format: "<cluster uid>:<namespace>:<job name>".
        """
        cluster_uid = self._get_cluster_uid()
        pid = f"{cluster_uid}:{self.namespace}:{job.metadata.name}"
        return pid

    def _parse_infrastructure_pid(
        self, infrastructure_pid: str
    ) -> Tuple[str, str, str]:
        """
        Parse a Kubernetes infrastructure PID into its component parts.

        Returns a cluster UID, namespace, and job name.
        """
        cluster_uid, namespace, job_name = infrastructure_pid.split(":", 2)
        return cluster_uid, namespace, job_name

    def _get_cluster_uid(self) -> str:
        """
        Gets a unique id for the current cluster being used.

        There is no real unique identifier for a cluster. However, the `kube-system`
        namespace is immutable and has a persistence UID that we use instead.

        PREFECT_KUBERNETES_CLUSTER_UID can be set in cases where the `kube-system`
        namespace cannot be read e.g. when a cluster role cannot be created. If set,
        this variable will be used and we will not attempt to read the `kube-system`
        namespace.

        See https://github.com/kubernetes/kubernetes/issues/44954
        """
        # Default to an environment variable
        env_cluster_uid = os.environ.get("PREFECT_KUBERNETES_CLUSTER_UID")
        if env_cluster_uid:
            return env_cluster_uid

        # Read the UID from the cluster namespace
        with self.get_client() as client:
            namespace = client.read_namespace("kube-system")
        cluster_uid = namespace.metadata.uid

        return cluster_uid

    def _configure_kubernetes_library_client(self) -> None:
        """
        Set the correct kubernetes client configuration.

        WARNING: This action is not threadsafe and may override the configuration
                  specified by another `KubernetesJob` instance.
        """
        # TODO: Investigate returning a configured client so calls on other threads
        #       will not invalidate the config needed here

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

    def _shortcut_customizations(self) -> JsonPatch:
        """Produces the JSON 6902 patch for the most commonly used customizations, like
        image and namespace, which we offer as top-level parameters (with sensible
        default values)"""
        shortcuts = []

        if self.namespace:
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/metadata/namespace",
                    "value": self.namespace,
                }
            )

        if self.image:
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/spec/template/spec/containers/0/image",
                    "value": self.image,
                }
            )

        shortcuts += [
            {
                "op": "add",
                "path": (
                    f"/metadata/labels/{self._slugify_label_key(key).replace('/', '~1', 1)}"
                ),
                "value": self._slugify_label_value(value),
            }
            for key, value in self.labels.items()
        ]

        shortcuts += [
            {
                "op": "add",
                "path": "/spec/template/spec/containers/0/env/-",
                "value": {"name": key, "value": value},
            }
            for key, value in self._get_environment_variables().items()
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

        if self.finished_job_ttl is not None:
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/spec/ttlSecondsAfterFinished",
                    "value": self.finished_job_ttl,
                }
            )

        if self.command:
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/spec/template/spec/containers/0/args",
                    "value": self.command,
                }
            )

        if self.name:
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/metadata/generateName",
                    "value": self._slugify_name(self.name) + "-",
                }
            )
        else:
            # Generate name is required
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/metadata/generateName",
                    "value": (
                        "prefect-job-"
                        # We generate a name using a hash of the primary job settings
                        + stable_hash(
                            *self.command if self.command else "",
                            *self.env.keys(),
                            *[v for v in self.env.values() if v is not None],
                        )
                        + "-"
                    ),
                }
            )

        return JsonPatch(shortcuts)

    def _get_job(self, job_id: str) -> Optional["V1Job"]:
        with self.get_batch_client() as batch_client:
            try:
                job = batch_client.read_namespaced_job(job_id, self.namespace)
            except kubernetes.client.exceptions.ApiException:
                self.logger.error(f"Job {job_id!r} was removed.", exc_info=True)
                return None
            return job

    def _get_job_pod(self, job_name: str) -> "V1Pod":
        """Get the first running pod for a job."""

        # Wait until we find a running pod for the job
        # if `pod_watch_timeout_seconds` is None, no timeout will be enforced
        watch = kubernetes.watch.Watch()
        self.logger.debug(f"Job {job_name!r}: Starting watch for pod start...")
        last_phase = None
        with self.get_client() as client:
            for event in watch.stream(
                func=client.list_namespaced_pod,
                namespace=self.namespace,
                label_selector=f"job-name={job_name}",
                timeout_seconds=self.pod_watch_timeout_seconds,
            ):
                phase = event["object"].status.phase
                if phase != last_phase:
                    self.logger.info(f"Job {job_name!r}: Pod has status {phase!r}.")

                if phase != "Pending":
                    watch.stop()
                    return event["object"]

                last_phase = phase

        self.logger.error(f"Job {job_name!r}: Pod never started.")

    def _watch_job(self, job_name: str) -> int:
        """
        Watch a job.

        Return the final status code of the first container.
        """
        self.logger.debug(f"Job {job_name!r}: Monitoring job...")

        job = self._get_job(job_name)
        if not job:
            return -1

        pod = self._get_job_pod(job_name)
        if not pod:
            return -1

        # Calculate the deadline before streaming output
        deadline = (
            (time.monotonic() + self.job_watch_timeout_seconds)
            if self.job_watch_timeout_seconds is not None
            else None
        )

        if self.stream_output:
            with self.get_client() as client:
                logs = client.read_namespaced_pod_log(
                    pod.metadata.name,
                    self.namespace,
                    follow=True,
                    _preload_content=False,
                    container="prefect-job",
                )
                try:
                    for log in logs.stream():
                        print(log.decode().rstrip())

                        # Check if we have passed the deadline and should stop streaming
                        # logs
                        remaining_time = (
                            deadline - time.monotonic() if deadline else None
                        )
                        if deadline and remaining_time <= 0:
                            break

                except Exception:
                    self.logger.warning(
                        (
                            "Error occurred while streaming logs - "
                            "Job will continue to run but logs will "
                            "no longer be streamed to stdout."
                        ),
                        exc_info=True,
                    )

        with self.get_batch_client() as batch_client:
            # Check if the job is completed before beginning a watch
            job = batch_client.read_namespaced_job(
                name=job_name, namespace=self.namespace
            )
            completed = job.status.completion_time is not None

            while not completed:
                remaining_time = (
                    math.ceil(deadline - time.monotonic()) if deadline else None
                )
                if deadline and remaining_time <= 0:
                    self.logger.error(
                        f"Job {job_name!r}: Job did not complete within "
                        f"timeout of {self.job_watch_timeout_seconds}s."
                    )
                    return -1

                watch = kubernetes.watch.Watch()
                # The kubernetes library will disable retries if the timeout kwarg is
                # present regardless of the value so we do not pass it unless given
                # https://github.com/kubernetes-client/python/blob/84f5fea2a3e4b161917aa597bf5e5a1d95e24f5a/kubernetes/base/watch/watch.py#LL160
                timeout_seconds = (
                    {"timeout_seconds": remaining_time} if deadline else {}
                )

                for event in watch.stream(
                    func=batch_client.list_namespaced_job,
                    field_selector=f"metadata.name={job_name}",
                    namespace=self.namespace,
                    **timeout_seconds,
                ):
                    if event["type"] == "DELETED":
                        self.logger.error(f"Job {job_name!r}: Job has been deleted.")
                        completed = True
                    elif event["object"].status.completion_time:
                        if not event["object"].status.succeeded:
                            # Job failed, exit while loop and return pod exit code
                            self.logger.error(f"Job {job_name!r}: Job failed.")
                        completed = True
                    # Check if the job has reached its backoff limit
                    # and stop watching if it has
                    elif (
                        event["object"].spec.backoff_limit is not None
                        and event["object"].status.failed is not None
                        and event["object"].status.failed
                        > event["object"].spec.backoff_limit
                    ):
                        self.logger.error(
                            f"Job {job_name!r}: Job reached backoff limit."
                        )
                        completed = True
                    # If the job has no backoff limit, check if it has failed
                    # and stop watching if it has
                    elif (
                        not event["object"].spec.backoff_limit
                        and event["object"].status.failed
                    ):
                        completed = True

                    if completed:
                        watch.stop()
                        break

        with self.get_client() as core_client:
            # Get all pods for the job
            pods = core_client.list_namespaced_pod(
                namespace=self.namespace, label_selector=f"job-name={job_name}"
            )
            # Get the status for only the most recently used pod
            pods.items.sort(
                key=lambda pod: pod.metadata.creation_timestamp, reverse=True
            )
            most_recent_pod = pods.items[0] if pods.items else None
            first_container_status = (
                most_recent_pod.status.container_statuses[0]
                if most_recent_pod
                else None
            )
            if not first_container_status:
                self.logger.error(f"Job {job_name!r}: No pods found for job.")
                return -1

            # In some cases, such as spot instance evictions, the pod will be forcibly
            # terminated and not report a status correctly.
            elif (
                first_container_status.state is None
                or first_container_status.state.terminated is None
                or first_container_status.state.terminated.exit_code is None
            ):
                self.logger.error(
                    f"Could not determine exit code for {job_name!r}."
                    "Exit code will be reported as -1."
                    "First container status info did not report an exit code."
                    f"First container info: {first_container_status}."
                )
                return -1

        return first_container_status.state.terminated.exit_code

    def _create_job(self, job_manifest: KubernetesManifest) -> "V1Job":
        """
        Given a Kubernetes Job Manifest, create the Job on the configured Kubernetes
        cluster and return its name.
        """
        with self.get_batch_client() as batch_client:
            job = batch_client.create_namespaced_job(self.namespace, job_manifest)
        return job

    def _slugify_name(self, name: str) -> str:
        """
        Slugify text for use as a name.

        Keeps only alphanumeric characters and dashes, and caps the length
        of the slug at 45 chars.

        The 45 character length allows room for the k8s utility
        "generateName" to generate a unique name from the slug while
        keeping the total length of a name below 63 characters, which is
        the limit for e.g. label names that follow RFC 1123 (hostnames) and
        RFC 1035 (domain names).

        Args:
            name: The name of the job

        Returns:
            the slugified job name
        """
        slug = slugify(
            name,
            max_length=45,  # Leave enough space for generateName
            regex_pattern=r"[^a-zA-Z0-9-]+",
        )

        # TODO: Handle the case that the name is an empty string after being
        # slugified.

        return slug

    def _slugify_label_key(self, key: str) -> str:
        """
        Slugify text for use as a label key.

        Keys are composed of an optional prefix and name, separated by a slash (/).

        Keeps only alphanumeric characters, dashes, underscores, and periods.
        Limits the length of the label prefix to 253 characters.
        Limits the length of the label name to 63 characters.

        See https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#syntax-and-character-set

        Args:
            key: The label key

        Returns:
            The slugified label key
        """
        if "/" in key:
            prefix, name = key.split("/", maxsplit=1)
        else:
            prefix = None
            name = key

        name_slug = (
            slugify(name, max_length=63, regex_pattern=r"[^a-zA-Z0-9-_.]+").strip(
                "_-."  # Must start or end with alphanumeric characters
            )
            or name
        )
        # Fallback to the original if we end up with an empty slug, this will allow
        # Kubernetes to throw the validation error

        if prefix:
            prefix_slug = (
                slugify(
                    prefix,
                    max_length=253,
                    regex_pattern=r"[^a-zA-Z0-9-\.]+",
                ).strip("_-.")  # Must start or end with alphanumeric characters
                or prefix
            )

            return f"{prefix_slug}/{name_slug}"

        return name_slug

    def _slugify_label_value(self, value: str) -> str:
        """
        Slugify text for use as a label value.

        Keeps only alphanumeric characters, dashes, underscores, and periods.
        Limits the total length of label text to below 63 characters.

        See https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#syntax-and-character-set

        Args:
            value: The text for the label

        Returns:
            The slugified value
        """
        slug = (
            slugify(value, max_length=63, regex_pattern=r"[^a-zA-Z0-9-_\.]+").strip(
                "_-."  # Must start or end with alphanumeric characters
            )
            or value
        )
        # Fallback to the original if we end up with an empty slug, this will allow
        # Kubernetes to throw the validation error

        return slug

    def _get_environment_variables(self):
        # If the API URL has been set by the base environment rather than the by the
        # user, update the value to ensure connectivity when using a bridge network by
        # updating local connections to use the internal host
        env = {**self._base_environment(), **self.env}

        if (
            "PREFECT_API_URL" in env
            and "PREFECT_API_URL" not in self.env
            and self._api_dns_name
        ):
            env["PREFECT_API_URL"] = (
                env["PREFECT_API_URL"]
                .replace("localhost", self._api_dns_name)
                .replace("127.0.0.1", self._api_dns_name)
            )

        # Drop null values allowing users to "unset" variables
        return {key: value for key, value in env.items() if value is not None}

import copy
import enum
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Union

import anyio.abc
import yaml
from pydantic import Field, validator
from typing_extensions import Literal

from prefect.blocks.kubernetes import KubernetesClusterConfig
from prefect.docker import get_prefect_image_name
from prefect.infrastructure.base import Infrastructure, InfrastructureResult
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible
from prefect.utilities.hashing import stable_hash
from prefect.utilities.importtools import lazy_import
from prefect.utilities.pydantic import JsonPatch
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    import kubernetes
    import kubernetes.client
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


class KubernetesJob(Infrastructure):
    """
    Runs a command as a Kubernetes Job.

    Attributes:
        command: A list of strings specifying the command to run in the container to
            start the flow run. In most cases you should not override this.
        customizations: A list of JSON 6902 patches to apply to the base Job manifest.
        env: Environment variables to set for the container.
        image: An optional string specifying the tag of a Docker image to use for the job.
            Defaults to the Prefect image.
        image_pull_policy: The Kubernetes image pull policy to use for job containers.
        job: The base manifest for the Kubernetes Job.
        job_watch_timeout_seconds: Number of seconds to watch for job creation before timing out (default 5).
        labels: An optional dictionary of labels to add to the job.
        name: An optional name for the job.
        namespace: An optional string signifying the Kubernetes namespace to use.
        pod_watch_timeout_seconds: Number of seconds to watch for pod creation before timing out (default 5).
        service_account_name: An optional string specifying which Kubernetes service account to use.
        stream_output: If set, stream output from the job to local standard output.
        finished_job_ttl: The number of seconds to retain jobs after completion. If set, finished jobs will
            be cleaned up by Kubernetes after the given delay. If None (default), jobs will need to be
            manually removed.
    """

    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/1zrSeY8DZ1MJZs2BAyyyGk/20445025358491b8b72600b8f996125b/Kubernetes_logo_without_workmark.svg.png?h=250"

    type: Literal["kubernetes-job"] = Field(
        default="kubernetes-job", description="The type of infrastructure."
    )
    # shortcuts for the most common user-serviceable settings
    image: str = Field(
        default_factory=get_prefect_image_name,
        description="The tag of a Docker image to use for the job. Defaults to the Prefect image.",
    )
    namespace: str = Field(
        default="default", description="The Kubernetes namespace to use for this job."
    )
    service_account_name: Optional[str] = Field(
        default=None, description="The Kubernetes service account to use for this job."
    )
    image_pull_policy: Optional[KubernetesImagePullPolicy] = Field(
        default=None,
        description="The Kubernetes image pull policy to use for job containers.",
    )

    # connection to a cluster
    cluster_config: Optional[KubernetesClusterConfig] = None

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
    job_watch_timeout_seconds: int = Field(
        default=5,
        description="Number of seconds to watch for job creation before timing out.",
    )
    pod_watch_timeout_seconds: int = Field(
        default=60,
        description="Number of seconds to watch for pod creation before timing out.",
    )
    stream_output: bool = Field(
        default=True,
        description="If set, output will be streamed from the job to local standard output.",
    )
    finished_job_ttl: Optional[int] = Field(
        default=None,
        description="The number of seconds to retain jobs after completion. If set, finished jobs will be cleaned up by Kubernetes after the given delay. If None (default), jobs will need to be manually removed.",
    )

    # internal-use only right now
    _api_dns_name: Optional[str] = None  # Replaces 'localhost' in API URL

    _block_type_name = "Kubernetes Job"

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
    ) -> Optional[bool]:
        if not self.command:
            raise ValueError("Kubernetes job cannot be run with empty command.")

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

        manifest = self.build_job()
        job_name = await run_sync_in_worker_thread(self._create_job, manifest)

        # Indicate that the job has started
        if task_status is not None:
            task_status.started(job_name)

        # Monitor the job
        return await run_sync_in_worker_thread(self._watch_job, job_name)

    def preview(self):
        return yaml.dump(self.build_job())

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
                "path": f"/metadata/labels/{self._slugify_label_key(key).replace('/', '~1', 1)}",
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
                    "value": self._slugify_name(self.name),
                }
            )
        else:
            # Generate name is required
            shortcuts.append(
                {
                    "op": "add",
                    "path": "/metadata/generateName",
                    "value": "prefect-job-"
                    # We generate a name using a hash of the primary job settings
                    + stable_hash(
                        *self.command,
                        *self.env.keys(),
                        *[v for v in self.env.values() if v is not None],
                    ),
                }
            )

        return JsonPatch(shortcuts)

    def _get_job(self, job_id: str) -> Optional["V1Job"]:
        with self.get_batch_client() as batch_client:
            try:
                job = batch_client.read_namespaced_job(job_id, self.namespace)
            except kubernetes.ApiException:
                self.logger.error(f"Job{job_id!r} was removed.", exc_info=True)
                return None
            return job

    def _get_job_pod(self, job_name: str) -> "V1Pod":
        """Get the first running pod for a job."""

        # Wait until we find a running pod for the job
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

    def _watch_job(self, job_name: str) -> bool:
        job = self._get_job(job_name)
        if not job:
            return KubernetesJobResult(status_code=-1, identifier=job_name)

        pod = self._get_job_pod(job_name)
        if not pod:
            return KubernetesJobResult(status_code=-1, identifier=job.metadata.name)

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
        self.logger.debug(f"Job {job_name!r}: Starting watch for job completion")
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
                self.logger.error(f"Job {job_name!r}: Job did not complete.")
                return KubernetesJobResult(status_code=-1, identifier=job.metadata.name)

        with self.get_client() as client:
            pod_status = client.read_namespaced_pod_status(
                namespace=self.namespace, name=pod.metadata.name
            )
            first_container_status = pod_status.status.container_statuses[0]

        return KubernetesJobResult(
            status_code=first_container_status.state.terminated.exit_code,
            identifier=job.metadata.name,
        )

    def _create_job(self, job_manifest: KubernetesManifest) -> str:
        """
        Given a Kubernetes Job Manifest, create the Job on the configured Kubernetes
        cluster and return its name.
        """
        with self.get_batch_client() as batch_client:
            job = batch_client.create_namespaced_job(self.namespace, job_manifest)
        return job.metadata.name

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

        # TODO: Note that the name must start and end with an alphanumeric character
        #       but that is not enforced here

        name_slug = (
            slugify(
                name,
                max_length=63,
                regex_pattern=r"[^a-zA-Z0-9-_.]+",
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
                )
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
        # TODO: Note that the text must start and end with an alphanumeric character
        #       but that is not enforced here
        slug = (
            slugify(
                value,
                max_length=63,
                regex_pattern=r"[^a-zA-Z0-9-_\.]+",
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

"""

Module containing the Kubernetes worker used for executing flow runs as Kubernetes jobs.

To start a Kubernetes worker, run the following command:

```bash
prefect worker start --pool 'my-work-pool' --type kubernetes
```

Replace `my-work-pool` with the name of the work pool you want the worker
to poll for flow runs.

### Securing your Prefect Cloud API key
If you are using Prefect Cloud and would like to pass your Prefect Cloud API key to
created jobs via a Kubernetes secret, set the
`PREFECT_INTEGRATIONS_KUBERNETES_WORKER_CREATE_SECRET_FOR_API_KEY` environment variable before
starting your worker:

```bash
export PREFECT_INTEGRATIONS_KUBERNETES_WORKER_CREATE_SECRET_FOR_API_KEY="true"
prefect worker start --pool 'my-work-pool' --type kubernetes
```

Note that your work will need permission to create secrets in the same namespace(s)
that Kubernetes jobs are created in to execute flow runs.

### Using a custom Kubernetes job manifest template

The default template used for Kubernetes job manifests looks like this:
```yaml
---
apiVersion: batch/v1
kind: Job
metadata:
annotations: "{{ annotations }}"
labels: "{{ labels }}"
namespace: "{{ namespace }}"
generateName: "{{ name }}-"
spec:
ttlSecondsAfterFinished: "{{ finished_job_ttl }}"
template:
    spec:
    parallelism: 1
    completions: 1
    restartPolicy: Never
    serviceAccountName: "{{ service_account_name }}"
    containers:
    - name: prefect-job
        env: "{{ env }}"
        image: "{{ image }}"
        imagePullPolicy: "{{ image_pull_policy }}"
        args: "{{ command }}"
```

Each values enclosed in `{{ }}` is a placeholder that will be replaced with
a value at runtime. The values that can be used a placeholders are defined
by the `variables` schema defined in the base job template.

The default job manifest and available variables can be customized on a work pool
by work pool basis. These customizations can be made via the Prefect UI when
creating or editing a work pool.

For example, if you wanted to allow custom memory requests for a Kubernetes work
pool you could update the job manifest template to look like this:

```yaml
---
apiVersion: batch/v1
kind: Job
metadata:
annotations: "{{ annotations }}"
labels: "{{ labels }}"
namespace: "{{ namespace }}"
generateName: "{{ name }}-"
spec:
ttlSecondsAfterFinished: "{{ finished_job_ttl }}"
template:
    spec:
    parallelism: 1
    completions: 1
    restartPolicy: Never
    serviceAccountName: "{{ service_account_name }}"
    containers:
    - name: prefect-job
        env: "{{ env }}"
        image: "{{ image }}"
        imagePullPolicy: "{{ image_pull_policy }}"
        args: "{{ command }}"
        resources:
            requests:
                memory: "{{ memory }}Mi"
            limits:
                memory: 128Mi
```

In this new template, the `memory` placeholder allows customization of the memory
allocated to Kubernetes jobs created by workers in this work pool, but the limit
is hard-coded and cannot be changed by deployments.

For more information about work pools and workers,
checkout out the [Prefect docs](https://www.prefect.io/docs/concepts/work-pools/).
"""

from __future__ import annotations

import base64
import enum
import json
import uuid
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
)

import anyio
import anyio.abc
import kubernetes_asyncio
from jsonpatch import JsonPatch
from kubernetes_asyncio import config
from kubernetes_asyncio.client import (
    ApiClient,
    BatchV1Api,
    CoreV1Api,
    V1Job,
)
from kubernetes_asyncio.client.exceptions import ApiException
from kubernetes_asyncio.client.models import (
    V1ObjectMeta,
    V1Secret,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_fixed,
    wait_random,
)
from typing_extensions import Literal, Self

import prefect
from prefect.client.schemas.objects import Flow as APIFlow
from prefect.exceptions import (
    InfrastructureError,
    InfrastructureNotFound,
)
from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.utilities.processutils import command_from_string
from prefect.utilities.templating import find_placeholders
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)
from prefect_kubernetes.credentials import KubernetesClusterConfig
from prefect_kubernetes.observer import start_observer, stop_observer
from prefect_kubernetes.settings import KubernetesSettings
from prefect_kubernetes.utilities import (
    KeepAliveClientRequest,
    _slugify_label_key,
    _slugify_label_value,
    _slugify_name,
)

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.objects import FlowRun, WorkPool
    from prefect.client.schemas.responses import DeploymentResponse

# Captures flow return type
R = TypeVar("R")

# Bounds cleaning up per-job Secrets, which runs shielded from cancellation
JOB_SECRET_CLEANUP_TIMEOUT_SECONDS = 30


def _get_default_job_manifest_template() -> Dict[str, Any]:
    """Returns the default job manifest template used by the Kubernetes worker."""
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "annotations": "{{ annotations }}",
            "labels": "{{ labels }}",
            "namespace": "{{ namespace }}",
            "generateName": "{{ name }}-",
        },
        "spec": {
            "backoffLimit": "{{ backoff_limit }}",
            "ttlSecondsAfterFinished": "{{ finished_job_ttl }}",
            "template": {
                "spec": {
                    "parallelism": 1,
                    "completions": 1,
                    "restartPolicy": "Never",
                    "serviceAccountName": "{{ service_account_name }}",
                    "containers": [
                        {
                            "name": "prefect-job",
                            "env": "{{ env }}",
                            "image": "{{ image }}",
                            "imagePullPolicy": "{{ image_pull_policy }}",
                            "args": "{{ command }}",
                            "resources": {
                                "limits": {
                                    "cpu": "{{ cpu_limit }}",
                                    "memory": "{{ memory_limit }}",
                                },
                                "requests": {
                                    "cpu": "{{ cpu_request }}",
                                    "memory": "{{ memory_request }}",
                                },
                            },
                        }
                    ],
                }
            },
        },
    }


def _get_base_job_manifest():
    """Returns a base job manifest to use for manifest validation."""
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"annotations": {}, "labels": {}},
        "spec": {
            "template": {
                "spec": {
                    "parallelism": 1,
                    "completions": 1,
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "prefect-job",
                        }
                    ],
                }
            }
        },
    }


class KubernetesImagePullPolicy(enum.Enum):
    """Enum representing the image pull policy options for a Kubernetes job."""

    IF_NOT_PRESENT = "IfNotPresent"
    ALWAYS = "Always"
    NEVER = "Never"


class KubernetesRegistryCredentials(BaseModel):
    """
    Credentials for pulling a flow run's image from a private registry.

    The fields match `prefect_docker.credentials.DockerRegistryCredentials`, and the
    JSON schema carries that block type's slug, so a reference to an existing
    `DockerRegistryCredentials` block can be selected for the `registry_credentials`
    job variable without installing `prefect-docker` alongside the worker.
    """

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "block_type_slug": "docker-registry-credentials",
            "secret_fields": ["password"],
            "block_schema_references": {},
        },
    )

    username: str = Field(description="The username to log into the registry with.")
    password: SecretStr = Field(
        description="The password to log into the registry with."
    )
    registry_url: str = Field(
        description=(
            "The URL to the registry, as passed to `docker login`. Generally, "
            '"http" or "https" can be omitted.'
        ),
        examples=["index.docker.io"],
    )

    def to_docker_config_json(self) -> str:
        """Returns the content of a `kubernetes.io/dockerconfigjson` Secret."""
        username = self.username
        password = self.password.get_secret_value()
        auth = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode(
            "utf-8"
        )
        return json.dumps(
            {
                "auths": {
                    self.registry_url: {
                        "username": username,
                        "password": password,
                        "auth": auth,
                    }
                }
            }
        )


class KubernetesWorkerJobConfiguration(BaseJobConfiguration):
    """
    Configuration class used by the Kubernetes worker.

    An instance of this class is passed to the Kubernetes worker's `run` method
    for each flow run. It contains all of the information necessary to execute
    the flow run as a Kubernetes job.

    Attributes:
        name: The name to give to created Kubernetes job.
        command: The command executed in created Kubernetes jobs to kick off
            flow run execution.
        env: The environment variables to set in created Kubernetes jobs.
        labels: The labels to set on created Kubernetes jobs.
        namespace: The Kubernetes namespace to create Kubernetes jobs in.
        job_manifest: The Kubernetes job manifest to use to create Kubernetes jobs.
        cluster_config: The Kubernetes cluster configuration to use for authentication
            to a Kubernetes cluster.
        job_watch_timeout_seconds: The number of seconds to wait for the job to
            complete before timing out. If `None`, the worker will wait indefinitely.
        pod_watch_timeout_seconds: The number of seconds to wait for the pod to
            complete before timing out.
        stream_output: Whether or not to stream the job's output.
    """

    annotations: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Annotations applied to infrastructure created by the worker using "
            "this job configuration."
        ),
    )
    namespace: str = Field(default="default")
    job_manifest: Dict[str, Any] = Field(
        json_schema_extra=dict(template=_get_default_job_manifest_template())
    )
    cluster_config: Optional[KubernetesClusterConfig] = Field(default=None)
    job_watch_timeout_seconds: Optional[int] = Field(default=None)
    pod_watch_timeout_seconds: int = Field(default=60)
    stream_output: bool = Field(default=True)
    registry_credentials: Optional[KubernetesRegistryCredentials] = Field(default=None)

    env: Union[Dict[str, Optional[str]], List[Dict[str, Any]]] = Field(
        default_factory=dict
    )

    # internal-use only
    _api_dns_name: Optional[str] = None  # Replaces 'localhost' in API URL

    @model_validator(mode="after")
    def _validate_job_manifest(self) -> Self:
        """
        Validates the job manifest by ensuring the presence of required fields
        and checking for compatible values.
        """
        job_manifest = self.job_manifest
        # Ensure metadata is present
        if "metadata" not in job_manifest:
            job_manifest["metadata"] = {}

        # Ensure annotations is present in metadata
        if "annotations" not in job_manifest["metadata"]:
            job_manifest["metadata"]["annotations"] = {}

        # Ensure labels is present in metadata
        if "labels" not in job_manifest["metadata"]:
            job_manifest["metadata"]["labels"] = {}

        # Ensure namespace is present in metadata
        if "namespace" not in job_manifest["metadata"]:
            job_manifest["metadata"]["namespace"] = self.namespace

        # Check if job includes all required components
        patch = JsonPatch.from_diff(job_manifest, _get_base_job_manifest())
        missing_paths = sorted([op["path"] for op in patch if op["op"] == "add"])
        if missing_paths:
            raise ValueError(
                "Job is missing required attributes at the following paths: "
                f"{', '.join(missing_paths)}"
            )

        # Check if job has compatible values
        incompatible = sorted(
            [
                f"{op['path']} must have value {op['value']!r}"
                for op in patch
                if op["op"] == "replace"
            ]
        )
        if incompatible:
            raise ValueError(
                "Job has incompatible values for the following attributes: "
                f"{', '.join(incompatible)}"
            )

        return self

    @field_validator("env", mode="before")
    @classmethod
    def _coerce_env(cls, v):
        if isinstance(v, list):
            return v
        return {k: str(v) if v is not None else None for k, v in v.items()}

    @staticmethod
    def _base_flow_run_labels(flow_run: "FlowRun") -> Dict[str, str]:
        """
        Generate a dictionary of labels for a flow run job.
        """
        slugified_version = _slugify_label_value(prefect.__version__.split("+")[0])
        return {
            "prefect.io/flow-run-id": str(flow_run.id),
            "prefect.io/flow-run-name": flow_run.name,
            "prefect.io/version": slugified_version,
            "app.kubernetes.io/managed-by": "prefect",
            "app.kubernetes.io/part-of": "prefect",
            "app.kubernetes.io/version": slugified_version,
        }

    @staticmethod
    def _base_flow_labels(flow: "APIFlow | None") -> Dict[str, str]:
        """
        Generate a dictionary of labels for a flow run job, including standard
        app.kubernetes.io labels.
        """
        labels = BaseJobConfiguration._base_flow_labels(flow)
        if flow is not None:
            labels["app.kubernetes.io/name"] = _slugify_label_value(flow.name)
        return labels

    @staticmethod
    def _base_deployment_labels(
        deployment: "DeploymentResponse | None",
    ) -> Dict[str, str]:
        """
        Generate a dictionary of labels for a deployment, including standard
        app.kubernetes.io labels.
        """
        labels = BaseJobConfiguration._base_deployment_labels(deployment)
        if deployment is not None:
            labels["app.kubernetes.io/name"] = _slugify_label_value(deployment.name)
        return labels

    def get_environment_variable_value(self, name: str) -> str | None:
        """
        Returns the value of an environment variable from the job manifest.
        """
        manifest_env: list[dict[str, Any]] = self.job_manifest["spec"]["template"][
            "spec"
        ]["containers"][0].get("env", [])
        return next(
            (
                env_entry.get("value")
                for env_entry in manifest_env
                if env_entry.get("name") == name
            ),
            None,
        )

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: "DeploymentResponse | None" = None,
        flow: "APIFlow | None" = None,
        work_pool: "WorkPool | None" = None,
        worker_name: str | None = None,
        worker_id: "UUID | None" = None,
    ):
        """
        Prepares the job configuration for a flow run.

        Ensures that necessary values are present in the job manifest and that the
        job manifest is valid.

        Args:
            flow_run: The flow run to prepare the job configuration for
            deployment: The deployment associated with the flow run used for
                preparation.
            flow: The flow associated with the flow run used for preparation.
            work_pool: The work pool associated with the flow run used for preparation.
            worker_name: The name of the worker used for preparation.
        """
        # Save special Kubernetes env vars (like those with valueFrom)
        special_env_vars = []
        if isinstance(self.env, list):
            special_env_vars = [item for item in self.env if "valueFrom" in item]
            original_env = {}
            for item in self.env:
                if "name" in item and "value" in item:
                    original_env[item["name"]] = item.get("value")
            self.env = original_env

        super().prepare_for_flow_run(
            flow_run, deployment, flow, work_pool, worker_name, worker_id=worker_id
        )

        self._update_prefect_api_url_if_local_server()

        # Restore any special env vars with valueFrom before populating the manifest
        if special_env_vars:
            # Convert dict env back to list format
            env_list = [{"name": k, "value": v} for k, v in self.env.items()]
            # Add special env vars back in
            env_list.extend(special_env_vars)
            self.env = env_list

        # After the restore, so a `valueFrom` behavior is visible here instead of
        # being appended back on top of what we set.
        self._configure_eviction_handling()

        self._populate_env_in_manifest()
        self._slugify_labels()
        self._slugify_annotations()
        self._populate_image_if_not_present()
        self._populate_command_if_not_present()
        self._populate_generate_name_if_not_present()
        self._propagate_labels_to_pod()
        self._propagate_annotations_to_pod()

    def _configure_eviction_handling(self):
        """
        Configures eviction handling for the job pod. Needs to run before

        If `backoffLimit` is set to 0 and `PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR` is
        not set in env, we'll tell the Runner to reschedule its flow run when it receives
        a SIGTERM.

        If `backoffLimit` is anything other than 0 (including absent, where Kubernetes
        defaults it to 6), Kubernetes owns Job retries, so we tell the supervisor to
        `relinquish` the run on SIGTERM instead of proposing a terminal state.
        """
        # If backoffLimit is set to 0, we'll tell the Runner to reschedule
        # its flow run when it receives a SIGTERM.
        if self.job_manifest["spec"].get("backoffLimit") == 0:
            if isinstance(self.env, dict):
                if not self.env.get("PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR"):
                    self.env["PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR"] = "reschedule"
            elif not any(
                v.get("name") == "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR"
                for v in self.env
            ):
                self.env.append(
                    {
                        "name": "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR",
                        "value": "reschedule",
                    }
                )
        # Otherwise Kubernetes owns retries, so the run must not be finalized.
        else:
            if isinstance(self.env, dict):
                self.env["PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR"] = "relinquish"
            else:
                self.env = [
                    v
                    for v in self.env
                    if v.get("name") != "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR"
                ]
                self.env.append(
                    {
                        "name": "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR",
                        "value": "relinquish",
                    }
                )

    def _populate_env_in_manifest(self):
        """
        Populates environment variables in the job manifest.

        When `env` is templated as a variable in the job manifest it comes in as a
        dictionary. We need to convert it to a list of dictionaries to conform to the
        Kubernetes job manifest schema.

        This function also handles the case where the user has removed the `{{ env }}`
        placeholder and hard coded a value for `env`. In this case, we need to prepend
        our environment variables to the list to ensure Prefect setting propagation.
        An example reason the a user would remove the `{{ env }}` placeholder to
        hardcode Kubernetes secrets in the base job template.
        """
        # Handle both dictionary and list formats for environment variables
        if isinstance(self.env, dict):
            transformed_env = [{"name": k, "value": v} for k, v in self.env.items()]
        else:
            # If env is already a list (k8s format), use it directly
            transformed_env = self.env

        template_env = self.job_manifest["spec"]["template"]["spec"]["containers"][
            0
        ].get("env")

        # If user has removed `{{ env }}` placeholder and hard coded a value for `env`,
        # we need to prepend our environment variables to the list to ensure Prefect
        # setting propagation.
        if isinstance(template_env, list):
            # Get the names of env vars we're about to add
            transformed_env_names = {env["name"] for env in transformed_env}

            # Filter out any env vars from template_env that are duplicates
            # (these came from template rendering of work pool variables)
            # Keep only user-hardcoded vars (not in transformed_env)
            unique_template_env = [
                env
                for env in template_env
                if env.get("name") not in transformed_env_names
            ]

            self.job_manifest["spec"]["template"]["spec"]["containers"][0]["env"] = [
                *transformed_env,
                *unique_template_env,
            ]
        # Current templating adds `env` as a dict when the kubernetes manifest requires
        # a list of dicts. Might be able to improve this in the future with a better
        # default `env` value and better typing.
        else:
            self.job_manifest["spec"]["template"]["spec"]["containers"][0]["env"] = (
                transformed_env
            )

    def _update_prefect_api_url_if_local_server(self):
        """If the API URL has been set by the base environment rather than the by the
        user, update the value to ensure connectivity when using a bridge network by
        updating local connections to use the internal host
        """
        if isinstance(self.env, dict):
            if (api_url := self.env.get("PREFECT_API_URL")) and self._api_dns_name:
                self.env["PREFECT_API_URL"] = api_url.replace(
                    "localhost", self._api_dns_name
                ).replace("127.0.0.1", self._api_dns_name)
        else:
            # Handle list format
            for env_var in self.env:
                if (
                    env_var.get("name") == "PREFECT_API_URL"
                    and self._api_dns_name
                    and (value := env_var.get("value"))
                ):
                    env_var["value"] = value.replace(
                        "localhost", self._api_dns_name
                    ).replace("127.0.0.1", self._api_dns_name)

    def _slugify_labels(self):
        """Slugifies the labels in the job manifest."""
        all_labels = {**self.job_manifest["metadata"].get("labels", {}), **self.labels}
        self.job_manifest["metadata"]["labels"] = {
            _slugify_label_key(k): _slugify_label_value(v)
            for k, v in all_labels.items()
        }

    def _populate_image_if_not_present(self):
        """Ensures that the image is present in the job manifest. Populates the image
        with the default Prefect image if it is not present."""
        try:
            if (
                "image"
                not in self.job_manifest["spec"]["template"]["spec"]["containers"][0]
            ):
                self.job_manifest["spec"]["template"]["spec"]["containers"][0][
                    "image"
                ] = get_prefect_image_name()
        except KeyError:
            raise ValueError(
                "Unable to verify image due to invalid job manifest template."
            )

    def _populate_command_if_not_present(self):
        """
        Ensures that the command is present in the job manifest. Populates the command
        with the `prefect -m prefect.engine` if a command is not present.
        """
        try:
            command = self.job_manifest["spec"]["template"]["spec"]["containers"][
                0
            ].get("args")
            if command is None:
                self.job_manifest["spec"]["template"]["spec"]["containers"][0][
                    "args"
                ] = command_from_string(self._base_flow_run_command())
            elif isinstance(command, str):
                self.job_manifest["spec"]["template"]["spec"]["containers"][0][
                    "args"
                ] = command_from_string(command)
            elif not isinstance(command, list):
                raise ValueError(
                    "Invalid job manifest template: 'command' must be a string or list."
                )
        except KeyError:
            raise ValueError(
                "Unable to verify command due to invalid job manifest template."
            )

    def _populate_generate_name_if_not_present(self):
        """Ensures that the generateName is present in the job manifest."""
        manifest_generate_name = self.job_manifest["metadata"].get("generateName", "")
        has_placeholder = len(find_placeholders(manifest_generate_name)) > 0
        # if name wasn't present during template rendering, generateName will be
        # just a hyphen

        manifest_generate_name_templated_with_empty_string = (
            manifest_generate_name == "-"
        )
        if (
            not manifest_generate_name
            or has_placeholder
            or manifest_generate_name_templated_with_empty_string
            or manifest_generate_name == "None-"
        ):
            generate_name = None
            if self.name:
                generate_name = _slugify_name(self.name)
            # _slugify_name will return None if the slugified name in an exception
            if not generate_name:
                generate_name = "prefect-job"
            self.job_manifest["metadata"]["generateName"] = f"{generate_name}-"

    def _propagate_labels_to_pod(self):
        """Propagates Prefect-specific labels to the pod in the job manifest."""
        current_pod_metadata = self.job_manifest["spec"]["template"].get("metadata", {})
        current_pod_labels = current_pod_metadata.get("labels", {})
        all_labels = {**current_pod_labels, **self.labels}

        current_pod_metadata["labels"] = {
            _slugify_label_key(k): _slugify_label_value(v)
            for k, v in all_labels.items()
        }
        self.job_manifest["spec"]["template"]["metadata"] = current_pod_metadata

    def _slugify_annotations(self):
        """Merges and slugifies annotation keys in the job manifest.

        Annotation keys follow the same rules as label keys, but annotation
        values are arbitrary strings so only keys are slugified.
        """
        all_annotations = {
            **self.job_manifest["metadata"].get("annotations", {}),
            **self.annotations,
        }
        self.job_manifest["metadata"]["annotations"] = {
            _slugify_label_key(k): v for k, v in all_annotations.items()
        }

    def _propagate_annotations_to_pod(self):
        """Propagates annotations to the pod in the job manifest.

        Unlike labels, there are no automatic base annotations, so we only
        touch pod metadata when the user actually provided annotations.
        """
        merged_annotations = self.job_manifest["metadata"].get("annotations", {})
        if not merged_annotations:
            return

        current_pod_metadata = self.job_manifest["spec"]["template"].get("metadata", {})
        current_pod_annotations = current_pod_metadata.get("annotations", {})
        all_annotations = {**current_pod_annotations, **merged_annotations}

        current_pod_metadata["annotations"] = all_annotations
        self.job_manifest["spec"]["template"]["metadata"] = current_pod_metadata


class KubernetesWorkerVariables(BaseVariables):
    """
    Default variables for the Kubernetes worker.

    The schema for this class is used to populate the `variables` section of the default
    base job template.
    """

    annotations: Dict[str, str] = Field(
        default_factory=dict,
        description="Annotations applied to Kubernetes jobs and pods created by the worker.",
    )
    namespace: str = Field(
        default="default", description="The Kubernetes namespace to create jobs within."
    )
    image: Optional[str] = Field(
        default=None,
        description="The image reference of a container image to use for created jobs. "
        "If not set, the latest Prefect image will be used.",
        examples=["docker.io/prefecthq/prefect:3-latest"],
    )
    service_account_name: Optional[str] = Field(
        default=None,
        description="The Kubernetes service account to use for job creation.",
    )
    image_pull_policy: Literal["IfNotPresent", "Always", "Never"] = Field(
        default=KubernetesImagePullPolicy.IF_NOT_PRESENT,
        description="The Kubernetes image pull policy to use for job containers.",
    )
    backoff_limit: int = Field(
        default=0,
        ge=0,
        title="Backoff Limit",
        description=(
            "The number of times Kubernetes will retry a job after pod eviction. "
            "If set to 0, Prefect will reschedule the flow run when the pod is evicted "
            "unless PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR is already set. "
            "Otherwise Kubernetes retries the Job and Prefect relinquishes the run."
        ),
    )
    finished_job_ttl: Optional[int] = Field(
        default=None,
        title="Finished Job TTL",
        description="The number of seconds to retain jobs after completion. If set, "
        "finished jobs will be cleaned up by Kubernetes after the given delay. If not "
        "set, jobs will be retained indefinitely.",
    )
    job_watch_timeout_seconds: Optional[int] = Field(
        default=None,
        description=(
            "Number of seconds to wait for each event emitted by a job before "
            "timing out. If not set, the worker will wait for each event indefinitely."
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
    cluster_config: Optional[KubernetesClusterConfig] = Field(
        default=None,
        description="The Kubernetes cluster config to use for job creation.",
    )
    registry_credentials: Optional[KubernetesRegistryCredentials] = Field(
        default=None,
        description=(
            "Credentials for pulling the job's image from a private registry, such as "
            "a DockerRegistryCredentials block. The worker stores them in an image "
            "pull Secret for each job, which is deleted together with the job. The "
            "worker needs permission to create, patch and delete Secrets."
        ),
    )
    cpu_request: Optional[str] = Field(
        default=None,
        title="CPU Request",
        description=(
            "The CPU resource request for the Kubernetes job container. Uses"
            " Kubernetes resource quantity format (e.g. '500m' for half a CPU,"
            " '2' for two CPUs). If not provided, no CPU request is configured."
        ),
    )
    cpu_limit: Optional[str] = Field(
        default=None,
        title="CPU Limit",
        description=(
            "The CPU resource limit for the Kubernetes job container. Uses"
            " Kubernetes resource quantity format (e.g. '500m' for half a CPU,"
            " '2' for two CPUs). If not provided, no CPU limit is configured."
        ),
    )
    memory_request: Optional[str] = Field(
        default=None,
        title="Memory Request",
        description=(
            "The memory resource request for the Kubernetes job container. Uses"
            " Kubernetes resource quantity format (e.g. '128Mi', '1Gi'). If not"
            " provided, no memory request is configured."
        ),
    )
    memory_limit: Optional[str] = Field(
        default=None,
        title="Memory Limit",
        description=(
            "The memory resource limit for the Kubernetes job container. Uses"
            " Kubernetes resource quantity format (e.g. '128Mi', '1Gi'). If not"
            " provided, no memory limit is configured."
        ),
    )


class KubernetesWorkerResult(BaseWorkerResult):
    """Contains information about the final state of a completed process"""


class KubernetesWorker(
    BaseWorker[
        "KubernetesWorkerJobConfiguration",
        "KubernetesWorkerVariables",
        "KubernetesWorkerResult",
    ]
):
    """Prefect worker that executes flow runs within Kubernetes Jobs."""

    type: str = "kubernetes"
    job_configuration = KubernetesWorkerJobConfiguration
    job_configuration_variables = KubernetesWorkerVariables
    _description = (
        "Execute flow runs within jobs scheduled on a Kubernetes cluster. Requires a "
        "Kubernetes cluster."
    )
    _display_name = "Kubernetes"
    _documentation_url = "https://www.prefect.io/docs/integrations/prefect-kubernetes"
    _logo_url = "https://raw.githubusercontent.com/PrefectHQ/prefect/420d0d6a78bb6df1fc18bcf188fdad43c1d22ea9/assets/block-logos/kubernetes.png"  # noqa

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._created_secrets: dict[
            tuple[str, str], KubernetesWorkerJobConfiguration
        ] = {}

    async def _initiate_run(
        self,
        flow_run: "FlowRun",
        configuration: KubernetesWorkerJobConfiguration,
    ) -> None:
        """
        Creates a Kubernetes job to start flow run execution. This method does not
        wait for the job to complete.

        Args:
            flow_run: The flow run to execute
            configuration: The configuration to use when executing the flow run
        """
        logger = self.get_flow_run_logger(flow_run)
        async with self._get_configured_kubernetes_client(configuration) as client:
            logger.info("Creating Kubernetes job...")

            await self._create_job(configuration, client)

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: KubernetesWorkerJobConfiguration,
        task_status: anyio.abc.TaskStatus[int] | None = None,
    ) -> KubernetesWorkerResult:
        """
        Executes a flow run within a Kubernetes Job and waits for the flow run
        to complete.

        Args:
            flow_run: The flow run to execute
            configuration: The configuration to use when executing the flow run.
            task_status: The task status object for the current flow run. If provided,
                the task will be marked as started.

        Returns:
            KubernetesWorkerResult: A result object containing information about the
                final state of the flow run
        """
        logger = self.get_flow_run_logger(flow_run)
        async with self._get_configured_kubernetes_client(configuration) as client:
            logger.info("Creating Kubernetes job...")

            job = await self._create_job(configuration, client)

            assert job, "Job should be created"
            logger.info(
                "Kubernetes job '%s' created in namespace '%s'",
                job.metadata.name,
                job.metadata.namespace,
            )
            pid = f"{job.metadata.namespace}:{job.metadata.name}"
            # Indicate that the job has started
            if task_status is not None:
                task_status.started(pid)

            return KubernetesWorkerResult(identifier=pid, status_code=0)

    async def teardown(self, *exc_info: Any):
        await super().teardown(*exc_info)

        await self._clean_up_created_secrets()

    async def _clean_up_created_secrets(self):
        """Deletes any secrets created during the worker's operation."""
        for key, configuration in self._created_secrets.items():
            async with self._get_configured_kubernetes_client(configuration) as client:
                v1 = CoreV1Api(client)
                result = await v1.delete_namespaced_secret(
                    name=key[0],
                    namespace=key[1],
                )

                if isinstance(result, Exception):
                    self._logger.warning(
                        "Failed to delete created secret with exception: %s", result
                    )

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: KubernetesWorkerJobConfiguration,
        grace_seconds: int = 30,
    ) -> None:
        """
        Kill a Kubernetes job by deleting it.

        Args:
            infrastructure_pid: The infrastructure identifier in format "namespace:job_name".
            configuration: The job configuration used to connect to the cluster.
            grace_seconds: Time to allow for graceful shutdown before force killing.

        Raises:
            InfrastructureNotFound: If the job doesn't exist.
            InfrastructureNotAvailable: If unable to connect to the cluster.
        """
        # Parse infrastructure_pid (format: "namespace:job_name")
        parts = infrastructure_pid.split(":")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid infrastructure_pid format: {infrastructure_pid!r}. "
                "Expected format: 'namespace:job_name'"
            )
        job_namespace, job_name = parts

        async with self._get_configured_kubernetes_client(configuration) as client:
            batch_client = BatchV1Api(api_client=client)

            try:
                await batch_client.delete_namespaced_job(
                    name=job_name,
                    namespace=job_namespace,
                    grace_period_seconds=grace_seconds,
                    propagation_policy="Foreground",
                )
                self._logger.info(
                    f"Deleted Kubernetes job {job_name!r} in namespace {job_namespace!r}"
                )
            except ApiException as exc:
                if exc.status == 404:
                    raise InfrastructureNotFound(
                        f"Kubernetes job {job_name!r} not found in namespace {job_namespace!r}"
                    )
                raise

    @asynccontextmanager
    async def _get_configured_kubernetes_client(
        self, configuration: KubernetesWorkerJobConfiguration
    ) -> AsyncGenerator["ApiClient", None]:
        """
        Returns a configured Kubernetes client.
        """
        client = None
        settings = KubernetesSettings()

        if configuration.cluster_config:
            config_dict = configuration.cluster_config.config
            context = configuration.cluster_config.context_name
            client = await config.new_client_from_config_dict(
                config_dict=config_dict,
                context=context,
            )
        else:
            # Try to load in-cluster configuration
            try:
                config.load_incluster_config()
                client = ApiClient()
            except config.ConfigException:
                # If in-cluster config fails, load the local kubeconfig
                client = await config.new_client_from_config()

        if settings.worker.add_tcp_keepalive:
            client.rest_client.pool_manager._request_class = KeepAliveClientRequest

        try:
            yield client
        finally:
            await client.close()

    async def _replace_api_key_with_secret(
        self,
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
        secret_name: str | None = None,
        secret_key: str | None = None,
    ):
        """Replaces the PREFECT_API_KEY environment variable with a Kubernetes secret"""
        api_key = configuration.get_environment_variable_value("PREFECT_API_KEY")
        if api_key and not secret_name:
            secret_name = f"prefect-{_slugify_name(self.name)}-api-key"
            secret = await self._upsert_secret(
                name=secret_name,
                value=api_key,
                namespace=configuration.namespace,
                client=client,
            )
            # Store configuration so that we can delete the secret when the worker shuts
            # down
            self._created_secrets[(secret.metadata.name, secret.metadata.namespace)] = (
                configuration
            )
            secret_key = "value"
        if secret_name and secret_key:
            await self._replace_env_variable_with_secret(
                env_variable_name="PREFECT_API_KEY",
                configuration=configuration,
                secret_name=secret_name,
                secret_key=secret_key,
            )

    async def _replace_env_variable_with_secret(
        self,
        env_variable_name: str,
        configuration: KubernetesWorkerJobConfiguration,
        secret_name: str,
        secret_key: str,
    ):
        """Replaces the an environment variable with a Kubernetes secret"""
        manifest_env: list[dict[str, Any]] = configuration.job_manifest["spec"][
            "template"
        ]["spec"]["containers"][0].get("env")
        if secret_name and secret_key:
            if not secret_key:
                secret_key = "value"
            new_api_env_entry = {
                "name": env_variable_name,
                "valueFrom": {"secretKeyRef": {"name": secret_name, "key": secret_key}},
            }
            manifest_env = [
                entry if entry.get("name") != env_variable_name else new_api_env_entry
                for entry in manifest_env
            ]
            configuration.job_manifest["spec"]["template"]["spec"]["containers"][0][
                "env"
            ] = manifest_env

    async def _create_job(
        self, configuration: KubernetesWorkerJobConfiguration, client: "ApiClient"
    ) -> "V1Job":
        """
        Creates a Kubernetes job from a job manifest.
        """
        settings = KubernetesSettings()
        if settings.worker.api_key_secret_name:
            await self._replace_api_key_with_secret(
                configuration=configuration,
                client=client,
                secret_name=settings.worker.api_key_secret_name,
                secret_key=settings.worker.api_key_secret_key,
            )
        elif settings.worker.create_secret_for_api_key:
            await self._replace_api_key_with_secret(
                configuration=configuration, client=client
            )

        if (
            settings.worker.api_auth_string_secret_name
            and settings.worker.api_auth_string_secret_key
        ):
            await self._replace_env_variable_with_secret(
                env_variable_name="PREFECT_API_AUTH_STRING",
                configuration=configuration,
                secret_name=settings.worker.api_auth_string_secret_name,
                secret_key=settings.worker.api_auth_string_secret_key,
            )
        else:
            if configuration.get_environment_variable_value("PREFECT_API_AUTH_STRING"):
                self._logger.warning(
                    "PREFECT_API_AUTH_STRING is set, but no secret name or key is provided. "
                    "The API auth string will be stored in the Kubernetes job manifest."
                    "This is not recommended and may be removed in a future version. "
                    "Please store the API auth string in a Kubernetes secret and "
                    "provide the secret name and key with the `PREFECT_INTEGRATIONS_KUBERNETES_WORKER_API_AUTH_STRING_SECRET_NAME` "
                    "and `PREFECT_INTEGRATIONS_KUBERNETES_WORKER_API_AUTH_STRING_SECRET_KEY` environment variables."
                )

        # Secrets created for this job only, owned by the Job once it exists.
        job_secret_names: list[str] = []
        if settings.worker.store_env_as_secret:
            env_secret_name = await self._store_env_as_secret(
                configuration=configuration, client=client
            )
            if env_secret_name:
                job_secret_names.append(env_secret_name)

        try:
            if configuration.registry_credentials:
                await self._create_image_pull_secret(
                    configuration=configuration,
                    client=client,
                    job_secret_names=job_secret_names,
                )

            batch_client = BatchV1Api(client)
            retry_settings = settings.worker.create_job_retry
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(retry_settings.max_retries),
                wait=wait_fixed(retry_settings.delay_seconds)
                + wait_random(
                    retry_settings.jitter_min_seconds,
                    retry_settings.jitter_max_seconds,
                ),
                reraise=True,
            ):
                with attempt:
                    job = await batch_client.create_namespaced_job(
                        configuration.namespace,
                        configuration.job_manifest,
                    )
        except BaseException as exc:
            # Also on transport errors and cancellation, after which Jobs may exist
            await self._settle_job_secrets_in_time(
                job_secret_names, None, configuration, client
            )
            if not isinstance(exc, ApiException):
                raise

            # Parse the reason and message from the response if feasible
            message = ""
            if exc.reason:
                message += ": " + exc.reason
            if exc.body and "message" in (body := json.loads(exc.body)):
                message += ": " + body["message"]

            if hint := self._get_k8s_error_hint(exc, configuration.namespace):
                message += f". Hint: {hint}"

            raise InfrastructureError(
                f"Unable to create Kubernetes job{message}"
            ) from exc

        await self._settle_job_secrets_in_time(
            job_secret_names, job, configuration, client
        )
        return job

    async def _set_job_secret_owners(
        self,
        secret_names: list[str],
        jobs: list["V1Job"],
        namespace: str,
        client: "ApiClient",
    ) -> None:
        """Makes the Jobs the owners of the per-job Secrets."""
        for secret_name in secret_names:
            try:
                await self._set_secret_owner_reference(
                    secret_name=secret_name,
                    namespace=namespace,
                    jobs=jobs,
                    client=client,
                )
            except Exception:
                self._logger.warning(
                    "Failed to set owner reference on secret %r; "
                    "it will not be automatically cleaned up when the Job is deleted",
                    secret_name,
                )

    async def _settle_job_secrets_in_time(
        self,
        secret_names: list[str],
        created_job: "V1Job | None",
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
    ) -> None:
        """Settles the per-job Secrets, shielded from cancellation and bounded."""
        with anyio.move_on_after(
            JOB_SECRET_CLEANUP_TIMEOUT_SECONDS, shield=True
        ) as scope:
            await self._settle_job_secrets(
                secret_names, created_job, configuration, client
            )
        if scope.cancelled_caught:
            self._logger.warning(
                "Timed out after %ss settling secrets %r; they may lack an owner "
                "and outlive their Job.",
                JOB_SECRET_CLEANUP_TIMEOUT_SECONDS,
                secret_names,
            )

    async def _settle_job_secrets(
        self,
        secret_names: list[str],
        created_job: "V1Job | None",
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
    ) -> None:
        """Gives the per-job Secrets an owner, or deletes them if no Job needs them.

        A lost response can create a Job that the worker never sees, or that a
        retry then reports as a conflict. Every Job of the flow run that
        references the Secrets therefore becomes an owner, so the Secrets live
        as long as any of them, and are deleted only if there is none.
        """
        if not secret_names:
            return
        namespace = configuration.namespace
        if created_job is not None:
            # The known owner first, in case looking up the others runs out of time
            await self._set_job_secret_owners(
                secret_names, [created_job], namespace, client
            )
        try:
            jobs = await self._jobs_referencing_secrets(
                secret_names, configuration, client
            )
        except Exception:
            if created_job is None:
                self._logger.warning(
                    "Could not check whether the Job was created; keeping secrets %r, "
                    "which a created Job may need.",
                    secret_names,
                )
            return
        if created_job is not None:
            if all(job.metadata.uid == created_job.metadata.uid for job in jobs):
                return
            jobs = [
                created_job,
                *(job for job in jobs if job.metadata.uid != created_job.metadata.uid),
            ]
        if jobs:
            await self._set_job_secret_owners(secret_names, jobs, namespace, client)
            return

        for secret_name in secret_names:
            try:
                await CoreV1Api(client).delete_namespaced_secret(
                    name=secret_name, namespace=namespace
                )
            except ApiException as delete_exc:
                # The Secret's creation may have failed as well
                if delete_exc.status != 404:
                    self._logger.warning(
                        "Failed to clean up secret %r after Job creation failure",
                        secret_name,
                    )
            except Exception:
                self._logger.warning(
                    "Failed to clean up secret %r after Job creation failure",
                    secret_name,
                )

    async def _jobs_referencing_secrets(
        self,
        secret_names: list[str],
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
    ) -> list["V1Job"]:
        """The flow run's Jobs whose manifest references any of the Secrets."""
        labels = configuration.job_manifest["metadata"].get("labels") or {}
        flow_run_id = labels.get("prefect.io/flow-run-id")
        if not flow_run_id:
            return []
        job_list = await BatchV1Api(client).list_namespaced_job(
            namespace=configuration.namespace,
            label_selector=f"prefect.io/flow-run-id={flow_run_id}",
        )
        # Secret names end in a random suffix, so a match is the submitted Job
        return [
            job
            for job in job_list.items
            if self._pod_secret_names(job) & set(secret_names)
        ]

    @staticmethod
    def _pod_secret_names(job: "V1Job") -> set[str]:
        """Names of the Secrets the Job's pod pulls images or env vars from."""
        pod_spec = job.spec.template.spec
        names = {ref.name for ref in pod_spec.image_pull_secrets or []}
        for container in pod_spec.containers or []:
            names.update(
                source.secret_ref.name
                for source in container.env_from or []
                if source.secret_ref
            )
        return names

    async def _service_account_image_pull_secrets(
        self,
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
    ) -> list[dict[str, str]]:
        """The `imagePullSecrets` of the pod's ServiceAccount.

        Kubernetes adds them only to pods that list none, so they must be listed
        explicitly once the pod gets its own.
        """
        pod_spec = configuration.job_manifest["spec"]["template"]["spec"]
        name = (
            pod_spec.get("serviceAccountName")
            or pod_spec.get("serviceAccount")
            or "default"
        )
        try:
            service_account = await CoreV1Api(client).read_namespaced_service_account(
                name=name, namespace=configuration.namespace
            )
        except ApiException as exc:
            # Only a missing permission or account; anything else may be transient
            if exc.status not in (403, 404):
                raise
            self._logger.warning(
                "Could not read the image pull secrets of ServiceAccount %r (%s); "
                "the pod only gets the pull Secret for its registry credentials.",
                name,
                exc.reason,
            )
            return []
        return [{"name": ref.name} for ref in service_account.image_pull_secrets or []]

    async def _create_image_pull_secret(
        self,
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
        job_secret_names: list[str],
    ) -> None:
        """Stores the job's registry credentials in a per-job image pull Secret.

        Adds the Secret to `job_secret_names` while this call may have created
        it, and to the pod's `imagePullSecrets`, after any the job manifest lists
        or, if it lists none, after those of the pod's ServiceAccount.
        """
        credentials = configuration.registry_credentials
        assert credentials is not None, "Expected registry credentials to be set"

        pod_spec = configuration.job_manifest["spec"]["template"]["spec"]
        pull_secrets = list(pod_spec.get("imagePullSecrets") or [])
        if not pull_secrets:
            pull_secrets = await self._service_account_image_pull_secrets(
                configuration, client
            )

        secret_name = self._job_secret_name(configuration, "pull")
        secret = V1Secret(
            api_version="v1",
            kind="Secret",
            type="kubernetes.io/dockerconfigjson",
            metadata=V1ObjectMeta(
                name=secret_name,
                namespace=configuration.namespace,
                labels=self._job_secret_labels(
                    configuration.job_manifest["metadata"].get("labels", {})
                ),
            ),
            # Secret string_data is automatically base64-encoded by the K8s API
            string_data={".dockerconfigjson": credentials.to_docker_config_json()},
        )
        # Tracked before the request, which may create the Secret and still fail
        job_secret_names.append(secret_name)
        try:
            await CoreV1Api(client).create_namespaced_secret(
                namespace=configuration.namespace, body=secret
            )
        except ApiException as exc:
            # Rejected, so not created here; a 409 means another job's Secret
            if exc.status is not None and exc.status < 500:
                job_secret_names.remove(secret_name)
            raise

        pod_spec["imagePullSecrets"] = [*pull_secrets, {"name": secret_name}]

    @staticmethod
    def _job_secret_name(
        configuration: KubernetesWorkerJobConfiguration, kind: str
    ) -> str:
        """A unique name for a per-job Secret, based on the job's name."""
        generate_name = configuration.job_manifest["metadata"].get(
            "generateName", "prefect-job-"
        )
        return f"{generate_name.rstrip('-')}-{kind}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _job_secret_labels(job_labels: dict[str, str] | None) -> dict[str, str]:
        """Labels for a Secret created for one job, with its flow-run-id label."""
        secret_labels = {"app.kubernetes.io/managed-by": "prefect"}
        if job_labels:
            # Propagate the flow-run-id label for auditability
            flow_run_id = job_labels.get("prefect.io/flow-run-id")
            if flow_run_id:
                secret_labels["prefect.io/flow-run-id"] = flow_run_id
        return secret_labels

    async def _store_env_as_secret(
        self,
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
    ) -> str | None:
        """Moves plaintext env vars from the Job manifest into a per-job Secret.

        Returns the name of the created Secret, or None if there were no
        plaintext env vars to store.
        """
        container = configuration.job_manifest["spec"]["template"]["spec"][
            "containers"
        ][0]
        manifest_env: list[dict[str, Any]] = container.get("env", [])

        # Separate plain-value entries from valueFrom entries
        plain_env: dict[str, str] = {}
        value_from_entries: list[dict[str, Any]] = []
        for entry in manifest_env:
            if "valueFrom" in entry:
                value_from_entries.append(entry)
            elif "value" in entry and entry.get("name"):
                plain_env[entry["name"]] = entry["value"]

        if not plain_env:
            return None

        # Derive secret name from the Job's generateName
        generate_name = configuration.job_manifest["metadata"].get(
            "generateName", "prefect-job-"
        )
        # Strip trailing hyphen for cleaner naming
        base_name = generate_name.rstrip("-")
        short_id = uuid.uuid4().hex[:8]
        secret_name = f"{base_name}-env-{short_id}"

        # Create the Secret
        secret = await self._create_env_secret(
            name=secret_name,
            env_vars=plain_env,
            namespace=configuration.namespace,
            client=client,
            labels=configuration.job_manifest["metadata"].get("labels", {}),
        )

        # Rewrite the manifest: keep only valueFrom entries in env
        container["env"] = value_from_entries

        # Append envFrom.secretRef (preserving any existing envFrom entries)
        existing_env_from: list[dict[str, Any]] = container.get("envFrom", [])
        container["envFrom"] = [
            *existing_env_from,
            {"secretRef": {"name": secret.metadata.name}},
        ]

        return secret.metadata.name

    async def _create_env_secret(
        self,
        name: str,
        env_vars: dict[str, str],
        namespace: str,
        client: "ApiClient",
        labels: dict[str, str] | None = None,
    ) -> "V1Secret":
        """Creates a Kubernetes Secret containing the given env var key-value pairs."""
        core_client = CoreV1Api(client)
        metadata = V1ObjectMeta(
            name=name,
            namespace=namespace,
            labels=self._job_secret_labels(labels),
        )
        # Secret string_data is automatically base64-encoded by the K8s API
        secret = V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=metadata,
            string_data=env_vars,
        )
        return await core_client.create_namespaced_secret(
            namespace=namespace, body=secret
        )

    @retry(
        # A rejection won't change; server errors and lost connections may
        retry=retry_if_exception(
            lambda exc: (
                not (
                    isinstance(exc, ApiException)
                    and exc.status is not None
                    and exc.status < 500
                )
            )
        ),
        stop=stop_after_attempt(3),
        wait=wait_random(0, 1),
        reraise=True,
    )
    async def _set_secret_owner_reference(
        self,
        secret_name: str,
        namespace: str,
        jobs: list["V1Job"],
        client: "ApiClient",
    ) -> None:
        """Patches the Secret to set the Jobs as its owners for automatic GC."""
        core_client = CoreV1Api(client)
        body = {
            "metadata": {
                "ownerReferences": [
                    {
                        "apiVersion": "batch/v1",
                        "kind": "Job",
                        "name": job.metadata.name,
                        "uid": job.metadata.uid,
                    }
                    for job in jobs
                ]
            }
        }
        await core_client.patch_namespaced_secret(
            name=secret_name,
            namespace=namespace,
            body=body,
        )

    @staticmethod
    def _get_k8s_error_hint(
        exc: "kubernetes_asyncio.client.exceptions.ApiException",
        namespace: str,
    ) -> str | None:
        status = exc.status
        reason = (exc.reason or "").lower()
        raw_body = exc.body or ""
        body_str = (
            raw_body.decode("utf-8", errors="replace")
            if isinstance(raw_body, bytes)
            else raw_body
        ).lower()

        if "quota" in body_str or "exceeded" in body_str:
            return "Check the resource quotas for the namespace and ensure the job does not exceed them."

        if status == 403 or "forbidden" in reason:
            return "Check that your service account has the required RBAC permissions for this operation."

        if status == 404 and namespace and namespace.lower() in body_str:
            return f"Verify that the namespace '{namespace}' exists in the cluster."

        return None

    @retry(
        retry=retry_if_exception(
            lambda exc: isinstance(exc, ApiException) and exc.status == 409
        ),
        stop=stop_after_attempt(3),
        wait=wait_random(0, 1),
        reraise=True,
    )
    async def _upsert_secret(
        self, name: str, value: str, namespace: str, client: "ApiClient"
    ):
        encoded_value = base64.b64encode(value.encode("utf-8")).decode("utf-8")
        core_client = CoreV1Api(client)
        try:
            # Get the current version of the Secret and update it with the
            # new value
            current_secret = await core_client.read_namespaced_secret(
                name=name, namespace=namespace
            )
            if current_secret.data == {"value": encoded_value}:
                return current_secret
            current_secret.data = {"value": encoded_value}
            secret = await core_client.replace_namespaced_secret(
                name=name, namespace=namespace, body=current_secret
            )
        except ApiException as exc:
            if exc.status != 404:
                raise
            # Create the secret if it doesn't already exist
            metadata = V1ObjectMeta(name=name, namespace=namespace)
            secret = V1Secret(
                api_version="v1",
                kind="Secret",
                metadata=metadata,
                data={"value": encoded_value},
            )
            secret = await core_client.create_namespaced_secret(
                namespace=namespace, body=secret
            )
        return secret

    @asynccontextmanager
    async def _get_batch_client(
        self, client: "ApiClient"
    ) -> AsyncGenerator["BatchV1Api", None]:
        """
        Context manager for retrieving a Kubernetes batch client.
        """
        try:
            yield BatchV1Api(api_client=client)
        finally:
            await client.close()

    async def __aenter__(self):
        if KubernetesSettings().observer.enabled:
            start_observer()
        return await super().__aenter__()

    async def __aexit__(self, *exc_info: Any):
        try:
            await super().__aexit__(*exc_info)
        finally:
            # Need to run after the runs task group exits
            if KubernetesSettings().observer.enabled:
                stop_observer()

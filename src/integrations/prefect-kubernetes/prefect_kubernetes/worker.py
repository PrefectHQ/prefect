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
checkout out the [Prefect docs](https://docs.prefect.io/concepts/work-pools/).
"""

from __future__ import annotations

import base64
import enum
import json
import shlex
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
from pydantic import Field, field_validator, model_validator
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random
from typing_extensions import Literal, Self

import prefect
from prefect.client.schemas.objects import Flow as APIFlow
from prefect.exceptions import (
    InfrastructureError,
)
from prefect.utilities.dockerutils import get_prefect_image_name
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
    from prefect.client.schemas.objects import FlowRun, WorkPool
    from prefect.client.schemas.responses import DeploymentResponse

# Captures flow return type
R = TypeVar("R")


MAX_ATTEMPTS = 3
RETRY_MIN_DELAY_SECONDS = 1
RETRY_MIN_DELAY_JITTER_SECONDS = 0
RETRY_MAX_DELAY_JITTER_SECONDS = 3


def _get_default_job_manifest_template() -> Dict[str, Any]:
    """Returns the default job manifest template used by the Kubernetes worker."""
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
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

    namespace: str = Field(default="default")
    job_manifest: Dict[str, Any] = Field(
        json_schema_extra=dict(template=_get_default_job_manifest_template())
    )
    cluster_config: Optional[KubernetesClusterConfig] = Field(default=None)
    job_watch_timeout_seconds: Optional[int] = Field(default=None)
    pod_watch_timeout_seconds: int = Field(default=60)
    stream_output: bool = Field(default=True)

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
        return {
            "prefect.io/flow-run-id": str(flow_run.id),
            "prefect.io/flow-run-name": flow_run.name,
            "prefect.io/version": _slugify_label_value(
                prefect.__version__.split("+")[0]
            ),
        }

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

        super().prepare_for_flow_run(flow_run, deployment, flow, work_pool, worker_name)

        self._configure_eviction_handling()
        self._update_prefect_api_url_if_local_server()

        # Restore any special env vars with valueFrom before populating the manifest
        if special_env_vars:
            # Convert dict env back to list format
            env_list = [{"name": k, "value": v} for k, v in self.env.items()]
            # Add special env vars back in
            env_list.extend(special_env_vars)
            self.env = env_list

        self._populate_env_in_manifest()
        self._slugify_labels()
        self._populate_image_if_not_present()
        self._populate_command_if_not_present()
        self._populate_generate_name_if_not_present()
        self._propagate_labels_to_pod()

    def _configure_eviction_handling(self):
        """
        Configures eviction handling for the job pod. Needs to run before

        If `backoffLimit` is set to 0, we'll tell the Runner to reschedule
        its flow run when it receives a SIGTERM.

        If `backoffLimit` is set to a positive number, we'll ensure that the
        reschedule SIGTERM handling is not set. Having both a `backoffLimit` and
        reschedule handling set can cause duplicate flow run execution.
        """
        # If backoffLimit is set to 0, we'll tell the Runner to reschedule
        # its flow run when it receives a SIGTERM.
        if self.job_manifest["spec"].get("backoffLimit") == 0:
            if isinstance(self.env, dict):
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
        # Otherwise, we'll ensure that the reschedule SIGTERM handling is not set.
        else:
            if isinstance(self.env, dict):
                self.env.pop("PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR", None)
            elif any(
                v.get("name") == "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR"
                for v in self.env
            ):
                self.env = [
                    v
                    for v in self.env
                    if v.get("name") != "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR"
                ]

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
            self.job_manifest["spec"]["template"]["spec"]["containers"][0]["env"] = [
                *transformed_env,
                *template_env,
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
                ] = shlex.split(self._base_flow_run_command())
            elif isinstance(command, str):
                self.job_manifest["spec"]["template"]["spec"]["containers"][0][
                    "args"
                ] = shlex.split(command)
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


class KubernetesWorkerVariables(BaseVariables):
    """
    Default variables for the Kubernetes worker.

    The schema for this class is used to populate the `variables` section of the default
    base job template.
    """

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
            "If set to 0, Prefect will reschedule the flow run when the pod is evicted."
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
    _documentation_url = "https://docs.prefect.io/integrations/prefect-kubernetes"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/2d0b896006ad463b49c28aaac14f31e00e32cfab-250x250.png"  # noqa

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
            task_status: The task status object for the current flow run. If provided,
                the task will be marked as started.
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

    @retry(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_fixed(RETRY_MIN_DELAY_SECONDS)
        + wait_random(
            RETRY_MIN_DELAY_JITTER_SECONDS,
            RETRY_MAX_DELAY_JITTER_SECONDS,
        ),
        reraise=True,
    )
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

        try:
            batch_client = BatchV1Api(client)
            job = await batch_client.create_namespaced_job(
                configuration.namespace,
                configuration.job_manifest,
            )
        except kubernetes_asyncio.client.exceptions.ApiException as exc:
            # Parse the reason and message from the response if feasible
            message = ""
            if exc.reason:
                message += ": " + exc.reason
            if exc.body and "message" in (body := json.loads(exc.body)):
                message += ": " + body["message"]

            raise InfrastructureError(
                f"Unable to create Kubernetes job{message}"
            ) from exc

        return job

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
        start_observer()
        return await super().__aenter__()

    async def __aexit__(self, *exc_info: Any):
        try:
            await super().__aexit__(*exc_info)
        finally:
            # Need to run after the runs task group exits
            stop_observer()

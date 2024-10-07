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
`PREFECT_KUBERNETES_WORKER_STORE_PREFECT_API_IN_SECRET` environment variable before
starting your worker:

```bash
export PREFECT_KUBERNETES_WORKER_STORE_PREFECT_API_IN_SECRET="true"
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

import asyncio
import base64
import enum
import json
import logging
import os
import shlex
from contextlib import asynccontextmanager
from datetime import datetime
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

import aiohttp
import anyio.abc
import kubernetes_asyncio
from kubernetes_asyncio import config
from kubernetes_asyncio.client import (
    ApiClient,
    BatchV1Api,
    CoreV1Api,
    V1Job,
    V1Pod,
)
from kubernetes_asyncio.client.exceptions import ApiException
from kubernetes_asyncio.client.models import (
    CoreV1Event,
    CoreV1EventList,
    V1ObjectMeta,
    V1Secret,
)
from pydantic import Field, field_validator, model_validator
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random
from typing_extensions import Literal, Self

import prefect
from prefect.client.schemas.objects import FlowRun
from prefect.exceptions import (
    InfrastructureError,
)
from prefect.server.schemas.core import Flow
from prefect.server.schemas.responses import DeploymentResponse
from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.utilities.pydantic import JsonPatch
from prefect.utilities.templating import find_placeholders
from prefect.utilities.timeout import timeout_async
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)
from prefect_kubernetes.credentials import KubernetesClusterConfig
from prefect_kubernetes.events import KubernetesEventsReplicator
from prefect_kubernetes.utilities import (
    KeepAliveClientRequest,
    _slugify_label_key,
    _slugify_label_value,
    _slugify_name,
)

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
            "backoffLimit": 0,
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

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: Optional["DeploymentResponse"] = None,
        flow: Optional["Flow"] = None,
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
        """

        super().prepare_for_flow_run(flow_run, deployment, flow)
        # Update configuration env and job manifest env
        self._update_prefect_api_url_if_local_server()
        self._populate_env_in_manifest()
        # Update labels in job manifest
        self._slugify_labels()
        # Add defaults to job manifest if necessary
        self._populate_image_if_not_present()
        self._populate_command_if_not_present()
        self._populate_generate_name_if_not_present()

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
        transformed_env = [{"name": k, "value": v} for k, v in self.env.items()]

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
            self.job_manifest["spec"]["template"]["spec"]["containers"][0][
                "env"
            ] = transformed_env

    def _update_prefect_api_url_if_local_server(self):
        """If the API URL has been set by the base environment rather than the by the
        user, update the value to ensure connectivity when using a bridge network by
        updating local connections to use the internal host
        """
        if self.env.get("PREFECT_API_URL") and self._api_dns_name:
            self.env["PREFECT_API_URL"] = (
                self.env["PREFECT_API_URL"]
                .replace("localhost", self._api_dns_name)
                .replace("127.0.0.1", self._api_dns_name)
            )

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


class KubernetesWorker(BaseWorker):
    """Prefect worker that executes flow runs within Kubernetes Jobs."""

    type: str = "kubernetes"
    job_configuration = KubernetesWorkerJobConfiguration
    job_configuration_variables = KubernetesWorkerVariables
    _description = (
        "Execute flow runs within jobs scheduled on a Kubernetes cluster. Requires a "
        "Kubernetes cluster."
    )
    _display_name = "Kubernetes"
    _documentation_url = "https://prefecthq.github.io/prefect-kubernetes/worker/"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/2d0b896006ad463b49c28aaac14f31e00e32cfab-250x250.png"  # noqa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._created_secrets = {}

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: KubernetesWorkerJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
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

            pid = await self._get_infrastructure_pid(job, client)
            # Indicate that the job has started
            if task_status is not None:
                task_status.started(pid)

            # Monitor the job until completion
            events_replicator = KubernetesEventsReplicator(
                client=client,
                job_name=job.metadata.name,
                namespace=configuration.namespace,
                worker_resource=self._event_resource(),
                related_resources=self._event_related_resources(
                    configuration=configuration
                ),
                timeout_seconds=configuration.pod_watch_timeout_seconds,
            )
            async with events_replicator:
                status_code = await self._watch_job(
                    logger, job.metadata.name, configuration, client
                )

            return KubernetesWorkerResult(identifier=pid, status_code=status_code)

    async def teardown(self, *exc_info):
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

        if os.environ.get(
            "PREFECT_KUBERNETES_WORKER_ADD_TCP_KEEPALIVE", "TRUE"
        ).strip().lower() in ("true", "1"):
            client.rest_client.pool_manager._request_class = KeepAliveClientRequest

        try:
            yield client
        finally:
            await client.close()

    async def _replace_api_key_with_secret(
        self, configuration: KubernetesWorkerJobConfiguration, client: "ApiClient"
    ):
        """Replaces the PREFECT_API_KEY environment variable with a Kubernetes secret"""
        manifest_env = configuration.job_manifest["spec"]["template"]["spec"][
            "containers"
        ][0].get("env")
        manifest_api_key_env = next(
            (
                env_entry
                for env_entry in manifest_env
                if env_entry.get("name") == "PREFECT_API_KEY"
            ),
            {},
        )
        api_key = manifest_api_key_env.get("value")
        if api_key:
            secret_name = f"prefect-{_slugify_name(self.name)}-api-key"
            secret = await self._upsert_secret(
                name=secret_name,
                value=api_key,
                namespace=configuration.namespace,
                client=client,
            )
            # Store configuration so that we can delete the secret when the worker shuts
            # down
            self._created_secrets[
                (secret.metadata.name, secret.metadata.namespace)
            ] = configuration
            new_api_env_entry = {
                "name": "PREFECT_API_KEY",
                "valueFrom": {"secretKeyRef": {"name": secret_name, "key": "value"}},
            }
            manifest_env = [
                entry if entry.get("name") != "PREFECT_API_KEY" else new_api_env_entry
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
        if os.environ.get(
            "PREFECT_KUBERNETES_WORKER_STORE_PREFECT_API_IN_SECRET", ""
        ).strip().lower() in ("true", "1"):
            await self._replace_api_key_with_secret(
                configuration=configuration, client=client
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

    async def _get_infrastructure_pid(self, job: "V1Job", client: "ApiClient") -> str:
        """
        Generates a Kubernetes infrastructure PID.

        The PID is in the format: "<cluster uid>:<namespace>:<job name>".
        """
        cluster_uid = await self._get_cluster_uid(client)
        pid = f"{cluster_uid}:{job.metadata.namespace}:{job.metadata.name}"
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

    async def _get_cluster_uid(self, client: "ApiClient") -> str:
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
        v1 = CoreV1Api(client)
        namespace = await v1.read_namespace("kube-system")
        cluster_uid = namespace.metadata.uid
        return cluster_uid

    async def _stream_job_logs(
        self,
        logger: logging.Logger,
        pod_name: str,
        job_name: str,
        configuration: KubernetesWorkerJobConfiguration,
        client,
    ):
        timeout = aiohttp.ClientTimeout(total=None)
        core_client = CoreV1Api(client)

        logs = await core_client.read_namespaced_pod_log(
            pod_name,
            configuration.namespace,
            follow=True,
            _preload_content=False,
            container="prefect-job",
            _request_timeout=timeout,
        )
        try:
            async for line in logs.content:
                if not line:
                    break
                print(line.decode().rstrip())
        except Exception:
            logger.warning(
                (
                    "Error occurred while streaming logs - "
                    "Job will continue to run but logs will "
                    "no longer be streamed to stdout."
                ),
                exc_info=True,
            )

    async def _job_events(
        self,
        batch_client: BatchV1Api,
        job_name: str,
        namespace: str,
        watch_kwargs: dict,
    ):
        """
        Stream job events.

        Pick up from the current resource version returned by the API
        in the case of a 410.

        See https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-changes  # noqa
        """
        watch = kubernetes_asyncio.watch.Watch()
        resource_version = None
        async with watch:
            while True:
                try:
                    async for event in watch.stream(
                        func=batch_client.list_namespaced_job,
                        namespace=namespace,
                        field_selector=f"metadata.name={job_name}",
                        **watch_kwargs,
                    ):
                        yield event
                except ApiException as e:
                    if e.status == 410:
                        job_list = await batch_client.list_namespaced_job(
                            namespace=namespace,
                            field_selector=f"metadata.name={job_name}",
                        )

                        resource_version = job_list.metadata.resource_version
                        watch_kwargs["resource_version"] = resource_version
                    else:
                        raise

    async def _monitor_job_events(self, batch_client, job_name, logger, configuration):
        job = await batch_client.read_namespaced_job(
            name=job_name, namespace=configuration.namespace
        )
        completed = job.status.completion_time is not None
        watch_kwargs = (
            {"timeout_seconds": configuration.job_watch_timeout_seconds}
            if configuration.job_watch_timeout_seconds
            else {}
        )

        while not completed:
            async for event in self._job_events(
                batch_client,
                job_name,
                configuration.namespace,
                watch_kwargs,
            ):
                if event["type"] == "DELETED":
                    logger.error(f"Job {job_name!r}: Job has been deleted.")
                    completed = True
                elif event["object"].status.completion_time:
                    if not event["object"].status.succeeded:
                        # Job failed, exit while loop and return pod exit code
                        logger.error(f"Job {job_name!r}: Job failed.")
                    completed = True
                # Check if the job has reached its backoff limit
                # and stop watching if it has
                elif (
                    event["object"].spec.backoff_limit is not None
                    and event["object"].status.failed is not None
                    and event["object"].status.failed
                    > event["object"].spec.backoff_limit
                ):
                    logger.error(f"Job {job_name!r}: Job reached backoff limit.")
                    completed = True
                # If the job has no backoff limit, check if it has failed
                # and stop watching if it has
                elif (
                    not event["object"].spec.backoff_limit
                    and event["object"].status.failed
                ):
                    completed = True
                if completed:
                    break

    async def _watch_job(
        self,
        logger: logging.Logger,
        job_name: str,
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
    ) -> int:
        """
        Watch a job.

        Return the final status code of the first container.
        """

        logger.debug(f"Job {job_name!r}: Monitoring job...")

        job = await self._get_job(logger, job_name, configuration, client)
        if not job:
            return -1

        pod = await self._get_job_pod(logger, job_name, configuration, client)
        if not pod:
            return -1

        # Create a list of tasks to run concurrently
        async with self._get_batch_client(client) as batch_client:
            tasks = [
                self._monitor_job_events(
                    batch_client,
                    job_name,
                    logger,
                    configuration,
                )
            ]
            try:
                with timeout_async(seconds=configuration.job_watch_timeout_seconds):
                    if configuration.stream_output:
                        tasks.append(
                            self._stream_job_logs(
                                logger,
                                pod.metadata.name,
                                job_name,
                                configuration,
                                client,
                            )
                        )

                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    if any(isinstance(result, Exception) for result in results):
                        for result in results:
                            if isinstance(result, Exception):
                                logger.error(
                                    f"Error during task execution: {result}",
                                    exc_info=True,
                                )
            except TimeoutError:
                logger.error(
                    f"Job {job_name!r}: Job did not complete within "
                    f"timeout of {configuration.job_watch_timeout_seconds}s."
                )
                return -1

            core_client = CoreV1Api(client)
            # Get all pods for the job
            pods = await core_client.list_namespaced_pod(
                namespace=configuration.namespace, label_selector=f"job-name={job_name}"
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
            logger.error(f"Job {job_name!r}: No pods found for job.")
            return -1
        # In some cases, such as spot instance evictions, the pod will be forcibly
        # terminated and not report a status correctly.
        elif (
            first_container_status.state is None
            or first_container_status.state.terminated is None
            or first_container_status.state.terminated.exit_code is None
        ):
            logger.error(
                f"Could not determine exit code for {job_name!r}."
                "Exit code will be reported as -1."
                f"First container status info did not report an exit code."
                f"First container info: {first_container_status}."
            )
            return -1

        return first_container_status.state.terminated.exit_code

    async def _get_job(
        self,
        logger: logging.Logger,
        job_id: str,
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
    ) -> Optional["V1Job"]:
        """Get a Kubernetes job by id."""

        try:
            batch_client = BatchV1Api(client)
            job = await batch_client.read_namespaced_job(
                name=job_id, namespace=configuration.namespace
            )
        except kubernetes_asyncio.client.exceptions.ApiException:
            logger.error(f"Job {job_id!r} was removed.", exc_info=True)
            return None
        return job

    async def _get_job_pod(
        self,
        logger: logging.Logger,
        job_name: str,
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
    ) -> Optional["V1Pod"]:
        """Get the first running pod for a job."""

        watch = kubernetes_asyncio.watch.Watch()
        logger.info(f"Job {job_name!r}: Starting watch for pod start...")
        last_phase = None
        last_pod_name: Optional[str] = None
        core_client = CoreV1Api(client)
        async with watch:
            async for event in watch.stream(
                func=core_client.list_namespaced_pod,
                namespace=configuration.namespace,
                label_selector=f"job-name={job_name}",
                timeout_seconds=configuration.pod_watch_timeout_seconds,
            ):
                pod: V1Pod = event["object"]
                last_pod_name = pod.metadata.name
                logger.info(f"Job {job_name!r}: Pod {last_pod_name!r} has started.")
                phase = pod.status.phase
                if phase != last_phase:
                    logger.info(f"Job {job_name!r}: Pod has status {phase!r}.")

                if phase != "Pending":
                    return pod

                last_phase = phase
            # If we've gotten here, we never found the Pod that was created for the flow run
            # Job, so let's inspect the situation and log what we can find.  It's possible
            # that the Job ran into scheduling constraints it couldn't satisfy, like
            # memory/CPU requests, or a volume that wasn't available, or a node with an
            # available GPU.
            logger.error(f"Job {job_name!r}: Pod never started.")
            await self._log_recent_events(
                logger, job_name, last_pod_name, configuration, client
            )

    async def _log_recent_events(
        self,
        logger: logging.Logger,
        job_name: str,
        pod_name: Optional[str],
        configuration: KubernetesWorkerJobConfiguration,
        client: "ApiClient",
    ) -> None:
        """Look for reasons why a Job may not have been able to schedule a Pod, or why
        a Pod may not have been able to start and log them to the provided logger."""

        def best_event_time(event: CoreV1Event) -> datetime:
            """Choose the best timestamp from a Kubernetes event"""
            return event.event_time or event.last_timestamp

        def log_event(event: CoreV1Event):
            """Log an event in one of a few formats to the provided logger"""
            if event.count and event.count > 1:
                logger.info(
                    "%s event %r (%s times) at %s: %s",
                    event.involved_object.kind,
                    event.reason,
                    event.count,
                    best_event_time(event),
                    event.message,
                )
            else:
                logger.info(
                    "%s event %r at %s: %s",
                    event.involved_object.kind,
                    event.reason,
                    best_event_time(event),
                    event.message,
                )

        core_client = CoreV1Api(client)

        events: CoreV1EventList = await core_client.list_namespaced_event(
            configuration.namespace
        )

        event: CoreV1Event
        for event in sorted(events.items, key=best_event_time):
            if (
                event.involved_object.api_version == "batch/v1"
                and event.involved_object.kind == "Job"
                and event.involved_object.namespace == configuration.namespace
                and event.involved_object.name == job_name
            ):
                log_event(event)

            if (
                pod_name
                and event.involved_object.api_version == "v1"
                and event.involved_object.kind == "Pod"
                and event.involved_object.namespace == configuration.namespace
                and event.involved_object.name == pod_name
            ):
                log_event(event)

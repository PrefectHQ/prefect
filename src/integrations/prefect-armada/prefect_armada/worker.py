"""

Module containing the Armada worker used for executing flow runs as Armada jobs.

To start an Armada worker, run the following command:

```bash
prefect worker start --pool 'my-work-pool' --type armada
```

Replace `my-work-pool` with the name of the work pool you want the worker
to poll for flow runs.

### Connecting to Armada

The worker connects to the Armada server's gRPC endpoint. The address can be set
on the work pool itself with the `armada_host`, `armada_port`, and
`armada_disable_ssl` variables, which are editable in the Prefect UI when
creating or editing an Armada work pool. Armada clusters that serve gRPC without
TLS - which is how the armada-operator's quickstart is configured - need
`armada_disable_ssl` set, or the worker's TLS handshake fails with
`WRONG_VERSION_NUMBER`.

A server whose certificate is privately issued, by an internal or cluster-local
CA, needs the issuing CA supplied with `armada_root_certificates_path`, a path
on the worker's host; gRPC's default roots only trust publicly-issued
certificates. gRPC matches that certificate's Subject Alternative Name against
`armada_host`, so a certificate issued for an in-cluster service name fails when
the worker dials `localhost` unless `grpc.ssl_target_name_override` is set in an
`ArmadaClusterConfig`'s `channel_options`. Armada does not support mutual TLS,
so a client certificate has no role here; authenticate with a token or basic
auth on an `ArmadaCredentials` block.

When none is set, and the work pool does not reference an
`ArmadaClusterConfig` or `ArmadaCredentials` block, connection details are read
from the environment:

```bash
export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_HOST="armada.example.com"
export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_PORT="50051"
export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_DISABLE_SSL="true"
prefect worker start --pool 'my-work-pool' --type armada
```

The `ARMADA_SERVER` and `ARMADA_PORT` environment variables used by Armada's own
tooling are also honored.

### Reaching the Prefect API from flow-run pods

Flow runs execute as pods inside the Armada cluster and inherit the worker's
`PREFECT_API_URL`, so that address has to be routable from the cluster. A worker
pointed at a Prefect server on `localhost` hands each pod an address that
resolves to the pod itself; set the `api_dns_name` work pool variable to an
address the API is reachable at from inside the cluster - for a kind cluster,
the gateway of its Docker network - and bind the server to it:

```bash
prefect server start --host 0.0.0.0
```

The worker warns when it is about to hand a job a local API address with no
`api_dns_name` set.

### Using a custom Armada job template

The default template used for Armada job submissions looks like this:
```yaml
---
priority: "{{ priority }}"
namespace: "{{ namespace }}"
labels: "{{ labels }}"
annotations: "{{ annotations }}"
podSpec:
  restartPolicy: Never
  serviceAccountName: "{{ service_account_name }}"
  containers:
  - name: prefect-job
    image: "{{ image }}"
    imagePullPolicy: "{{ image_pull_policy }}"
    args: "{{ command }}"
    env: "{{ env }}"
```

Each value enclosed in `{{ }}` is a placeholder that will be replaced with
a value at runtime. The values that can be used as placeholders are defined
by the `variables` schema defined in the base job template.

The default job template and available variables can be customized on a work
pool by work pool basis. These customizations can be made via the Prefect UI
when creating or editing a work pool.

For example, if you wanted to require a node label for an Armada work pool you
could update the job template to look like this:

```yaml
---
priority: "{{ priority }}"
namespace: "{{ namespace }}"
labels: "{{ labels }}"
annotations: "{{ annotations }}"
requiredNodeLabels:
  node-pool: "{{ node_pool }}"
podSpec:
  restartPolicy: Never
  containers:
  - name: prefect-job
    image: "{{ image }}"
    args: "{{ command }}"
    env: "{{ env }}"
```

The job template is an Armada `JobSubmitRequestItem` in dictionary form, so any
field Armada accepts on a job submission can be templated, including `ingress`,
`services`, and `requiredNodeLabels`.

For more information about work pools and workers,
checkout out the [Prefect docs](https://docs.prefect.io/concepts/work-pools/).
"""

from __future__ import annotations

import enum
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypeVar,
)

import anyio
import anyio.abc
import grpc
from armada_client.asyncio_client import ArmadaAsyncIOClient
from jsonpatch import JsonPatch
from pydantic import Field, field_validator, model_validator
from tenacity import AsyncRetrying, stop_after_attempt, wait_fixed, wait_random
from typing_extensions import Self

import prefect
from prefect.client.schemas.objects import Flow as APIFlow
from prefect.exceptions import (
    InfrastructureError,
    InfrastructureNotFound,
)
from prefect.logging.loggers import get_logger
from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.utilities.processutils import command_from_string
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)
from prefect_armada.credentials import ArmadaClusterConfig, ArmadaCredentials
from prefect_armada.exceptions import rpc_details, rpc_status_code
from prefect_armada.observer import observe_job_set, start_observer, stop_observer
from prefect_armada.settings import ArmadaSettings
from prefect_armada.utilities import (
    _slugify_label_key,
    _slugify_label_value,
    _slugify_name,
    coerce_job_request_items,
    format_job_pid,
    parse_job_pid,
)

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.objects import FlowRun, WorkPool
    from prefect.client.schemas.responses import DeploymentResponse

# Captures flow return type
R = TypeVar("R")

# The annotation Armada uses to associate a job with a resource in an external
# system. Armada indexes it so jobs can be looked up without their job ID.
EXTERNAL_JOB_URI_FIELD = "externalJobUri"

# Hosts in a Prefect API URL that a job's pod cannot reach the worker's API at:
# the loopback names resolve to the pod itself, and `0.0.0.0` is only an address
# to bind to, not one to connect to.
_LOCAL_API_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")

# How long the worker waits on Armada when checking its queue exists at startup.
_QUEUE_CHECK_TIMEOUT_SECONDS = 30

logger: logging.Logger = get_logger("prefect_armada.worker")


def _get_default_job_manifest_template() -> dict[str, Any]:
    """Returns the default job manifest template used by the Armada worker."""
    return {
        "priority": "{{ priority }}",
        "namespace": "{{ namespace }}",
        "labels": "{{ labels }}",
        "annotations": "{{ annotations }}",
        "podSpec": {
            "restartPolicy": "Never",
            "serviceAccountName": "{{ service_account_name }}",
            "containers": [
                {
                    "name": "prefect-job",
                    "image": "{{ image }}",
                    "imagePullPolicy": "{{ image_pull_policy }}",
                    "args": "{{ command }}",
                    "env": "{{ env }}",
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
        },
    }


def _get_base_job_manifest() -> dict[str, Any]:
    """Returns a base job manifest to use for manifest validation."""
    return {
        "labels": {},
        "annotations": {},
        "podSpec": {
            "restartPolicy": "Never",
            "containers": [
                {
                    "name": "prefect-job",
                }
            ],
        },
    }


class ArmadaImagePullPolicy(enum.Enum):
    """Enum representing the image pull policy options for an Armada job."""

    IF_NOT_PRESENT = "IfNotPresent"
    ALWAYS = "Always"
    NEVER = "Never"


class ArmadaWorkerJobConfiguration(BaseJobConfiguration):
    """
    Configuration class used by the Armada worker.

    An instance of this class is passed to the Armada worker's `run` method
    for each flow run. It contains all of the information necessary to execute
    the flow run as an Armada job.

    Attributes:
        name: The name to give to created Armada jobs.
        command: The command executed in created Armada jobs to kick off
            flow run execution.
        env: The environment variables to set in created Armada jobs.
        labels: The labels to set on created Armada jobs.
        annotations: The annotations to set on created Armada jobs.
        queue: The Armada queue to submit jobs to.
        job_set_id: The Armada job set to submit jobs to.
        namespace: The Kubernetes namespace Armada should run jobs in.
        job_manifest: The Armada job request used to submit jobs.
        armada_host: The hostname or IP address of the Armada server.
        armada_port: The port of the Armada server.
        armada_disable_ssl: Whether to connect to the Armada server without TLS.
        armada_root_certificates_path: Path to a PEM file of root certificates
            verifying the Armada server's TLS certificate.
        api_dns_name: The address the Prefect API is reachable at from inside the
            cluster, substituted for a local address in jobs' `PREFECT_API_URL`.
        cluster_config: The Armada cluster configuration to connect with.
        credentials: The Armada credentials to authenticate with.
        job_watch_timeout_seconds: The number of seconds to wait for the job to
            complete before timing out. If `None`, the observer will watch the
            job indefinitely.
        stream_output: Whether or not to stream the job's output.
    """

    annotations: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Annotations applied to infrastructure created by the worker using "
            "this job configuration."
        ),
    )
    queue: str = Field(default="prefect")
    job_set_id: str | None = Field(default=None)
    namespace: str = Field(default="default")
    job_manifest: dict[str, Any] = Field(
        json_schema_extra={"template": _get_default_job_manifest_template()}
    )
    armada_host: str | None = Field(default=None)
    armada_port: int | None = Field(default=None)
    armada_disable_ssl: bool | None = Field(default=None)
    armada_root_certificates_path: str | None = Field(default=None)
    api_dns_name: str | None = Field(default=None)
    cluster_config: ArmadaClusterConfig | None = Field(default=None)
    credentials: ArmadaCredentials | None = Field(default=None)
    job_watch_timeout_seconds: int | None = Field(default=None)
    stream_output: bool = Field(default=True)

    env: dict[str, str | None] | list[dict[str, Any]] = Field(default_factory=dict)

    @field_validator("job_manifest", mode="before")
    @classmethod
    def _normalize_manifest_keys(cls, value: Any) -> Any:
        """
        Accepts the pod spec under either the protobuf field name (`pod_spec`)
        or its JSON name (`podSpec`), which is what Armada's own examples and
        the default template use.
        """
        if isinstance(value, dict) and "pod_spec" in value and "podSpec" not in value:
            value = {**value}
            value["podSpec"] = value.pop("pod_spec")
        return value

    @model_validator(mode="after")
    def _validate_job_manifest(self) -> Self:
        """
        Validates the job manifest by ensuring the presence of required fields
        and checking for compatible values.
        """
        job_manifest = self.job_manifest

        # Ensure labels and annotations are present
        if "labels" not in job_manifest:
            job_manifest["labels"] = {}
        if "annotations" not in job_manifest:
            job_manifest["annotations"] = {}

        # Ensure namespace is present
        if not job_manifest.get("namespace"):
            job_manifest["namespace"] = self.namespace

        # Check if the job includes all required components
        patch = JsonPatch.from_diff(job_manifest, _get_base_job_manifest())
        missing_paths = sorted([op["path"] for op in patch if op["op"] == "add"])
        if missing_paths:
            raise ValueError(
                "Job is missing required attributes at the following paths: "
                f"{', '.join(missing_paths)}"
            )

        # Check if the job has compatible values
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
        """Coerces environment variable values to strings."""
        if isinstance(v, list):
            return v
        return {k: str(v) if v is not None else None for k, v in v.items()}

    @staticmethod
    def _base_flow_run_labels(flow_run: FlowRun) -> dict[str, str]:
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
    def _base_flow_labels(flow: APIFlow | None) -> dict[str, str]:
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
        deployment: DeploymentResponse | None,
    ) -> dict[str, str]:
        """
        Generate a dictionary of labels for a deployment, including standard
        app.kubernetes.io labels.
        """
        labels = BaseJobConfiguration._base_deployment_labels(deployment)
        if deployment is not None:
            labels["app.kubernetes.io/name"] = _slugify_label_value(deployment.name)
        return labels

    @property
    def container(self) -> dict[str, Any]:
        """The first container in the job manifest's pod spec."""
        return self.job_manifest["podSpec"]["containers"][0]

    def get_environment_variable_value(self, name: str) -> str | None:
        """
        Returns the value of an environment variable from the job manifest.
        """
        manifest_env: list[dict[str, Any]] = self.container.get("env", [])
        if not isinstance(manifest_env, list):
            return None
        return next(
            (
                env_entry.get("value")
                for env_entry in manifest_env
                if env_entry.get("name") == name
            ),
            None,
        )

    def get_credentials(self) -> ArmadaCredentials:
        """
        Returns the credentials used to connect to Armada.

        A `credentials` block takes precedence over a `cluster_config` block, and
        a `cluster_config` set on the job configuration is used when the
        credentials block does not carry one of its own. When neither is set,
        connection details are read from the current environment.

        `armada_host`, `armada_port`, `armada_disable_ssl`, and
        `armada_root_certificates_path` override the host, port, and TLS settings
        of whichever cluster config is used, so a work pool can point at an
        Armada server without configuring a block.
        """
        credentials = self._get_block_credentials()

        overrides: dict[str, Any] = {}
        if self.armada_host:
            overrides["host"] = self.armada_host
        if self.armada_port:
            overrides["port"] = self.armada_port
        if self.armada_disable_ssl is not None:
            overrides["disable_ssl"] = self.armada_disable_ssl
        if self.armada_root_certificates_path:
            # The inline PEM on a cluster config takes precedence when resolving,
            # so it is cleared for this override to take effect.
            overrides["root_certificates"] = None
            overrides["root_certificates_path"] = Path(
                self.armada_root_certificates_path
            )
        if not overrides:
            return credentials

        cluster_config = credentials.get_cluster_config().model_copy(update=overrides)
        return credentials.model_copy(update={"cluster_config": cluster_config})

    def _get_block_credentials(self) -> ArmadaCredentials:
        """Returns the credentials described by this configuration's blocks."""
        if self.credentials:
            if self.credentials.cluster_config is None and self.cluster_config:
                return self.credentials.model_copy(
                    update={"cluster_config": self.cluster_config}
                )
            return self.credentials
        if self.cluster_config:
            return ArmadaCredentials(cluster_config=self.cluster_config)
        return ArmadaCredentials()

    def prepare_for_flow_run(
        self,
        flow_run: FlowRun,
        deployment: DeploymentResponse | None = None,
        flow: APIFlow | None = None,
        work_pool: WorkPool | None = None,
        worker_name: str | None = None,
        worker_id: UUID | None = None,
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

        self._populate_env_in_manifest()
        self._slugify_labels()
        self._slugify_annotations()
        self._populate_image_if_not_present()
        self._populate_command_if_not_present()
        self._populate_namespace_if_not_present()
        self._populate_external_job_uri(flow_run)
        self._populate_job_set_id_if_not_present(flow_run)

    def _populate_env_in_manifest(self):
        """
        Populates environment variables in the job manifest.

        When `env` is templated as a variable in the job manifest it comes in as a
        dictionary. We need to convert it to a list of dictionaries to conform to
        the pod spec schema Armada expects.

        This function also handles the case where the user has removed the
        `{{ env }}` placeholder and hard coded a value for `env`. In this case, we
        need to prepend our environment variables to the list to ensure Prefect
        setting propagation.
        """
        # Handle both dictionary and list formats for environment variables
        if isinstance(self.env, dict):
            transformed_env = [{"name": k, "value": v} for k, v in self.env.items()]
        else:
            # If env is already a list (pod spec format), use it directly
            transformed_env = self.env

        template_env = self.container.get("env")

        # If the user has removed the `{{ env }}` placeholder and hard coded a
        # value for `env`, we need to prepend our environment variables to the
        # list to ensure Prefect setting propagation.
        if isinstance(template_env, list):
            transformed_env_names = {env["name"] for env in transformed_env}

            # Filter out any env vars from template_env that are duplicates
            # (these came from template rendering of work pool variables)
            unique_template_env = [
                env
                for env in template_env
                if env.get("name") not in transformed_env_names
            ]

            self.container["env"] = [*transformed_env, *unique_template_env]
        else:
            self.container["env"] = transformed_env

    def _update_prefect_api_url_if_local_server(self):
        """Rewrites a local Prefect API address into one jobs can reach.

        The worker propagates its own `PREFECT_API_URL` to the jobs it submits,
        but a worker talking to a server on `localhost` hands the job an address
        that, inside a pod, resolves to the pod itself. `api_dns_name` replaces
        the local host with an address routable from the cluster.
        """
        if isinstance(self.env, dict):
            api_url = self.env.get("PREFECT_API_URL")
            if api_url and (rewritten := self._rewrite_local_api_url(api_url)):
                self.env["PREFECT_API_URL"] = rewritten
        else:
            # Handle list format
            for env_var in self.env:
                if env_var.get("name") != "PREFECT_API_URL":
                    continue
                value = env_var.get("value")
                if value and (rewritten := self._rewrite_local_api_url(value)):
                    env_var["value"] = rewritten

    def _rewrite_local_api_url(self, api_url: str) -> str | None:
        """Points a local API URL at `api_dns_name`.

        Returns the rewritten URL, or `None` when the URL needs no rewriting.
        Warns when a local URL is about to be handed to a job with no
        `api_dns_name` to replace it, since the job cannot reach it.
        """
        if not any(host in api_url for host in _LOCAL_API_HOSTS):
            return None

        if not self.api_dns_name:
            logger.warning(
                "Flow runs will be given PREFECT_API_URL=%s, which inside an "
                "Armada job resolves to the job's own pod rather than to the "
                "Prefect API, so they will fail to connect. Set the "
                "`api_dns_name` job variable on the work pool to an address the "
                "Prefect API is reachable at from inside the cluster, and make "
                "sure the API is bound to that address.",
                api_url,
            )
            return None

        for host in _LOCAL_API_HOSTS:
            api_url = api_url.replace(host, self.api_dns_name)
        return api_url

    def _slugify_labels(self):
        """Slugifies the labels in the job manifest."""
        all_labels = {**self.job_manifest.get("labels", {}), **self.labels}
        self.job_manifest["labels"] = {
            _slugify_label_key(k): _slugify_label_value(v)
            for k, v in all_labels.items()
        }

    def _slugify_annotations(self):
        """Merges and slugifies annotation keys in the job manifest.

        Annotation keys follow the same rules as label keys, but annotation
        values are arbitrary strings so only keys are slugified.

        Prefect metadata is written to annotations as well as labels because
        Armada carries annotations through to its event stream, which is how the
        observer associates an Armada job with a flow run.
        """
        all_annotations = {
            **self.job_manifest.get("annotations", {}),
            **self.labels,
            **self.annotations,
        }
        self.job_manifest["annotations"] = {
            _slugify_label_key(k): v for k, v in all_annotations.items()
        }

    def _populate_image_if_not_present(self):
        """Ensures that the image is present in the job manifest. Populates the image
        with the default Prefect image if it is not present."""
        try:
            if not self.container.get("image"):
                self.container["image"] = get_prefect_image_name()
        except KeyError:
            raise ValueError(
                "Unable to verify image due to invalid job manifest template."
            )

    def _populate_command_if_not_present(self):
        """
        Ensures that the command is present in the job manifest. Populates the
        command with `prefect flow-run execute` if a command is not present.
        """
        try:
            command = self.container.get("args")
            if command is None:
                self.container["args"] = command_from_string(
                    self._base_flow_run_command()
                )
            elif isinstance(command, str):
                self.container["args"] = command_from_string(command)
            elif not isinstance(command, list):
                raise ValueError(
                    "Invalid job manifest template: 'command' must be a string or list."
                )
        except KeyError:
            raise ValueError(
                "Unable to verify command due to invalid job manifest template."
            )

    def _populate_namespace_if_not_present(self):
        """Ensures that a namespace is present in the job manifest.

        Armada rejects job submissions without a namespace, and template
        rendering leaves the field empty when a work pool does not set one.
        """
        if not self.job_manifest.get("namespace"):
            self.job_manifest["namespace"] = self.namespace or "default"

    def _populate_external_job_uri(self, flow_run: FlowRun):
        """Records the flow run as the job's external owner.

        Armada indexes `externalJobUri`, so this allows the Armada job for a flow
        run to be found without knowing its Armada job ID.
        """
        if not self.job_manifest.get(EXTERNAL_JOB_URI_FIELD):
            self.job_manifest[EXTERNAL_JOB_URI_FIELD] = (
                f"prefect://flow-run/{flow_run.id}"
            )

    def _populate_job_set_id_if_not_present(self, flow_run: FlowRun):
        """Ensures that a job set ID is set for this flow run.

        Each flow run gets its own job set so that the observer's watch of the
        job set's event stream can end once the flow run's job is finished.
        """
        if not self.job_set_id:
            name = _slugify_name(self.name or "prefect-job") or "prefect-job"
            self.job_set_id = f"{name}-{flow_run.id}"


class ArmadaWorkerVariables(BaseVariables):
    """
    Default variables for the Armada worker.

    The schema for this class is used to populate the `variables` section of the
    default base job template.
    """

    armada_host: str | None = Field(
        default=None,
        title="Armada Server Host",
        description=(
            "The hostname or IP address of the Armada server's gRPC endpoint. "
            "Overrides the host of the cluster config used for job submission. "
            "If not set here or on a block, the host is read from the worker's "
            "environment, defaulting to 'localhost'."
        ),
        examples=["armada.example.com"],
    )
    armada_port: int | None = Field(
        default=None,
        title="Armada Server Port",
        ge=1,
        le=65535,
        description=(
            "The port of the Armada server's gRPC endpoint. Overrides the port "
            "of the cluster config used for job submission. If not set here or "
            "on a block, the port is read from the worker's environment, "
            "defaulting to 50051. (If you started the Armada cluster via the "
            "armada-operator, it is probably 30002)"
        ),
        examples=[50051],
    )
    armada_disable_ssl: bool | None = Field(
        default=None,
        title="Disable TLS",
        description=(
            "Whether to connect to the Armada server without TLS. Overrides the "
            "TLS setting of the cluster config used for job submission. If not "
            "set here or on a block, it is read from the worker's environment, "
            "defaulting to using TLS. Armada clusters started by the "
            "armada-operator serve gRPC without TLS, so they need this enabled."
        ),
        examples=[True],
    )
    armada_root_certificates_path: str | None = Field(
        default=None,
        title="TLS Root Certificates Path",
        description=(
            "Path to a PEM file holding the root certificates that verify the "
            "Armada server's TLS certificate, for a cluster serving gRPC with a "
            "privately-issued certificate. The file is read by the worker, so it "
            "must exist on the worker's host. Overrides the root certificates of "
            "the cluster config used for job submission. Ignored when TLS is "
            "disabled. If not set here or on a block, gRPC's default roots are "
            "used, which only trust publicly-issued certificates."
        ),
        examples=["/etc/prefect/armada/ca.crt"],
    )
    api_dns_name: str | None = Field(
        default=None,
        title="Prefect API Address for Jobs",
        description=(
            "The hostname or IP address the Prefect API is reachable at from "
            "inside the cluster. Jobs inherit the worker's PREFECT_API_URL, so a "
            "worker pointed at a Prefect server on localhost hands each job an "
            "address that resolves to the job's own pod; this value replaces the "
            "local host in that URL. Only needed for a Prefect API that is local "
            "to the worker, and the API must be bound to the address given here."
            "(If you started the Armada cluster via the armada-operator, it is "
            "probably 172.18.0.1)"
        ),
        examples=["172.18.0.1"],
    )
    annotations: dict[str, str] = Field(
        default_factory=dict,
        description="Annotations applied to Armada jobs created by the worker.",
    )
    queue: str = Field(
        default="prefect",
        description="The Armada queue to submit jobs to. The queue must already "
        "exist and the worker's credentials must be permitted to submit to it.",
    )
    job_set_id: str | None = Field(
        default=None,
        title="Job Set ID",
        description="The Armada job set to submit jobs to. If not set, each flow "
        "run is submitted to its own job set.",
    )
    namespace: str = Field(
        default="default",
        description="The Kubernetes namespace Armada should run jobs in.",
    )
    priority: float = Field(
        default=1.0,
        ge=0,
        description="The Armada priority of created jobs. Lower values are "
        "scheduled first.",
    )
    image: str | None = Field(
        default=None,
        description="The image reference of a container image to use for created jobs. "
        "If not set, the latest Prefect image will be used.",
        examples=["docker.io/prefecthq/prefect:3-latest"],
    )
    service_account_name: str | None = Field(
        default=None,
        description="The Kubernetes service account to use for created jobs.",
    )
    image_pull_policy: Literal["IfNotPresent", "Always", "Never"] = Field(
        default=ArmadaImagePullPolicy.IF_NOT_PRESENT,
        description="The Kubernetes image pull policy to use for job containers.",
    )
    job_watch_timeout_seconds: int | None = Field(
        default=None,
        description=(
            "Number of seconds to wait for each event emitted by a job before "
            "timing out. If not set, the observer will watch each job indefinitely."
        ),
    )
    stream_output: bool = Field(
        default=True,
        description=(
            "If set, output will be streamed from the job to local standard output."
        ),
    )
    cluster_config: ArmadaClusterConfig | None = Field(
        default=None,
        description="The Armada cluster config to use for job submission.",
    )
    credentials: ArmadaCredentials | None = Field(
        default=None,
        description="The Armada credentials to use for job submission.",
    )
    cpu_request: str | None = Field(
        default=None,
        title="CPU Request",
        description=(
            "The CPU resource request for the job container. Uses Kubernetes"
            " resource quantity format (for example '500m' for half a CPU, '2'"
            " for two"
            " CPUs). If not provided, no CPU request is configured."
        ),
    )
    cpu_limit: str | None = Field(
        default=None,
        title="CPU Limit",
        description=(
            "The CPU resource limit for the job container. Uses Kubernetes"
            " resource quantity format (for example '500m' for half a CPU, '2'"
            " for two"
            " CPUs). If not provided, no CPU limit is configured."
        ),
    )
    memory_request: str | None = Field(
        default=None,
        title="Memory Request",
        description=(
            "The memory resource request for the job container. Uses Kubernetes"
            " resource quantity format (for example '128Mi', '1Gi'). If not"
            " provided, no"
            " memory request is configured."
        ),
    )
    memory_limit: str | None = Field(
        default=None,
        title="Memory Limit",
        description=(
            "The memory resource limit for the job container. Uses Kubernetes"
            " resource quantity format (for example '128Mi', '1Gi'). If not"
            " provided, no"
            " memory limit is configured."
        ),
    )


class ArmadaWorkerResult(BaseWorkerResult):
    """Contains information about the final state of a completed process"""


class ArmadaWorker(
    BaseWorker[
        "ArmadaWorkerJobConfiguration",
        "ArmadaWorkerVariables",
        "ArmadaWorkerResult",
    ]
):
    """Prefect worker that executes flow runs within Armada jobs."""

    type: str = "armada"
    job_configuration = ArmadaWorkerJobConfiguration
    job_configuration_variables = ArmadaWorkerVariables
    _description = (
        "Execute flow runs within jobs scheduled on an Armada cluster. Requires "
        "access to an Armada server."
    )
    _display_name = "Armada"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-armada"
    _logo_url = "https://raw.githubusercontent.com/armadaproject/armada/master/logo.svg"

    async def _initiate_run(
        self,
        flow_run: FlowRun,
        configuration: ArmadaWorkerJobConfiguration,
    ) -> None:
        """
        Submits an Armada job to start flow run execution. This method does not
        wait for the job to complete.

        Args:
            flow_run: The flow run to execute
            configuration: The configuration to use when executing the flow run
        """
        logger = self.get_flow_run_logger(flow_run)
        async with self._get_configured_armada_client(configuration) as client:
            logger.info("Submitting Armada job...")

            await self._submit_job(configuration, client)

    async def run(
        self,
        flow_run: FlowRun,
        configuration: ArmadaWorkerJobConfiguration,
        task_status: anyio.abc.TaskStatus[str] | None = None,
    ) -> ArmadaWorkerResult:
        """
        Executes a flow run within an Armada job.

        Args:
            flow_run: The flow run to execute
            configuration: The configuration to use when executing the flow run.
            task_status: The task status object for the current flow run. If provided,
                the task will be marked as started.

        Returns:
            ArmadaWorkerResult: A result object containing information about the
                final state of the flow run
        """
        logger = self.get_flow_run_logger(flow_run)
        async with self._get_configured_armada_client(configuration) as client:
            logger.info("Submitting Armada job...")

            job_id = await self._submit_job(configuration, client)

            job_set_id = configuration.job_set_id
            assert job_set_id, "Expected a job set ID to be set for the flow run"
            logger.info(
                "Armada job '%s' submitted to queue '%s' in job set '%s'",
                job_id,
                configuration.queue,
                job_set_id,
            )
            pid = format_job_pid(configuration.queue, job_set_id, job_id)
            # Indicate that the job has started
            if task_status is not None:
                task_status.started(pid)

            return ArmadaWorkerResult(identifier=pid, status_code=0)

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: ArmadaWorkerJobConfiguration,
        grace_seconds: int = 30,
    ) -> None:
        """
        Kill an Armada job by cancelling it.

        Args:
            infrastructure_pid: The infrastructure identifier in the format
                "queue:job_set_id:job_id".
            configuration: The job configuration used to connect to Armada.
            grace_seconds: Unused. Armada does not support a grace period when
                cancelling a job.

        Raises:
            InfrastructureNotFound: If the job doesn't exist.
        """
        queue, job_set_id, job_id = parse_job_pid(infrastructure_pid)

        async with self._get_configured_armada_client(configuration) as client:
            try:
                result = await client.cancel_jobs(
                    queue=queue,
                    job_set_id=job_set_id,
                    job_id=job_id,
                )
            except grpc.RpcError as exc:
                if rpc_status_code(exc) is grpc.StatusCode.NOT_FOUND:
                    raise InfrastructureNotFound(
                        f"Armada job {job_id!r} not found in queue {queue!r}"
                    ) from exc
                raise

            if not list(result.cancelled_ids):
                raise InfrastructureNotFound(
                    f"Armada job {job_id!r} in queue {queue!r} could not be "
                    "cancelled; it may have already reached a terminal state."
                )

            self._logger.info(
                f"Cancelled Armada job {job_id!r} in queue {queue!r}",
            )

    @asynccontextmanager
    async def _get_configured_armada_client(
        self, configuration: ArmadaWorkerJobConfiguration
    ) -> AsyncGenerator[ArmadaAsyncIOClient, None]:
        """
        Returns a configured Armada client.
        """
        credentials = configuration.get_credentials()
        async with credentials.get_client() as client:
            yield client

    async def _submit_job(
        self,
        configuration: ArmadaWorkerJobConfiguration,
        client: ArmadaAsyncIOClient,
    ) -> str:
        """
        Submits an Armada job from a job manifest and returns its job ID.
        """
        settings = ArmadaSettings()
        job_set_id = configuration.job_set_id
        assert job_set_id, "Expected a job set ID to be set for the flow run"

        job_request_items = coerce_job_request_items(configuration.job_manifest)

        try:
            retry_settings = settings.worker.submit_job_retry
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
                    response = await client.submit_jobs(
                        queue=configuration.queue,
                        job_set_id=job_set_id,
                        job_request_items=job_request_items,
                    )
        except grpc.RpcError as exc:
            message = ""
            if status_code := rpc_status_code(exc):
                message += ": " + status_code.name
            if details := rpc_details(exc):
                message += ": " + details
            if hint := self._get_armada_error_hint(exc, configuration.queue):
                message += f". Hint: {hint}"

            raise InfrastructureError(f"Unable to submit Armada job{message}") from exc

        if len(response.job_response_items) != 1:
            raise InfrastructureError(
                "Expected Armada to create exactly one job for this flow run, but "
                f"it reported {len(response.job_response_items)} jobs."
            )

        job_response = response.job_response_items[0]
        if job_response.error:
            raise InfrastructureError(
                f"Unable to submit Armada job: {job_response.error}"
            )

        if settings.observer.enabled:
            observe_job_set(
                credentials=configuration.get_credentials(),
                queue=configuration.queue,
                job_set_id=job_set_id,
            )

        return job_response.job_id

    @staticmethod
    def _get_armada_error_hint(exc: grpc.RpcError, queue: str) -> str | None:
        """Returns an actionable hint for a failed Armada submission, if any."""
        status_code = rpc_status_code(exc)
        details = rpc_details(exc).lower()

        if "requests and limits" in details:
            return (
                "Armada requires a container's resource requests to equal its "
                "limits; set matching values for the cpu and memory variables."
            )

        if "quota" in details or "exceeded" in details:
            return (
                "Check the resource limits for the queue and ensure the job does "
                "not exceed them."
            )

        if status_code is grpc.StatusCode.PERMISSION_DENIED:
            return (
                f"Check that the worker's credentials are permitted to submit to "
                f"queue {queue!r}."
            )

        if status_code is grpc.StatusCode.NOT_FOUND:
            return f"Verify that the queue {queue!r} exists in Armada."

        if status_code is grpc.StatusCode.UNAVAILABLE:
            return (
                "Verify that the Armada server is reachable and that the "
                "configured host, port, and TLS settings are correct."
            )

        if status_code is grpc.StatusCode.INVALID_ARGUMENT:
            return "Check the job template for this work pool for invalid values."

        return None

    async def _get_missing_queue(self) -> str | None:
        """Checks that the work pool's Armada queue exists.

        A missing queue otherwise goes unnoticed until a flow run is submitted,
        and the flow run sits in `Late` until then. Only the queue set on the
        work pool is checked; a deployment overriding `queue` is checked when
        its flow runs are submitted.

        Returns:
            The queue's name if Armada reports that it does not exist, or `None`
            otherwise, including when the check could not be completed.
        """
        if self._work_pool is None:
            self._logger.debug(
                "Work pool is not yet known; skipping the Armada queue check."
            )
            return None

        try:
            configuration = await self.job_configuration.from_template_and_values(
                base_job_template=self._work_pool.base_job_template,
                values={},
                client=self._client,
            )
        except Exception as exc:
            self._logger.warning(
                "Unable to read the work pool's job configuration; skipping the "
                "Armada queue check: %s",
                exc,
            )
            return None

        queue = configuration.queue
        try:
            with anyio.fail_after(_QUEUE_CHECK_TIMEOUT_SECONDS):
                async with self._get_configured_armada_client(configuration) as client:
                    await client.get_queue(name=queue)
        except grpc.RpcError as exc:
            if rpc_status_code(exc) is grpc.StatusCode.NOT_FOUND:
                return queue
            message = rpc_details(exc) or str(exc)
            if hint := self._get_armada_error_hint(exc, queue):
                message += f". Hint: {hint}"
            self._logger.warning(
                "Unable to verify that Armada queue %r exists: %s", queue, message
            )
        except TimeoutError:
            self._logger.warning(
                "Timed out after %s seconds verifying that Armada queue %r exists.",
                _QUEUE_CHECK_TIMEOUT_SECONDS,
                queue,
            )
        return None

    async def __aenter__(self):
        """Starts the Armada observer alongside the worker.

        Exits the process if the work pool's Armada queue does not exist, since
        every flow run the worker submits would be rejected.
        """
        if ArmadaSettings().observer.enabled:
            start_observer()
        try:
            await super().__aenter__()
        except BaseException:
            if ArmadaSettings().observer.enabled:
                stop_observer()
            raise

        if queue := await self._get_missing_queue():
            self._logger.error(
                "Armada queue %r, configured for work pool %r, does not exist. "
                "Create the queue in Armada (for example, `armadactl create "
                "queue %s`) or set the work pool's `queue` variable to an "
                "existing queue, then restart the worker.",
                queue,
                self._work_pool_name,
                queue,
            )
            await self.__aexit__(None, None, None)
            raise SystemExit(1)

        return self

    async def __aexit__(self, *exc_info: object):
        """Stops the Armada observer when the worker shuts down."""
        try:
            await super().__aexit__(*exc_info)
        finally:
            # Need to run after the runs task group exits
            if ArmadaSettings().observer.enabled:
                stop_observer()

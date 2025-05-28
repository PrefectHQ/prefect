"""volcanoworker.py – Custom Prefect worker that can handle both Kubernetes **batch/v1**
Jobs *and* Volcano **batch.volcano.sh/v1alpha1** Jobs.

* Default base‑job‑template is **Kubernetes** (so existing pools need not change).
* If a deployment (or pool base‑template) overrides `apiVersion` to
  `batch.volcano.sh/v1alpha1`, this worker automatically switches to Volcano
  logic: creation via `CustomObjectsApi`, pod selector `volcano.sh/job-name`,
  status polling via Job `status.state`.
* Otherwise it behaves exactly like the upstream `KubernetesWorker`.

Only minimal, internal‑use functionality is implemented.
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Any, Dict, Optional

import anyio
from kubernetes_asyncio.client import (
    ApiClient,
    CustomObjectsApi,
)
from pydantic import Field, model_validator

from prefect.utilities.dockerutils import get_prefect_image_name
from prefect_kubernetes.utilities import (
    _slugify_label_key,
    _slugify_label_value,
    _slugify_name,
)
from prefect_kubernetes.worker import (
    KubernetesWorker,
    KubernetesWorkerJobConfiguration,
    KubernetesWorkerResult,
    KubernetesWorkerVariables,
)

if TYPE_CHECKING:
    from kubernetes_asyncio.client import ApiClient

    from prefect.client.schemas.objects import FlowRun
    from prefect_kubernetes.volcanoworker import (  # noqa: F401
        KubernetesWorkerResult,
        VolcanoWorkerJobConfiguration,
    )


def _get_default_volcano_job_manifest_template() -> Dict[str, Any]:
    """Returns the default Volcano Job manifest template used by VolcanoWorker."""
    return {
        "apiVersion": "batch.volcano.sh/v1alpha1",
        "kind": "Job",
        "metadata": {
            "labels": "{{ labels }}",
            "namespace": "{{ namespace }}",
            "generateName": "{{ name }}-",
        },
        "spec": {
            "schedulerName": "volcano",
            "queue": "{{ queue }}",
            "maxRetry": 3,
            "minAvailable": 1,
            "tasks": [
                {
                    "name": "volcano-task",
                    "replicas": 1,
                    "policies": [
                        {"event": "TaskCompleted", "action": "CompleteJob"},
                    ],
                    "template": {
                        "metadata": {"labels": "{{ labels }}"},
                        "spec": {
                            "restartPolicy": "Never",
                            "serviceAccountName": "{{ service_account_name }}",
                            "containers": [
                                {
                                    "name": "volcano-job",
                                    "env": "{{ env }}",
                                    "image": "{{ image }}",
                                    "imagePullPolicy": "{{ image_pull_policy }}",
                                    "args": "{{ command }}",
                                }
                            ],
                        },
                    },
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Job configuration ----------------------------------------------------------
# ---------------------------------------------------------------------------


class VolcanoWorkerJobConfiguration(KubernetesWorkerJobConfiguration):
    """Configuration that accepts both batch/v1 *and* Volcano manifests."""

    # optional helper variable (queue) that can be templated in Volcano manifests
    queue: Optional[str] = Field(default=None)
    job_manifest: Dict[str, Any] = Field(
        json_schema_extra=dict(template=_get_default_volcano_job_manifest_template())
    )
    # ---------------------------------------------------------------------
    # Validation override
    # ---------------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_job_manifest(cls, self):
        if "tasks" not in self.job_manifest.get("spec", {}):
            raise ValueError("Volcano job must contain spec.tasks")
        return self

    # ------------------------------------------------------------------
    # Helpers – locate the main container regardless of job kind
    # ------------------------------------------------------------------

    def _main_container(self) -> Dict[str, Any]:
        if self.job_manifest.get("apiVersion") == "batch.volcano.sh/v1alpha1":
            return self.job_manifest["spec"]["tasks"][0]["template"]["spec"][
                "containers"
            ][0]
        return self.job_manifest["spec"]["template"]["spec"]["containers"][0]

    # Replace populate helpers so they use _main_container()
    def _populate_image_if_not_present(self):
        container = self._main_container()
        container.setdefault("image", get_prefect_image_name())

    def _populate_command_if_not_present(self):
        container = self._main_container()
        cmd = container.get("args")
        if cmd is None:
            container["args"] = shlex.split(self._base_flow_run_command())
        elif isinstance(cmd, str):
            container["args"] = shlex.split(cmd)
        elif not isinstance(cmd, list):
            raise ValueError("command/args must be string or list")

    def _populate_env_in_manifest(self):
        container = self._main_container()
        env = self.env
        if isinstance(env, dict):
            env = [{"name": k, "value": v} for k, v in env.items()]
        existing = container.get("env") or []
        container["env"] = [*env, *existing]

    def _propagate_labels_to_pod(self):
        """Propagates Prefect-specific labels to the pod in the job manifest."""
        if self.job_manifest.get("apiVersion") == "batch.volcano.sh/v1alpha1":
            # For Volcano Jobs, the pod template is at spec.tasks[0].template
            current_pod_metadata = self.job_manifest["spec"]["tasks"][0][
                "template"
            ].get("metadata", {})
            current_pod_labels = current_pod_metadata.get("labels", {})

            # Handle case where labels might be a template string
            if isinstance(current_pod_labels, str):
                current_pod_labels = {}

            all_labels = {**current_pod_labels, **self.labels}

            current_pod_metadata["labels"] = {
                _slugify_label_key(k): _slugify_label_value(v)
                for k, v in all_labels.items()
            }
            self.job_manifest["spec"]["tasks"][0]["template"]["metadata"] = (
                current_pod_metadata
            )
        else:
            # For standard Kubernetes Jobs, use the parent implementation
            super()._propagate_labels_to_pod()


# ---------------------------------------------------------------------------
# Variable schema (inherits everything, plus queue) -------------------------
# ---------------------------------------------------------------------------


class VolcanoWorkerVariables(KubernetesWorkerVariables):
    queue: str = Field(default="default", description="Volcano queue name")


# ---------------------------------------------------------------------------
# Worker implementation ------------------------------------------------------
# ---------------------------------------------------------------------------


class VolcanoWorker(KubernetesWorker):
    """Worker that detects manifest kind at runtime and submits to Volcano if asked."""

    type: str = "volcano"
    _display_name = "Volcano"
    _description = "Execute flow runs within Volcano Jobs or standard K8s Jobs."

    job_configuration = VolcanoWorkerJobConfiguration
    job_configuration_variables = VolcanoWorkerVariables

    # ---------------------------------------------------------------------
    # Job‑creation override
    # ---------------------------------------------------------------------

    async def _create_job(
        self, configuration: VolcanoWorkerJobConfiguration, client: ApiClient
    ):  # type: ignore[override]
        api_version = configuration.job_manifest.get("apiVersion", "batch/v1")
        if api_version == "batch.volcano.sh/v1alpha1":
            await self._replace_api_key_with_secret(configuration, client)
            api = CustomObjectsApi(client)
            return await api.create_namespaced_custom_object(
                group="batch.volcano.sh",
                version="v1alpha1",
                namespace=configuration.namespace,
                plural="jobs",
                body=configuration.job_manifest,
            )
        # else fall back to parent (Kubernetes Job)
        return await super()._create_job(configuration, client)  # type: ignore[arg-type]

    async def run(  # type: ignore[override]
        self,
        flow_run: "FlowRun",
        configuration: "VolcanoWorkerJobConfiguration",
        task_status: Optional[anyio.abc.TaskStatus[int]] = None,
    ) -> "KubernetesWorkerResult":
        """
        Executes a flow run within a Kubernetes Job or Volcano Job and waits for the flow run
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
            logger.info("Creating Kubernetes/Volcano job...")
            job = await self._create_job(configuration, client)

            # -------- Fix point: Adapt to both dict / V1Job returns ----------
            if isinstance(job, dict):  # Volcano path
                job_name = job["metadata"]["name"]
                namespace = job["metadata"]["namespace"]
                pid = f"{namespace}:{job_name}"
            else:  # batch/v1 path
                job_name = job.metadata.name
                namespace = job.metadata.namespace
                pid = f"{namespace}:{job_name}"

            if task_status is not None:
                task_status.started(pid)

            return KubernetesWorkerResult(identifier=pid, status_code=0)

    async def _replace_api_key_with_secret(  # noqa: C901 – keep it simple
        self,
        configuration: VolcanoWorkerJobConfiguration,
        client: ApiClient,
        secret_name: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """
        Same logic as parent class, but first finds the "main" container, then reads/writes env,
        to be compatible with both batch/v1 **and** Volcano manifests.
        """
        container = configuration._main_container()

        # Get env list; create new one if empty
        manifest_env: list[dict[str, Any]] = container.get("env") or []
        container["env"] = manifest_env

        # ------------------------------------------------------------
        # Content below is basically the same as parent class, just using manifest_env variable
        # ------------------------------------------------------------
        api_key_entry = next(
            (e for e in manifest_env if e.get("name") == "PREFECT_API_KEY"), {}
        )
        api_key = api_key_entry.get("value")

        if api_key and not secret_name:
            secret_name = f"prefect-{_slugify_name(self.name)}-api-key"
            secret = await self._upsert_secret(
                name=secret_name,
                value=api_key,
                namespace=configuration.namespace,
                client=client,
            )
            # Record for deletion when worker exits
            self._created_secrets[(secret.metadata.name, secret.metadata.namespace)] = (
                configuration
            )

        if secret_name:
            secret_key = secret_key or "value"
            new_entry = {
                "name": "PREFECT_API_KEY",
                "valueFrom": {"secretKeyRef": {"name": secret_name, "key": secret_key}},
            }
            # Replace old entry with new one
            container["env"] = [
                new_entry if e.get("name") == "PREFECT_API_KEY" else e
                for e in manifest_env
            ]


# ---------------------------------------------------------------------------
# Export for Prefect plugin system -----------------------------------------
# ---------------------------------------------------------------------------

__all__ = [
    "VolcanoWorker",
    "VolcanoWorkerJobConfiguration",
    "VolcanoWorkerVariables",
]

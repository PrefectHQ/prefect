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

import asyncio
import logging
import shlex
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

import anyio
import kubernetes_asyncio
from kubernetes_asyncio.client import (
    ApiClient,
    CoreV1Api,
    CustomObjectsApi,
    V1Pod,
    V1Job,
)
from kubernetes_asyncio.client.exceptions import ApiException
from pydantic import Field, model_validator

from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.utilities.timeout import timeout_async
from prefect_kubernetes.events import KubernetesEventsReplicator
from prefect_kubernetes.utilities import (
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

# ---------------------------------------------------------------------------
# Job configuration ----------------------------------------------------------
# ---------------------------------------------------------------------------


class VolcanoWorkerJobConfiguration(KubernetesWorkerJobConfiguration):
    """Configuration that accepts both batch/v1 *and* Volcano manifests."""

    # optional helper variable (queue) that can be templated in Volcano manifests
    queue: Optional[str] = Field(default=None)

    # ---------------------------------------------------------------------
    # Validation override
    # ---------------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_job_manifest(cls, self):
        api_version = self.job_manifest.get("apiVersion", "batch/v1")
        if api_version == "batch.volcano.sh/v1alpha1":
            if "tasks" not in self.job_manifest.get("spec", {}):
                raise ValueError("Volcano job must contain spec.tasks")
            return self
        return super()._validate_job_manifest()

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
    # Job‑creation / fetch overrides
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

    async def _get_job(
        self,
        job_name: str,
        namespace: str,
        client: "ApiClient",
        job_manifest: Optional[Dict[str, Any]] = None
    ) -> Union[Dict[str, Any], "V1Job", None]:
        """
        Get a Kubernetes or Volcano job by name.
        """
        if job_manifest and job_manifest.get("apiVersion") == "batch.volcano.sh/v1alpha1":
            # For Volcano Job, use CustomObjectsApi
            custom_api = CustomObjectsApi(client)
            try:
                return await custom_api.get_namespaced_custom_object(
                    group="batch.volcano.sh",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="jobs",
                    name=job_name
                )
            except ApiException as e:
                if e.status == 404:
                    self.logger.warning(f"Volcano Job {job_name} was removed.")
                return None
        # For standard Kubernetes Job or other types, use parent implementation
        return await super()._get_job(job_name, namespace, client, job_manifest)

    async def _get_job_pod(  # noqa: E501
        self,
        logger: logging.Logger,
        job_name: str,
        configuration: KubernetesWorkerJobConfiguration,
        client: ApiClient,
    ) -> Optional[V1Pod]:
        """Get the first running pod for a volcano job"""

        watch = kubernetes_asyncio.watch.Watch()
        logger.info(f"Volcano Job {job_name!r}: Starting watch for pod start...")
        last_phase = None
        last_pod_name: str | None = None
        core_client = CoreV1Api(client)
        label_selector = f"volcano.sh/job-name={job_name}"

        async for event in watch.stream(
            func=core_client.list_namespaced_pod,
            namespace=configuration.namespace,
            label_selector=label_selector,
            timeout_seconds=configuration.pod_watch_timeout_seconds,
        ):
            pod: V1Pod = event["object"]
            last_pod_name = pod.metadata.name
            phase = pod.status.phase
            if phase != last_phase:
                logger.info(f"Volcano Job {job_name!r}: Pod has status {phase!r}.")

            if phase != "Pending":
                return pod

            last_phase = phase

        logger.error(f"Volcano Job {job_name!r}: Pod never started.")
        await self._log_recent_events(
            logger, job_name, last_pod_name, configuration, client
        )

    # ------------------------------------------------------------------
    # Watch logic; for Volcano we poll status.state
    # ------------------------------------------------------------------

    async def _watch_job(
        self,
        logger: logging.Logger,
        job_name: str,
        configuration: VolcanoWorkerJobConfiguration,
        client: ApiClient,
        flow_run: "FlowRun",
    ) -> int:
        """
        Watch a Volcano job
        """
        logger.debug(f"Volcano Job {job_name!r}: Monitoring volcano job...")
        if configuration.job_manifest.get("apiVersion") != "batch.volcano.sh/v1alpha1":
            return await super()._watch_job(
                logger, job_name, configuration, client, flow_run
            )  # type: ignore[arg-type]

        # Get job and pod information
        job = await self._get_job(
            job_name=job_name, 
            namespace=configuration.namespace, 
            client=client,
            job_manifest=configuration.job_manifest
        )
        if not job:
            return -1
        
        pod = await self._get_job_pod(logger, job_name, configuration, client)
        if not pod:
            return -1

        # Volcano Job monitoring
        tasks = [
            self._monitor_volcano_job_state(
                logger, 
                job_name, 
                configuration.namespace, 
                client
            )
        ]
        
        if configuration.stream_output:
            tasks.append(
                self._stream_job_logs(
                    logger, 
                    pod.metadata.name, 
                    job_name, 
                    configuration, 
                    client
                )
            )

        try:
            with timeout_async(seconds=configuration.job_watch_timeout_seconds):
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.error("Error while monitoring Volcano job", exc_info=result)
                        return -1
        except TimeoutError:
            logger.error(f"Volcano job {job_name!r} timed out.")
            return -1

        return await self._get_container_exit_code(logger, job_name, configuration, client)
    

    # ------------------------------------------------------------------
    # PID helper override (job is dict for Volcano)
    # ------------------------------------------------------------------

    async def _get_infrastructure_pid(
        self, job: Union[Dict[str, Any], Any], client: ApiClient
    ) -> str:  # type: ignore[override]
        cluster_uid = await self._get_cluster_uid(client)
        if isinstance(job, dict):  # Volcano
            ns = job["metadata"]["namespace"]
            name = job["metadata"]["name"]
        else:
            ns = job.metadata.namespace
            name = job.metadata.name
        return f"{cluster_uid}:{ns}:{name}"

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

    async def run(  # type: ignore[override]
        self,
        flow_run: "FlowRun",
        configuration: "VolcanoWorkerJobConfiguration",
        task_status: Optional[anyio.abc.TaskStatus[int]] = None,
    ) -> "KubernetesWorkerResult":
        logger = self.get_flow_run_logger(flow_run)

        async with self._get_configured_kubernetes_client(configuration) as client:
            logger.info("Creating Kubernetes/Volcano job...")
            job = await self._create_job(configuration, client)

            # -------- Fix point: Adapt to both dict / V1Job returns ----------
            if isinstance(job, dict):  # Volcano path
                job_name = job["metadata"]["name"]
                namespace = job["metadata"]["namespace"]
            else:  # batch/v1 path
                job_name = job.metadata.name
                namespace = job.metadata.namespace

            pid = await self._get_infrastructure_pid(job, client)
            if task_status is not None:
                task_status.started(pid)

            # The rest of the logic is identical to the parent class, just passing in `namespace` ----------------
            events_replicator = KubernetesEventsReplicator(
                client=client,
                job_name=job_name,
                namespace=namespace,
                worker_resource=self._event_resource(),
                related_resources=self._event_related_resources(
                    configuration=configuration
                ),
                timeout_seconds=configuration.pod_watch_timeout_seconds,
            )
            async with events_replicator:
                status_code = await self._watch_job(
                    logger=logger,
                    job_name=job_name,
                    configuration=configuration,
                    client=client,
                    flow_run=flow_run,
                )

            return KubernetesWorkerResult(identifier=pid, status_code=status_code)


    async def _monitor_volcano_job_state(
        self,
        logger: logging.Logger,
        job_name: str,
        namespace: str,
        client: "ApiClient",
    ) -> None:
        """
        Monitor the state of a Volcano job until completion.
        
        Args:
            logger: Logger to use for logging
            job_name: Name of the Volcano job
            namespace: Namespace where the job is running
            client: Kubernetes API client
        """
        custom_api = CustomObjectsApi(client)
        while True:
            try:
                job_status = await custom_api.get_namespaced_custom_object_status(
                    group="batch.volcano.sh",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="jobs",
                    name=job_name,
                )
                volcano_state = job_status.get("status", {}).get("state", "Unknown")
                logger.info(f"Volcano job {job_name!r} state: {volcano_state}")

                if volcano_state in ["Completed", "Failed", "Aborted"]:
                    logger.info(f"Volcano job {job_name!r} finished with state: {volcano_state}")
                    return

                await asyncio.sleep(5)  # Poll every 5 seconds
            except Exception as e:
                logger.warning(f"Error monitoring Volcano job {job_name!r}: {e}")
                await asyncio.sleep(5)

# ---------------------------------------------------------------------------
# Export for Prefect plugin system -----------------------------------------
# ---------------------------------------------------------------------------

__all__ = [
    "VolcanoWorker",
    "VolcanoWorkerJobConfiguration",
    "VolcanoWorkerVariables",
]

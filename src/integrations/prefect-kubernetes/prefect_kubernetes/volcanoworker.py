"""volcanoworker.py – Custom Prefect worker that can handle both Kubernetes **batch/v1**
Jobs *and* Volcano **batch.volcano.sh/v1alpha1** Jobs.

* Default base‑job‑template is **Kubernetes** (so existing pools need not change).
* If a deployment (or pool base‑template) overrides `apiVersion` to
  `batch.volcano.sh/v1alpha1`, this worker automatically switches to Volcano
  logic: creation via `CustomObjectsApi`, pod selector `volcano.sh/job-name`,
  status polling via Job `status.state`.
* Otherwise it behaves exactly like the upstream `KubernetesWorker`.

Only minimal, internal‑use functionality is implemented.
"""
from __future__ import annotations

import asyncio
import anyio
import json
import logging
import shlex
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING, Union

import kubernetes_asyncio
from kubernetes_asyncio.client import (
    ApiClient,
    CoreV1Api,
    CustomObjectsApi,
    V1Pod,
    BatchV1Api,
)
from kubernetes_asyncio.client.exceptions import ApiException
from kubernetes_asyncio.client.models import CoreV1Event, CoreV1EventList
from pydantic import Field, model_validator
from typing_extensions import Self

from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.utilities.templating import find_placeholders
from prefect_kubernetes.utilities import (
    _slugify_label_key,
    _slugify_label_value,
    _slugify_name,
)
from prefect_kubernetes.events import KubernetesEventsReplicator
from prefect_kubernetes.settings import KubernetesSettings
from prefect_kubernetes.worker import (
    KubernetesWorker,
    KubernetesWorkerJobConfiguration,
    KubernetesWorkerVariables,
    KubernetesWorkerResult,
)

if TYPE_CHECKING:
    from kubernetes_asyncio.client import ApiClient
    from prefect_kubernetes.volcanoworker import (          # noqa: F401
        VolcanoWorkerJobConfiguration,
        KubernetesWorkerResult,
    )
    from prefect.client.schemas.objects import FlowRun

# ---------------------------------------------------------------------------
# Job configuration ----------------------------------------------------------
# ---------------------------------------------------------------------------

class VolcanoWorkerJobConfiguration(KubernetesWorkerJobConfiguration):
    """Configuration that accepts both batch/v1 *and* Volcano manifests."""

    # optional helper variable (queue) that can be templated in Volcano manifests
    queue: str | None = Field(default=None)

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
            return self.job_manifest["spec"]["tasks"][0]["template"]["spec"]["containers"][0]
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

    async def _create_job(self, configuration: VolcanoWorkerJobConfiguration, client: ApiClient):  # type: ignore[override]
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

    async def _get_job(self, logger: logging.Logger, job_name: str, configuration: VolcanoWorkerJobConfiguration, client: ApiClient):  # noqa: E501
        if configuration.job_manifest.get("apiVersion") == "batch.volcano.sh/v1alpha1":
            api = CustomObjectsApi(client)
            try:
                return await api.get_namespaced_custom_object(
                    group="batch.volcano.sh",
                    version="v1alpha1",
                    namespace=configuration.namespace,
                    plural="jobs",
                    name=job_name,
                )
            except ApiException:
                logger.error("Volcano Job %s was removed.", job_name)
                return None
        return await super()._get_job(logger, job_name, configuration, client)  # type: ignore[arg-type]

    async def _get_job_pod(            # noqa: E501
        self,
        logger: logging.Logger,
        job_name: str,
        configuration: KubernetesWorkerJobConfiguration,
        client: ApiClient,
    ) -> V1Pod | None:
        """
        Locate the first Pod belonging to the Job.

        - Volcano Job：依次尝试
            1. `volcano.sh/job-name=<job>`
            2. `job-name=<job>`
            3. ownerReferences.name == <job>
        - batch/v1 Job：保持父类行为
        """
        timeout = configuration.pod_watch_timeout_seconds or 0
        deadline = anyio.current_time() + timeout if timeout else None

        core = CoreV1Api(client)
        selectors = [
            f"volcano.sh/job-name={job_name}",
            f"job-name={job_name}",
        ]

        while True:
            # 1. 先按 label selector 查
            for sel in selectors:
                pods = await core.list_namespaced_pod(
                    configuration.namespace, label_selector=sel
                )
                if pods.items:
                    return pods.items[0]            # ← 找到了！

            # 2. 再兜底 ownerReferences
            pods = await core.list_namespaced_pod(configuration.namespace)
            for pod in pods.items:
                for ref in pod.metadata.owner_references or []:
                    if ref.kind.lower() == "job" and ref.name == job_name:
                        return pod

            # ——— 没找到；判断是否超时 ———
            if deadline and anyio.current_time() >= deadline:
                logger.error("Pod for Volcano Job %s not found in %ss",
                            job_name, timeout)
                return None

            await asyncio.sleep(2)   # 每 2 秒再查一次

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
        if configuration.job_manifest.get("apiVersion") != "batch.volcano.sh/v1alpha1":
            return await super()._watch_job(logger, job_name, configuration, client, flow_run)  # type: ignore[arg-type]

        # Volcano path ---------------------------------------------------
        pod = await self._get_job_pod(logger, job_name, configuration, client)
        if not pod:
            return -1

        async def _poll_state() -> str:
            api = CustomObjectsApi(client)
            while True:
                job = await api.get_namespaced_custom_object_status(
                    group="batch.volcano.sh",
                    version="v1alpha1",
                    namespace=configuration.namespace,
                    plural="jobs",
                    name=job_name,
                )
                state_obj = job.get("status", {}).get("state", "Unknown")

                # 安全兼容判断（防止 future 出现 dict）
                if isinstance(state_obj, dict):
                    state = state_obj.get("phase", "Unknown")
                else:
                    state = state_obj

                logger.info(f"Polling Volcano Job {job_name} state: {state}")
                if state in {"Completed", "Failed", "Aborted"}:
                    return state
                await asyncio.sleep(5)

        # 注意：必须将协程包装为 Task，否则 asyncio.wait 会报 TypeError
        poll_task = asyncio.create_task(_poll_state())
        tasks = [poll_task]

        if configuration.stream_output:
            stream_task = asyncio.create_task(
                self._stream_job_logs(logger, pod.metadata.name, job_name, configuration, client)
            )
            tasks.append(stream_task)

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        final_state: str = next(iter(done)).result()
        logger.info("Volcano Job %s finished with state %s", job_name, final_state)

        # 读取容器状态作为退出码
        core = CoreV1Api(client)
        pod = await core.read_namespaced_pod(pod.metadata.name, configuration.namespace)
        cs = pod.status.container_statuses and pod.status.container_statuses[0]
        if cs and cs.state and cs.state.terminated:
            return cs.state.terminated.exit_code or 0
        return 0 if final_state == "Completed" else -1

    # ------------------------------------------------------------------
    # PID helper override (job is dict for Volcano)
    # ------------------------------------------------------------------

    async def _get_infrastructure_pid(self, job: Union[Dict[str, Any], Any], client: ApiClient) -> str:  # type: ignore[override]
        cluster_uid = await self._get_cluster_uid(client)
        if isinstance(job, dict):  # Volcano
            ns = job["metadata"]["namespace"]
            name = job["metadata"]["name"]
        else:
            ns = job.metadata.namespace
            name = job.metadata.name
        return f"{cluster_uid}:{ns}:{name}"
    
    async def _replace_api_key_with_secret(        # noqa: C901 – keep it simple
        self,
        configuration: VolcanoWorkerJobConfiguration,
        client: ApiClient,
        secret_name: str | None = None,
        secret_key: str | None = None,
    ):
        """
        与父类相同逻辑，但先找到“主” container，再读/写 env，
        从而兼容 batch/v1 **和** Volcano 两种 manifest。
        """
        container = configuration._main_container()

        # 取出 env 列表；如果为空就新建
        manifest_env: list[dict[str, Any]] = container.get("env") or []
        container["env"] = manifest_env

        # ------------------------------------------------------------
        # 下面的内容与父类基本一致，只是用了 manifest_env 变量
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
            # 记录，便于 worker 退出时删除
            self._created_secrets[(secret.metadata.name, secret.metadata.namespace)] = (
                configuration
            )

        if secret_name:
            secret_key = secret_key or "value"
            new_entry = {
                "name": "PREFECT_API_KEY",
                "valueFrom": {
                    "secretKeyRef": {"name": secret_name, "key": secret_key}
                },
            }
            # 用新 entry 替换旧的
            container["env"] = [
                new_entry if e.get("name") == "PREFECT_API_KEY" else e
                for e in manifest_env
            ]

    async def run(                                           # type: ignore[override]
        self,
        flow_run: "FlowRun",
        configuration: "VolcanoWorkerJobConfiguration",
        task_status: anyio.abc.TaskStatus[int] | None = None,
    ) -> "KubernetesWorkerResult":
        logger = self.get_flow_run_logger(flow_run)

        async with self._get_configured_kubernetes_client(configuration) as client:
            logger.info("Creating Kubernetes/Volcano job...")
            job = await self._create_job(configuration, client)

            # -------- 修正点：适配 dict / V1Job 两种返回 ----------
            if isinstance(job, dict):        # Volcano path
                job_name   = job["metadata"]["name"]
                namespace  = job["metadata"]["namespace"]
            else:                            # batch/v1 path
                job_name   = job.metadata.name
                namespace  = job.metadata.namespace

            pid = await self._get_infrastructure_pid(job, client)
            if task_status is not None:
                task_status.started(pid)

            # 其余逻辑与父类完全相同，只是把 `namespace` 传进去 ----------------
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


# ---------------------------------------------------------------------------
# Export for Prefect plugin system -----------------------------------------
# ---------------------------------------------------------------------------

__all__ = [
    "VolcanoWorker",
    "VolcanoWorkerJobConfiguration",
    "VolcanoWorkerVariables",
]
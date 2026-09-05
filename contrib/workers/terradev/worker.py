"""Terradev work pool worker for Prefect.

Provisions a GPU instance via Terradev for the duration of a flow run,
executes the run on that instance, and terminates it on completion or failure.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any, Optional
from uuid import UUID

from prefect.client.schemas import FlowRun
from prefect.workers.base import BaseWorker, BaseWorkerResult

from .worker_config import TerradevWorkerConfiguration


class TerradevWorkerResult(BaseWorkerResult):
    pass


class TerradevWorker(BaseWorker):
    """Prefect worker that routes flow runs to GPU compute via Terradev.

    Provisions a VM from the cheapest matching provider, runs the flow,
    and terminates the instance regardless of outcome.

    Usage::

        prefect worker start --pool gpu-pool --type terradev
    """

    type = "terradev"
    job_configuration = TerradevWorkerConfiguration

    async def run(
        self,
        flow_run: FlowRun,
        configuration: TerradevWorkerConfiguration,
        task_status: Optional[Any] = None,
    ) -> TerradevWorkerResult:
        instance_id: Optional[str] = None
        try:
            instance_id, address = await self._provision(configuration)
            self._logger.info(
                "Terradev: provisioned %s on %s (%s)",
                configuration.gpu_type,
                configuration.provider or "cheapest",
                address,
            )
            if task_status:
                task_status.started()

            exit_code = await self._run_flow(flow_run, address, configuration)
            status_code = 0 if exit_code == 0 else 1
            return TerradevWorkerResult(
                status_code=status_code,
                identifier=str(flow_run.id),
            )
        except Exception as exc:
            self._logger.error("Terradev worker failed: %s", exc)
            return TerradevWorkerResult(status_code=1, identifier=str(flow_run.id))
        finally:
            if instance_id:
                await self._terminate(instance_id, configuration)

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _provision(
        self, cfg: TerradevWorkerConfiguration
    ) -> tuple[str, str]:
        cmd = ["terradev", "compute", "provision", "--gpu", cfg.gpu_type, "--format", "json"]
        if cfg.provider:
            cmd += ["--provider", cfg.provider]
        if cfg.region:
            cmd += ["--region", cfg.region]
        if cfg.max_price_per_hour:
            cmd += ["--max-price", str(cfg.max_price_per_hour)]
        if cfg.spot:
            cmd.append("--spot")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"terradev provision failed: {stderr.decode()}")

        import json
        result = json.loads(stdout)
        return result["instance_id"], result["address"]

    async def _run_flow(
        self, flow_run: FlowRun, address: str, cfg: TerradevWorkerConfiguration
    ) -> int:
        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=30",
            f"{cfg.ssh_user}@{address}",
            f"prefect flow-run execute {flow_run.id}",
        ]
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        return proc.returncode or 0

    async def _terminate(self, instance_id: str, cfg: TerradevWorkerConfiguration) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "terradev", "compute", "terminate", instance_id,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            self._logger.info("Terradev: terminated %s", instance_id)
        except Exception as exc:
            self._logger.warning("Terradev: failed to terminate %s: %s", instance_id, exc)

"""Terradev work pool worker for Prefect.

Provisions a GPU instance via Terradev for the duration of a flow run,
executes the run on that instance, and terminates it on completion or failure.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

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
                # Pass the infrastructure ID so Prefect can associate
                # cancellation and concurrency slots with this instance.
                task_status.started(instance_id)

            exit_code = await self._run_flow(flow_run, address, configuration)
            status_code = 0 if exit_code == 0 else 1
            return TerradevWorkerResult(
                status_code=status_code,
                identifier=instance_id or str(flow_run.id),
            )
        except Exception as exc:
            self._logger.error("Terradev worker failed: %s", exc)
            return TerradevWorkerResult(
                status_code=1,
                identifier=instance_id or str(flow_run.id),
            )
        finally:
            if instance_id:
                await self._terminate(instance_id, configuration)

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _provision(
        self, cfg: TerradevWorkerConfiguration
    ) -> tuple[str, str]:
        """Provision a GPU instance via the Terradev Python API."""
        from terradev_cli.providers.provider_factory import ProviderFactory

        factory = ProviderFactory()
        provider_name = cfg.provider or await self._cheapest_provider(cfg)
        p = factory.create_provider(provider_name, cfg.credentials)
        try:
            result = await p.provision_instance(
                gpu_type=cfg.gpu_type,
                count=1,
                max_price=cfg.max_price_per_hour,
                region=cfg.region,
                spot=cfg.spot,
            )
            instance_id = result.instance_id
            address = getattr(result, "address", "") or ""

            # Poll until the provider assigns an IP (up to 5 minutes).
            if not address:
                for _ in range(30):
                    await asyncio.sleep(10)
                    status = await p.get_instance_status(instance_id)
                    address = getattr(status, "address", "") or ""
                    if address:
                        break

            if not address:
                raise RuntimeError(
                    f"Instance {instance_id} did not receive an IP within 5 minutes"
                )

            return instance_id, address
        finally:
            await p.aclose()

    async def _cheapest_provider(self, cfg: TerradevWorkerConfiguration) -> str:
        """Return the cheapest provider name for the requested GPU."""
        from terradev_cli.providers.provider_factory import ProviderFactory

        factory = ProviderFactory()
        best_price = float("inf")
        best_name = "runpod"

        for name, creds in cfg.credentials.items():
            try:
                p = factory.create_provider(name, creds)
                try:
                    quotes = await p.get_instance_quotes(
                        gpu_type=cfg.gpu_type,
                        count=1,
                        max_price=cfg.max_price_per_hour,
                    )
                    if quotes and quotes[0].price_per_hour < best_price:
                        best_price = quotes[0].price_per_hour
                        best_name = name
                finally:
                    await p.aclose()
            except Exception:  # noqa: BLE001
                continue

        return best_name

    async def _run_flow(
        self, flow_run: FlowRun, address: str, cfg: TerradevWorkerConfiguration
    ) -> int:
        """Execute the flow run on the remote instance via SSH."""
        env_fwd = ""
        if api_url := os.getenv("PREFECT_API_URL"):
            env_fwd += f"PREFECT_API_URL={api_url} "
        if api_key := os.getenv("PREFECT_API_KEY"):
            env_fwd += f"PREFECT_API_KEY={api_key} "

        remote_cmd = f"{env_fwd}prefect flow-run execute {flow_run.id}"
        cmd = [
            "ssh",
            # Trust on first connect; never silently accept a changed key.
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=30",
            f"{cfg.ssh_user}@{address}",
            remote_cmd,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        return proc.returncode or 0

    async def _terminate(
        self, instance_id: str, cfg: TerradevWorkerConfiguration
    ) -> None:
        """Terminate the instance; logs a warning but does not swallow errors."""
        from terradev_cli.providers.provider_factory import ProviderFactory

        provider_name = cfg.provider or next(iter(cfg.credentials), None)
        if not provider_name:
            self._logger.warning(
                "Terradev: no provider set, cannot terminate %s", instance_id
            )
            return

        factory = ProviderFactory()
        p = factory.create_provider(provider_name, cfg.credentials.get(provider_name, {}))
        try:
            await p.terminate_instance(instance_id)
            self._logger.info("Terradev: terminated %s", instance_id)
        except Exception as exc:
            self._logger.warning(
                "Terradev: failed to terminate %s — instance may still be billing: %s",
                instance_id,
                exc,
            )
            raise
        finally:
            await p.aclose()

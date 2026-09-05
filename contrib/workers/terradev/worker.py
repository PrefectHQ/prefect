"""Terradev work pool worker for Prefect.

Provisions a GPU instance via Terradev for the duration of a flow run,
executes the run on that instance, and terminates it on completion or failure.
"""

from __future__ import annotations

import asyncio
import os
import shlex
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
        provider_name: Optional[str] = None
        try:
            # _provision returns immediately after creation (before IP polling)
            # so instance_id is set in the outer scope before any RuntimeError
            # from _wait_for_address can prevent cleanup.
            instance_id, address, provider_name = await self._provision(configuration)
            if not address:
                address = await self._wait_for_address(
                    instance_id, provider_name, configuration
                )

            self._logger.info(
                "Terradev: provisioned %s on %s (%s)",
                configuration.gpu_type,
                provider_name,
                address,
            )
            if task_status:
                # Encode provider_name:instance_id so kill_infrastructure
                # can parse it back and reach the correct provider.
                task_status.started(f"{provider_name}:{instance_id}")

            exit_code = await self._run_flow(flow_run, address, configuration)
            status_code = 0 if exit_code == 0 else 1
            return TerradevWorkerResult(
                status_code=status_code,
                identifier=f"{provider_name}:{instance_id}",
            )
        except Exception as exc:
            self._logger.error("Terradev worker failed: %s", exc)
            return TerradevWorkerResult(
                status_code=1,
                identifier=f"{provider_name or 'unknown'}:{instance_id or 'unknown'}",
            )
        finally:
            if instance_id and provider_name:
                await self._terminate(instance_id, provider_name, configuration)

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        grace_seconds: int = 30,
    ) -> None:
        """Terminate the provisioned GPU when Prefect cancels a pending run."""
        try:
            provider_name, instance_id = infrastructure_pid.split(":", 1)
        except ValueError:
            self._logger.warning(
                "Terradev: cannot parse infrastructure ID %r — "
                "manual termination may be required",
                infrastructure_pid,
            )
            return

        pool_vars = (
            getattr(self, "_work_pool", None)
            and self._work_pool.base_job_template.get("variables", {})
        ) or {}
        cfg = TerradevWorkerConfiguration(
            provider=provider_name,
            credentials=pool_vars.get("credentials", {}),
        )
        await self._terminate(instance_id, provider_name, cfg)

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _provision(
        self, cfg: TerradevWorkerConfiguration
    ) -> tuple[str, str, str]:
        """Provision a GPU; return (instance_id, address_or_empty, provider_name).

        Returns immediately after instance creation — IP polling is handled by
        _wait_for_address so that instance_id is captured before any timeout
        raises and cleanup in run() can call _terminate.
        """
        from terradev_cli.providers.provider_factory import ProviderFactory

        factory = ProviderFactory()
        provider_name = cfg.provider or await self._cheapest_provider(cfg)
        p = factory.create_provider(
            provider_name, cfg.credentials.get(provider_name, {})
        )
        try:
            result = await p.provision_instance(
                gpu_type=cfg.gpu_type,
                count=1,
                max_price=cfg.max_price_per_hour,
                region=cfg.region,
                spot=cfg.spot,
            )
            address = getattr(result, "address", "") or ""
            return result.instance_id, address, provider_name
        finally:
            await p.aclose()

    async def _wait_for_address(
        self,
        instance_id: str,
        provider_name: str,
        cfg: TerradevWorkerConfiguration,
    ) -> str:
        """Poll until the provider assigns a public IP (up to 5 minutes).

        Intentionally separated from _provision: if this raises, instance_id
        is already set in run() so the finally block can terminate the GPU.
        """
        from terradev_cli.providers.provider_factory import ProviderFactory

        factory = ProviderFactory()
        p = factory.create_provider(
            provider_name, cfg.credentials.get(provider_name, {})
        )
        try:
            for _ in range(30):
                await asyncio.sleep(10)
                status = await p.get_instance_status(instance_id)
                address = getattr(status, "address", "") or ""
                if address:
                    return address
        finally:
            await p.aclose()

        raise RuntimeError(
            f"Instance {instance_id} on {provider_name} did not receive an IP "
            "within 5 minutes"
        )

    async def _cheapest_provider(self, cfg: TerradevWorkerConfiguration) -> str:
        """Return the name of the cheapest configured provider for the GPU."""
        from terradev_cli.providers.provider_factory import ProviderFactory

        factory = ProviderFactory()
        best_price = float("inf")
        best_name = next(iter(cfg.credentials), "runpod")

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
        """Execute the flow run on the remote instance via SSH.

        Uses configuration.command when set. Prefect API credentials are
        forwarded via shlex.quote — values are never interpolated as raw shell
        syntax and do not appear in process listings.
        """
        flow_cmd_parts: list[str] = (
            list(cfg.command)
            if getattr(cfg, "command", None)
            else ["prefect", "flow-run", "execute", str(flow_run.id)]
        )

        env_pairs: list[str] = []
        for var in ("PREFECT_API_URL", "PREFECT_API_KEY"):
            val = os.getenv(var)
            if val:
                env_pairs.append(f"{var}={shlex.quote(val)}")

        remote_parts = (["env"] + env_pairs if env_pairs else []) + flow_cmd_parts
        remote_cmd = " ".join(remote_parts)

        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=30",
            f"{cfg.ssh_user}@{address}",
            remote_cmd,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.communicate()
        return proc.returncode or 0

    async def _terminate(
        self,
        instance_id: str,
        provider_name: str,
        cfg: TerradevWorkerConfiguration,
    ) -> None:
        """Terminate the instance; re-raises on failure so the caller can log the leak."""
        from terradev_cli.providers.provider_factory import ProviderFactory

        factory = ProviderFactory()
        p = factory.create_provider(
            provider_name, cfg.credentials.get(provider_name, {})
        )
        try:
            await p.terminate_instance(instance_id)
            self._logger.info(
                "Terradev: terminated %s on %s", instance_id, provider_name
            )
        except Exception as exc:
            self._logger.warning(
                "Terradev: failed to terminate %s on %s "
                "— instance may still be billing: %s",
                instance_id,
                provider_name,
                exc,
            )
            raise
        finally:
            await p.aclose()

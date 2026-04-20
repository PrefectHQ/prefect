"""Shared worker utilities used by both typer and cyclopts CLI implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Type

from prefect._internal.integrations import KNOWN_EXTRAS_FOR_PACKAGES
from prefect.client.collections import get_collections_metadata_client
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import WorkQueueFilter, WorkQueueFilterName
from prefect.exceptions import ObjectNotFound
from prefect.plugins import load_prefect_collections
from prefect.utilities.dispatch import lookup_type
from prefect.workers.base import BaseWorker

if TYPE_CHECKING:
    from rich.console import Console


async def _check_work_pool_paused(work_pool_name: str) -> bool:
    try:
        async with get_client() as client:
            work_pool = await client.read_work_pool(work_pool_name=work_pool_name)
            return work_pool.is_paused
    except ObjectNotFound:
        return False


async def _check_work_queues_paused(
    work_pool_name: str, work_queues: Optional[list[str]]
) -> bool:
    """Check if all work queues in the work pool are paused.

    Args:
        work_pool_name: the name of the work pool to check
        work_queues: the names of the work queues to check
    """
    try:
        work_queues_filter = (
            WorkQueueFilter(name=WorkQueueFilterName(any_=work_queues))
            if work_queues
            else None
        )
        async with get_client() as client:
            wqs = await client.read_work_queues(
                work_pool_name=work_pool_name, work_queue_filter=work_queues_filter
            )
            return all(queue.is_paused for queue in wqs) if wqs else False
    except ObjectNotFound:
        return False


async def _retrieve_worker_type_from_pool(
    console: "Console",
    exit_fn: object,
    work_pool_name: Optional[str] = None,
) -> str:
    """Discover the worker type for a work pool.

    Args:
        console: Rich console for output
        exit_fn: Called with an error message when the pool is push/managed
        work_pool_name: Name of the work pool
    """
    try:
        async with get_client() as client:
            work_pool = await client.read_work_pool(work_pool_name=work_pool_name)

        worker_type = work_pool.type
        console.print(
            f"Discovered type {worker_type!r} for work pool {work_pool.name!r}."
        )

        if work_pool.is_push_pool or work_pool.is_managed_pool:
            exit_fn(
                "Workers are not required for push work pools. "
                "See https://docs.prefect.io/latest/deploy/infrastructure-examples/serverless "
                "for more details."
            )

    except ObjectNotFound:
        console.print(
            (
                f"Work pool {work_pool_name!r} does not exist and no worker type was"
                " provided. Starting a process worker..."
            ),
            style="yellow",
        )
        worker_type = "process"
    return worker_type


def _load_worker_class(worker_type: str) -> Optional[Type[BaseWorker]]:
    try:
        load_prefect_collections()
        return lookup_type(BaseWorker, worker_type)
    except KeyError:
        return None


async def _install_package(
    console: "Console",
    package: str,
    upgrade: bool = False,
) -> None:
    from prefect._internal.installation import ainstall_packages

    console.print(f"Installing {package}...")
    install_package = KNOWN_EXTRAS_FOR_PACKAGES.get(package, package)
    await ainstall_packages([install_package], stream_output=True, upgrade=upgrade)


async def _find_package_for_worker_type(
    console: "Console",
    worker_type: str,
) -> Optional[str]:
    async with get_collections_metadata_client() as client:
        worker_metadata = await client.read_worker_metadata()

    worker_types_with_packages = {
        wt: package_name
        for package_name, worker_dict in worker_metadata.items()
        for wt in worker_dict
        if wt != "prefect-agent"
    }
    try:
        return worker_types_with_packages[worker_type]
    except KeyError:
        console.print(
            f"Could not find a package for worker type {worker_type!r}.",
            style="yellow",
        )
        return None

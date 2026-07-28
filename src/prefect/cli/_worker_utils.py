"""Shared worker utilities used by both typer and cyclopts CLI implementations."""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable, NoReturn, Optional, Type

import httpx

from prefect._internal.integrations import KNOWN_EXTRAS_FOR_PACKAGES
from prefect.client.collections import get_collections_metadata_client
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import WorkQueueFilter, WorkQueueFilterName
from prefect.exceptions import ObjectNotFound
from prefect.logging.loggers import get_logger
from prefect.plugins import load_prefect_collections
from prefect.utilities.dispatch import lookup_type
from prefect.workers.base import BaseWorker, _is_transient_api_error

if TYPE_CHECKING:
    from rich.console import Console

logger: logging.Logger = get_logger(__name__)

WORKER_PID_DIR_NAME = "workers"


def _worker_marker_path(pid_file: Path) -> Path:
    """Return the path storing the process identity marker for a worker's PID file."""
    return pid_file.with_suffix(".marker")


def _verify_worker_process(pid_file: Path, pid: int) -> bool:
    """Check whether `pid` is still the same worker process recorded at `pid_file`.

    A liveness check alone cannot tell a still-running worker from an unrelated
    process that the OS has since assigned the same PID, so this also compares the
    identity marker recorded when the worker was started. If no marker was
    recorded (e.g. no procfs on this platform), liveness alone is trusted.
    """
    from prefect.cli._server_utils import _is_process_running, _process_start_marker

    if not _is_process_running(pid):
        return False

    marker_path = _worker_marker_path(pid_file)
    if not marker_path.exists():
        return True
    try:
        recorded_marker = marker_path.read_text()
    except OSError:
        return True

    current_marker = _process_start_marker(pid)
    return current_marker is None or current_marker == recorded_marker


async def _check_work_pool_paused(work_pool_name: str) -> bool:
    try:
        async with get_client() as client:
            work_pool = await client.read_work_pool(work_pool_name=work_pool_name)
            return work_pool.is_paused
    except ObjectNotFound:
        return False
    except httpx.HTTPError as exc:
        logger.debug(
            "Unable to check if work pool %r is paused: %s", work_pool_name, exc
        )
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
    except httpx.HTTPError as exc:
        logger.debug(
            "Unable to check if the work queues in work pool %r are paused: %s",
            work_pool_name,
            exc,
        )
        return False


async def _retrieve_worker_type_from_pool(
    console: "Console",
    exit_fn: Callable[[str], NoReturn],
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
    except httpx.HTTPError as exc:
        if _is_transient_api_error(exc):
            exit_fn(
                f"Unable to reach the Prefect API to determine the type of work pool"
                f" {work_pool_name!r}: {exc}. Provide a worker type with '--type' to"
                " start a worker while the API is unavailable."
            )
        exit_fn(f"Unable to determine the type of work pool {work_pool_name!r}: {exc}")
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


def _run_worker_in_background(
    console: "Console",
    pid_file: Path,
    *,
    work_pool_name: str,
    worker_name: Optional[str] = None,
    work_queues: Optional[list[str]] = None,
    worker_type: Optional[str] = None,
    limit: Optional[int] = None,
    prefetch_seconds: Optional[int] = None,
    run_once: bool = False,
    with_healthcheck: bool = False,
    install_policy: str = "prompt",
    base_job_template: Optional[Path] = None,
    create_pool_if_not_found: bool = True,
    profile_name: Optional[str] = None,
) -> None:
    """Spawn `prefect worker start` as a background process.

    Reconstructs the equivalent foreground command from the provided options,
    launches it with `subprocess.Popen`, and records the child process id in
    `pid_file` so `prefect worker stop` can terminate it later. This mirrors the
    background behavior of `prefect server start`. The caller resolves a concrete
    `worker_name` so each background worker has a stable, individually stoppable
    identity, and passes the active `profile_name` so the detached child polls the
    same API the parent validated against instead of whatever profile happens to
    be active on disk when it starts.
    """
    from prefect.cli._server_utils import _process_start_marker, _write_pid_file
    from prefect.utilities.slugify import slugify

    command = [sys.executable, "-m", "prefect"]
    if profile_name:
        command += ["--profile", profile_name]
    command += ["worker", "start", "--pool", work_pool_name]
    if worker_name:
        command += ["--name", worker_name]
    if worker_type:
        command += ["--type", worker_type]
    for queue in work_queues or []:
        command += ["--work-queue", queue]
    if limit is not None:
        command += ["--limit", str(limit)]
    if prefetch_seconds is not None:
        command += ["--prefetch-seconds", str(prefetch_seconds)]
    if run_once:
        command += ["--run-once"]
    if with_healthcheck:
        command += ["--with-healthcheck"]
    if base_job_template is not None:
        command += ["--base-job-template", str(base_job_template)]
    if not create_pool_if_not_found:
        command += ["--no-create-pool-if-not-found"]
    command += ["--install-policy", install_policy]

    logger.debug("Opening worker process with command: %s", shlex.join(command))

    # Detach from the CLI process (own session, output to DEVNULL) so the worker
    # survives the parent exiting instead of dying on a broken pipe once the CLI
    # closes the pipe read ends.
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=(os.name != "nt"),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    _write_pid_file(pid_file, process.pid)
    marker = _process_start_marker(process.pid)
    if marker is not None:
        _worker_marker_path(pid_file).write_text(marker)

    console.print(
        f"Worker {worker_name!r} is now running in the background. Run "
        f"`prefect worker stop {slugify(worker_name or '')}` to stop it."
    )

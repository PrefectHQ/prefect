from __future__ import annotations

import argparse
import asyncio
import os
import signal
import socket
import sys
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"[{timestamp()}] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run and monitor a Prefect process worker long enough to reproduce "
            "Windows worker-channel or heartbeat stalls."
        )
    )
    parser.add_argument("--work-pool", default=os.getenv("WORK_POOL_NAME"))
    parser.add_argument("--worker-name", default=os.getenv("WORKER_NAME"))
    parser.add_argument("--duration-minutes", type=float, default=355)
    parser.add_argument("--monitor-interval-seconds", type=float, default=60)
    parser.add_argument("--startup-grace-seconds", type=float, default=180)
    parser.add_argument("--heartbeat-seconds", type=float, default=30)
    parser.add_argument("--query-seconds", type=float, default=10)
    parser.add_argument("--healthcheck-port", type=int, default=8080)
    parser.add_argument("--keep-work-pool", action="store_true")
    parser.add_argument("--worker-log-path", default="worker.log")
    return parser.parse_args()


async def ensure_work_pool(work_pool_name: str) -> bool:
    async with get_client() as client:
        try:
            await client.read_work_pool(work_pool_name)
            log(f"Using existing work pool {work_pool_name!r}.")
            return False
        except ObjectNotFound:
            pass

        try:
            await client.create_work_pool(
                WorkPoolCreate(name=work_pool_name, type="process")
            )
            log(f"Created process work pool {work_pool_name!r}.")
            return True
        except ObjectAlreadyExists:
            log(f"Work pool {work_pool_name!r} was created concurrently.")
            return False


async def delete_work_pool(work_pool_name: str) -> None:
    async with get_client() as client:
        with suppress(ObjectNotFound):
            await client.delete_work_pool(work_pool_name)
            log(f"Deleted work pool {work_pool_name!r}.")


def worker_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        "-m",
        "prefect",
        "worker",
        "start",
        "--pool",
        args.work_pool,
        "--type",
        "process",
        "--name",
        args.worker_name,
        "--with-healthcheck",
        "--install-policy",
        "never",
    ]


async def stream_output(
    proc: asyncio.subprocess.Process, worker_log_path: Path
) -> None:
    assert proc.stdout is not None
    with worker_log_path.open("w", encoding="utf-8") as worker_log:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace").rstrip()
            print(decoded, flush=True)
            worker_log.write(decoded + "\n")
            worker_log.flush()


async def read_worker_state(
    work_pool_name: str, worker_name: str
) -> dict[str, Any] | None:
    async with get_client() as client:
        workers = await client.read_workers_for_work_pool(work_pool_name, limit=200)
        for worker in workers:
            if worker.name == worker_name:
                return {
                    "name": worker.name,
                    "status": str(worker.status),
                    "last_heartbeat_time": (
                        worker.last_heartbeat_time.isoformat()
                        if worker.last_heartbeat_time
                        else None
                    ),
                    "heartbeat_interval_seconds": worker.heartbeat_interval_seconds,
                }
    return None


async def read_work_pool_state(work_pool_name: str) -> dict[str, Any]:
    async with get_client() as client:
        work_pool = await client.read_work_pool(work_pool_name)
        return {
            "name": work_pool.name,
            "status": str(work_pool.status),
            "is_paused": work_pool.is_paused,
        }


async def healthcheck(port: int) -> str:
    url = f"http://127.0.0.1:{port}/health"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
        return f"{response.status_code} {response.text}"
    except Exception as exc:
        return f"ERROR {type(exc).__name__}: {exc}"


async def monitor(
    args: argparse.Namespace, proc: asyncio.subprocess.Process
) -> list[dict[str, Any]]:
    started_at = datetime.now(UTC)
    deadline = datetime.now(UTC) + timedelta(minutes=args.duration_minutes)
    observations: list[dict[str, Any]] = []
    while datetime.now(UTC) < deadline:
        worker_state = await read_worker_state(args.work_pool, args.worker_name)
        work_pool_state = await read_work_pool_state(args.work_pool)
        health = await healthcheck(args.healthcheck_port)
        observation = {
            "time": timestamp(),
            "elapsed_seconds": (datetime.now(UTC) - started_at).total_seconds(),
            "worker_process_returncode": proc.returncode,
            "healthcheck": health,
            "work_pool": work_pool_state,
            "worker": worker_state,
        }
        observations.append(observation)
        log(f"observation={observation!r}")

        if proc.returncode is not None:
            log(f"Worker process exited early with return code {proc.returncode}.")
            break

        await asyncio.sleep(args.monitor_interval_seconds)

    return observations


async def terminate_worker(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return

    log("Stopping worker process.")
    if os.name == "nt":
        proc.terminate()
    else:
        proc.send_signal(signal.SIGINT)

    try:
        await asyncio.wait_for(proc.wait(), timeout=30)
    except TimeoutError:
        log("Worker did not exit gracefully; killing it.")
        proc.kill()
        await proc.wait()


async def main() -> int:
    args = parse_args()
    run_id = os.getenv("GITHUB_RUN_ID") or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")

    if not args.work_pool:
        args.work_pool = f"windows-worker-repro-{run_id}-{attempt}"
    if not args.worker_name:
        hostname = socket.gethostname().lower()
        args.worker_name = f"gha-windows-{hostname}-{run_id}-{attempt}"

    log(f"Python: {sys.version}")
    log(f"Executable: {sys.executable}")
    log(f"Work pool: {args.work_pool}")
    log(f"Worker name: {args.worker_name}")

    created_pool = await ensure_work_pool(args.work_pool)
    env = os.environ.copy()
    env.update(
        {
            "PREFECT_LOGGING_LEVEL": "DEBUG",
            "PREFECT_WORKER_HEARTBEAT_SECONDS": str(args.heartbeat_seconds),
            "PREFECT_WORKER_QUERY_SECONDS": str(args.query_seconds),
            "PREFECT_WORKER_WEBSERVER_PORT": str(args.healthcheck_port),
            "PYTHONUNBUFFERED": "1",
        }
    )

    command = worker_command(args)
    log(f"Starting worker command: {' '.join(command)}")
    proc = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    output_task = asyncio.create_task(stream_output(proc, Path(args.worker_log_path)))

    observations: list[dict[str, Any]] = []
    try:
        await asyncio.sleep(15)
        observations = await monitor(args, proc)
    finally:
        await terminate_worker(proc)
        await output_task
        if created_pool and not args.keep_work_pool:
            await delete_work_pool(args.work_pool)

    unhealthy = [
        observation
        for observation in observations
        if observation["worker_process_returncode"] is not None
        or (
            observation["elapsed_seconds"] >= args.startup_grace_seconds
            and (
                observation["worker"] is None
                or observation["healthcheck"].startswith("ERROR")
                or not observation["healthcheck"].startswith("200")
                or "OFFLINE" in str(observation["worker"].get("status", ""))
            )
        )
    ]

    if unhealthy:
        log(f"Detected {len(unhealthy)} unhealthy observation(s).")
        log(f"First unhealthy observation: {unhealthy[0]!r}")
        return 1

    log("No unhealthy worker observations detected before the run ended.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

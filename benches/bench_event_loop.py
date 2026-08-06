"""Compare PREFECT_EVENT_LOOP choices on real flow workloads.

    PREFECT_EVENT_LOOP=zuvloop uv run --with zuvloop python benches/bench_event_loop.py

Runs each workload in a fresh subprocess per arm so the loop choice, settings,
and ephemeral server state cannot leak between measurements.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys

ARMS = ("asyncio", "zuvloop")
REPS = 5

WORKER = """
import asyncio, json, sys, time

from prefect import flow, task
from prefect._internal.loop_factory import run_coro
from prefect.utilities.processutils import run_process


@task
async def tick(i: int) -> int:
    return i


@task
async def launch() -> int:
    result = await run_process(["uv", "--version"])
    return result.returncode


@flow
async def many_tasks() -> None:
    async with asyncio.TaskGroup() as tg:
        for i in range(100):
            tg.create_task(tick(i))


@flow
async def process_churn() -> None:
    async with asyncio.TaskGroup() as tg:
        for _ in range(20):
            tg.create_task(launch())


async def main() -> None:
    workload = {"many_tasks": many_tasks, "process_churn": process_churn}[sys.argv[1]]
    await workload()  # warm the ephemeral server outside the measurement
    t0 = time.perf_counter()
    await workload()
    print(json.dumps({"seconds": time.perf_counter() - t0}))


run_coro(main())
"""


def measure(arm: str, workload: str) -> list[float]:
    times: list[float] = []
    for _ in range(REPS):
        env = os.environ | {
            "PREFECT_EVENT_LOOP": arm,
            "PREFECT_LOGGING_LEVEL": "CRITICAL",
        }
        out = subprocess.run(
            [sys.executable, "-c", WORKER, workload],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        times.append(json.loads(out.stdout.strip().splitlines()[-1])["seconds"])
    return times


def main() -> None:
    for workload in ("many_tasks", "process_churn"):
        print(workload)
        for arm in ARMS:
            times = measure(arm, workload)
            print(
                f"  {arm:8s} min {min(times) * 1000:8.1f}ms  "
                f"median {statistics.median(times) * 1000:8.1f}ms"
            )


if __name__ == "__main__":
    main()

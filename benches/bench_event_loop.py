"""Compare PREFECT_EVENT_LOOP choices on the loop-bound regions of real flows.

    uv run --with zuvloop python benches/bench_event_loop.py

Whole-flow timings are dominated by orchestration — sqlite, state transitions,
events — which no event loop can improve, and at that altitude every loop
measures the same. So each workload here runs inside a live flow (real engine,
real loop selection) but times only the region an event loop actually executes:
callback scheduling, subprocess spawn/reap, and pipe throughput.

Each arm runs in a fresh subprocess so loop choice and ephemeral server state
cannot leak between measurements, and arms are interleaved across rounds so
machine drift moves both equally.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys

ARMS = ("asyncio", "zuvloop")
ROUNDS = 5

WORKER = """
import asyncio, json, os, sys, time

from prefect import flow
from prefect._internal.loop_factory import run_with_selected_loop
from prefect.utilities.processutils import run_process


async def scheduling() -> float:
    # 10k wakeups: the timer/callback churn of a busy flow, without orchestration.
    async def hop(n: int) -> None:
        for _ in range(n):
            await asyncio.sleep(0)

    t0 = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
        for _ in range(10):
            tg.create_task(hop(1_000))
    return time.perf_counter() - t0


async def process_churn() -> float:
    # 50 concurrent launches through prefect's own run_process path.
    async def one() -> None:
        result = await run_process(["uv", "--version"])
        assert result.returncode == 0

    t0 = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
        for _ in range(50):
            tg.create_task(one())
    return time.perf_counter() - t0


async def pipe_throughput() -> float:
    # 32 MiB through a child's stdin/stdout pipes.
    payload = os.urandom(1 << 20)
    t0 = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        "cat",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate(payload * 32)
    assert len(stdout) == 32 << 20
    return time.perf_counter() - t0


WORKLOADS = {f.__name__: f for f in (scheduling, process_churn, pipe_throughput)}


@flow(name="loop-bench")
async def bench_flow(workload: str) -> float:
    await WORKLOADS[workload]()  # warm: interpreter, server, caches
    return await WORKLOADS[workload]()


async def main() -> None:
    seconds = await bench_flow(sys.argv[1])
    print(json.dumps({"seconds": seconds}))


run_with_selected_loop(main())
"""


def measure_once(arm: str, workload: str) -> float:
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
    return json.loads(out.stdout.strip().splitlines()[-1])["seconds"]


def main() -> None:
    for workload in ("scheduling", "process_churn", "pipe_throughput"):
        results: dict[str, list[float]] = {arm: [] for arm in ARMS}
        for _ in range(ROUNDS):
            for arm in ARMS:
                results[arm].append(measure_once(arm, workload))
        print(workload)
        for arm in ARMS:
            times = results[arm]
            print(
                f"  {arm:8s} min {min(times) * 1000:8.1f}ms  "
                f"median {statistics.median(times) * 1000:8.1f}ms"
            )
        ratio = statistics.median(results["asyncio"]) / statistics.median(
            results["zuvloop"]
        )
        print(f"  asyncio/zuvloop median: {ratio:.2f}x")


if __name__ == "__main__":
    main()

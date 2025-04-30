"""
regression test for #17686

before the fix a synchronous flow with
  • threadpooltaskrunner(max_workers=2)
  • a tag-concurrency limit of 2
  • a chain of tasks submitted in reverse (`wait_for`)
would dead-lock—each queued task grabbed its slot and its worker
thread before blocking on its dependency, so the root task never
got a thread.

calling `future.result(timeout=3)` makes the test self-timing:
if the bug re-appears the first `result()` raises `TimeoutError`
and the test fails.
"""

from __future__ import annotations

import asyncio
import time

from prefect import flow, task
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.futures import PrefectFuture
from prefect.task_runners import ThreadPoolTaskRunner

TAG = "deadlock-regression"


@task(tags=[TAG])
def sleeper(i: int) -> int:
    time.sleep(0.1)
    return i


async def _ensure_limit() -> None:
    LIMIT = 2
    async with get_client() as client:
        try:
            await client.reset_concurrency_limit_by_tag(TAG)
        except ObjectNotFound:
            pass
        await client.create_concurrency_limit(TAG, LIMIT)


@flow(task_runner=ThreadPoolTaskRunner(max_workers=2))
def reverse_chain(n: int) -> list[int]:
    asyncio.run(_ensure_limit())

    futures: list[PrefectFuture[int] | None] = [None] * n
    for i in range(n - 1, -1, -1):
        futures[i] = sleeper.submit(i, wait_for=[futures[i + 1]] if i + 1 < n else None)

    return [f.result(timeout=3) for f in futures if f is not None]


if __name__ == "__main__":
    N_TASKS = 3  # minimal chain that previously dead-locked
    out: list[int] = reverse_chain(N_TASKS)
    assert out == list(range(N_TASKS)), f"unexpected result {out!r}"
    print("reverse-chain flow completed without dead-lock")

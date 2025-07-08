import asyncio
import random

from prefect import flow, task


@task
async def dummy_task(j: int):
    await asyncio.sleep(random.randint(0, 2))
    return j


@flow
async def child_flow(i: int, n_tasks: int):
    await asyncio.gather(
        *[
            dummy_task.with_options(name=f"dummy-task-{i}-{j}")(j)
            for j in range(n_tasks)
        ]
    )


@flow
async def parent_flow(n_subflows: int, n_tasks_per_subflow: int):
    await asyncio.gather(
        *[
            child_flow.with_options(name=f"child_flow-{i}")(i, n_tasks_per_subflow)
            for i in range(n_subflows)
        ]
    )


def test_concurrent_subflows():
    result = asyncio.run(parent_flow(10, 10))
    # Test passes if the flow completes without error
    assert result is None  # Flow doesn't return anything, just completes

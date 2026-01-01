import asyncio

from prefect import flow, task


@task
async def dummy_task(j: int):
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
    # Use smaller numbers to reduce API overhead while still testing concurrent
    # subflow execution. The original 10x10 (100 tasks) caused timeouts in CI
    # due to orchestration overhead when running with pytest-xdist.
    result = asyncio.run(parent_flow(3, 3))
    assert result is None

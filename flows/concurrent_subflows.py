import asyncio
import random

from packaging.version import Version

import prefect
from prefect import flow, task

# Support for subflows with the same name was added in 2.10.6
# Support for the concurrent subflow fix in #10533 was released in 2.12.0
MINIMUM_VERSION = "2.12.0"


@task
async def dummy_task(j: int):
    await asyncio.sleep(random.randint(0, 2))
    return j


@flow
async def child_flow(i: int, n_tasks: int):
    for j in range(n_tasks):
        await dummy_task.with_options(name=f"dummy-task-{i}-{j}").submit(j)


@flow
async def parent_flow(n_subflows: int, n_tasks_per_subflow: int):
    await asyncio.gather(
        *[
            child_flow.with_options(name=f"child_flow-{i}")(i, n_tasks_per_subflow)
            for i in range(n_subflows)
        ]
    )


if __name__ == "__main__":
    if Version(prefect.__version__) >= Version(MINIMUM_VERSION):
        asyncio.run(parent_flow(10, 10))

import asyncio

from prefect import flow
from prefect.client.schemas.objects import (
    ConcurrencyLimitConfig,
    ConcurrencyLimitStrategy,
)
from prefect.deployments import deploy, run_deployment


@flow(log_prints=True)
async def parent():
    parallel_subflows = []
    for _ in range(0, 50):
        x = run_deployment(name="child/child")
        parallel_subflows.append(x)

    return await asyncio.gather(*parallel_subflows)


@flow(log_prints=True)
async def child():
    await asyncio.sleep(1000)


if __name__ == "__main__":
    parentflow_deployement = parent.to_deployment(
        name="parent",
        concurrency_limit=ConcurrencyLimitConfig(
            limit=1,
            collision_strategy=ConcurrencyLimitStrategy.ENQUEUE,
        ),
    )

    childflow_deployement = child.to_deployment(
        name="child",
        concurrency_limit=ConcurrencyLimitConfig(
            limit=5,
            collision_strategy=ConcurrencyLimitStrategy.CANCEL_NEW,
        ),
    )

    deployables = [parentflow_deployement, childflow_deployement]

    deploy(
        *deployables,
        work_pool_name="OSS-5929",
        image="prefecthq/prefect:latest",
        build=False,
        push=False,
    )

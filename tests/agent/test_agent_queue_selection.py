import random

import prefect.exceptions
from prefect.agent import PrefectAgent
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import WorkPool
from prefect.server.models.workers import DEFAULT_AGENT_WORK_POOL_NAME


async def _safe_get_or_create_workpool(
    client: PrefectClient, *, name: str, type=str
) -> WorkPool:
    try:
        pool = await client.create_work_pool(WorkPoolCreate(name=name, type=type))
    except prefect.exceptions.ObjectAlreadyExists:
        pool = await client.read_work_pool(name)
    return pool


async def test_get_work_queues_returns_default_queues(prefect_client: PrefectClient):
    # create WorkPools to associate with our WorkQueues
    default = await _safe_get_or_create_workpool(
        prefect_client, name=DEFAULT_AGENT_WORK_POOL_NAME, type="prefect-agent"
    )
    ecs = await _safe_get_or_create_workpool(prefect_client, name="ecs", type="ecs")
    agent_pool = await _safe_get_or_create_workpool(
        prefect_client, name="agent", type="prefect-agent"
    )

    # create WorkQueues, associating them with a pool at random
    expected = set()
    for i in range(10):
        random_pool = random.choice([default, ecs, agent_pool])
        q = await prefect_client.create_work_queue(
            name="test-{i}".format(i=i), work_pool_name=random_pool.name
        )
        if random_pool == default:
            expected.add(q.name)

    # create an agent with a prefix that matches all of the created queues
    async with PrefectAgent(work_queue_prefix=["test-"]) as agent:
        results = {q.name async for q in agent.get_work_queues()}

    # verify that only WorkQueues with in the default pool are returned for
    # this agent since it does not have a work pool name
    assert results == expected

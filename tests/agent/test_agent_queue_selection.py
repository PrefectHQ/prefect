from prefect.agent import PrefectAgent
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate


async def test_select_default_agent_queues_only_returns_default_queues(
    prefect_client: PrefectClient,
):
    p1 = await prefect_client.create_work_pool(WorkPoolCreate(name="t1", type="ecs"))
    p2 = await prefect_client.create_work_pool(
        WorkPoolCreate(name="t2", type="prefect-agent")
    )
    q1 = await prefect_client.create_work_queue(
        name="prod-deployment-1", work_pool_name=p1.name
    )
    q2 = await prefect_client.create_work_queue(
        name="prod-deployment-2", work_pool_name=p2.name
    )

    async with PrefectAgent(work_queues=[q1.name, q2.name]) as agent:
        results = await agent._select_default_agent_queues(prefect_client, [q1, q2])

    # verify we only selected the queue with the default "prefect-agent" work pool
    assert results == [q2]


async def test_get_work_queues_returns_default_queues(prefect_client: PrefectClient):
    import random

    from prefect.server.models.workers import DEFAULT_AGENT_WORK_POOL_NAME

    # delete the default WorkPool if it exists, otherwise WorkQueue queries will
    # always search within it
    try:
        await prefect_client.delete_work_pool(DEFAULT_AGENT_WORK_POOL_NAME)
    except Exception:
        pass

    # two WorkPools to associate with our WorkQueues
    p1 = await prefect_client.create_work_pool(WorkPoolCreate(name="p1", type="ecs"))
    agent_pool = await prefect_client.create_work_pool(
        WorkPoolCreate(name="p2", type="prefect-agent")
    )

    # create WorkQueues, associating them with a pool at random
    expected = set()
    for i in range(10):
        random_pool = random.choice([p1, agent_pool])
        q = await prefect_client.create_work_queue(
            name="test-{i}".format(i=i), work_pool_name=random_pool.name
        )
        if random_pool == agent_pool:
            expected.add(q.name)

    # create an agent with a prefix that matches all of the created queues
    async with PrefectAgent(work_queue_prefix=["test-"]) as agent:
        results = {q.name async for q in agent.get_work_queues()}

    # verify that only WorkQueues with a default pool type are returned for
    # this agent since it does not have a work pool name
    assert results == expected

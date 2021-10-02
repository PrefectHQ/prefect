from uuid import uuid4
from unittest.mock import MagicMock

import pendulum
import pytest

from prefect import flow
from prefect.agents import OrionAgent
from prefect.orion.schemas.core import FlowRun
from prefect.orion.schemas.states import Completed, Pending, Running, Scheduled
from prefect.utilities.compat import AsyncMock


async def test_agent_start_will_not_run_without_start():
    agent = OrionAgent(prefetch_seconds=1)
    mock = AsyncMock()
    with pytest.raises(RuntimeError, match="Agent is not started"):
        await agent.get_and_submit_flow_runs(query_fn=mock)

    mock.assert_not_called()


async def test_agent_start_and_shutdown():
    async with OrionAgent(prefetch_seconds=1) as agent:
        assert agent.started
        assert agent.task_group is not None
        agent.submitting_flow_run_ids.add("test")
    assert agent.submitting_flow_run_ids == set(), "Resets submitting flow run ids"
    assert agent.task_group is None, "Shuts down the task group"


async def test_agent_submittable_flow_run_filter(orion_client, deployment):
    @flow
    def foo():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment, state=state
        )
    )
    fr_id_1 = (await create_run_with_deployment(Pending())).id
    fr_id_2 = (
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        )
    ).id
    fr_id_3 = (
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        )
    ).id
    fr_id_4 = (
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        )
    ).id
    fr_id_5 = (
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        )
    ).id
    fr_id_6 = (await create_run_with_deployment(Running())).id
    fr_id_7 = (await create_run_with_deployment(Completed())).id
    fr_id_8 = (await orion_client.create_flow_run(foo, state=Scheduled())).id

    async with OrionAgent(prefetch_seconds=10) as agent:
        agent.submit_flow_run_to_subprocess = AsyncMock()  # do not actually run
        agent.submitting_flow_run_ids.add(fr_id_4)  # add a submitting id to check skip
        submitted_flow_runs = await agent.get_and_submit_flow_runs(
            query_fn=orion_client.read_flow_runs
        )

    submitted_flow_run_ids = {flow_run.id for flow_run in submitted_flow_runs}
    # Only include scheduled runs in the past or next prefetch seconds
    # Does not include runs without deployments
    assert submitted_flow_run_ids == {fr_id_2, fr_id_3}


async def test_agent_flow_run_submission():
    flow_run = FlowRun(
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        deployment_id=uuid4(),
        flow_id=uuid4(),
    )

    async def fake_query(sort, flow_run_filter):
        return [flow_run]

    mock_submit = AsyncMock()
    async with OrionAgent(prefetch_seconds=10) as agent:
        # Mock the lookup so we can assert that submit is called with the flow run
        agent.lookup_submission_method = MagicMock(return_value=mock_submit)
        await agent.get_and_submit_flow_runs(query_fn=fake_query)

    mock_submit.assert_awaited_once_with(flow_run, agent.submitted_callback)

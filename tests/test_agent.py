from unittest.mock import ANY, MagicMock
from uuid import uuid4

import pendulum
import pytest

from prefect import flow
from prefect.agent import OrionAgent
from prefect.flow_runners import SubprocessFlowRunner, UniversalFlowRunner, FlowRunner
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import Completed, Pending, Running, Scheduled
from prefect.exceptions import Abort
from prefect.utilities.compat import AsyncMock


def mock_flow_runner(runner_type, start_error=None):
    runner = MagicMock()

    def mark_as_started(flow_run, task_status):
        if start_error:
            raise start_error

        task_status.started()

    runner.submit_flow_run = AsyncMock(
        side_effect=mark_as_started, spec=FlowRunner.submit_flow_run
    )

    return runner


async def test_agent_start_will_not_run_without_start():
    agent = OrionAgent()
    mock = AsyncMock()
    with pytest.raises(RuntimeError, match="Agent is not started"):
        agent.client = mock
        await agent.get_and_submit_flow_runs()

    mock.assert_not_called()


async def test_agent_start_and_shutdown():
    async with OrionAgent() as agent:
        assert agent.started
        assert agent.task_group is not None
        assert agent.client is not None
        agent.submitting_flow_run_ids.add("test")
    assert agent.submitting_flow_run_ids == set(), "Resets submitting flow run ids"
    assert agent.task_group is None, "Shuts down the task group"
    assert agent.client is None, "Shuts down the client"


async def test_agent_submittable_flow_run_filter(orion_client, deployment):
    @flow
    def foo():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment.id, state=state
        )
    )

    flow_runs = [
        await create_run_with_deployment(Pending()),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        ),
        await create_run_with_deployment(Running()),
        await create_run_with_deployment(Completed()),
        await orion_client.create_flow_run(foo, state=Scheduled()),
    ]
    flow_run_ids = [run.id for run in flow_runs]

    async with OrionAgent(prefetch_seconds=10) as agent:
        agent.submit_run = AsyncMock()  # do not actually run
        agent.submitting_flow_run_ids.add(
            flow_run_ids[3]
        )  # add a submitting id to check skip
        submitted_flow_runs = await agent.get_and_submit_flow_runs()

    submitted_flow_run_ids = {flow_run.id for flow_run in submitted_flow_runs}
    # Only include scheduled runs in the past or next prefetch seconds
    # Does not include runs without deployments
    assert submitted_flow_run_ids == {flow_run_ids[1], flow_run_ids[2]}


async def test_agent_internal_submit_run_called(orion_client, deployment):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
    )

    async with OrionAgent(prefetch_seconds=10) as agent:
        agent.submit_run = AsyncMock()
        await agent.get_and_submit_flow_runs()

    agent.submit_run.assert_awaited_once_with(flow_run)


async def test_agent_submits_using_the_retrieved_flow_runner(orion_client, deployment):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    def mark_as_started(_, task_status):
        task_status.started()

    submit_flow_run = AsyncMock(side_effect=mark_as_started)

    async with OrionAgent(prefetch_seconds=10) as agent:
        agent.get_flow_runner = MagicMock()
        agent.get_flow_runner().submit_flow_run = submit_flow_run
        await agent.get_and_submit_flow_runs()

    agent.get_flow_runner().submit_flow_run.assert_awaited_once_with(
        flow_run, task_status=ANY
    )


async def test_agent_submit_run_sets_pending_state(orion_client, deployment):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    def mark_as_started(_, task_status):
        task_status.started()

    async with OrionAgent(prefetch_seconds=10) as agent:
        # Create a mock flow runner
        agent.get_flow_runner = MagicMock()
        agent.get_flow_runner().submit_flow_run = AsyncMock(side_effect=mark_as_started)
        agent.submitting_flow_run_ids.add(flow_run.id)

        await agent.submit_run(flow_run)

    assert (await orion_client.read_flow_run(flow_run.id)).state.is_pending()
    agent.get_flow_runner().submit_flow_run.assert_awaited_once()


async def test_agent_submit_run_waits_for_scheduled_time_before_submitting(
    orion_client, deployment, monkeypatch
):
    # TODO: We should abstract this now/sleep pattern into fixtures for resuse
    #       as there are a few other locations we want to test sleeps without
    #       actually sleeping
    now = pendulum.now("utc")

    def get_now(*args):
        return now

    def move_forward_in_time(seconds):
        nonlocal now
        now = now.add(seconds=seconds)

    sleep = AsyncMock(side_effect=move_forward_in_time)
    monkeypatch.setattr("pendulum.now", get_now)
    monkeypatch.setattr("anyio.sleep", sleep)

    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=now.add(seconds=10)),
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    def mark_as_started(_, task_status):
        task_status.started()

    async with OrionAgent(prefetch_seconds=10) as agent:
        # Create a mock flow runner
        agent.get_flow_runner = MagicMock()
        agent.get_flow_runner().submit_flow_run = AsyncMock(side_effect=mark_as_started)
        agent.submitting_flow_run_ids.add(flow_run.id)

        await agent.submit_run(flow_run)

    sleep.assert_awaited_once_with(10)
    state = (await orion_client.read_flow_run(flow_run.id)).state
    assert state.timestamp >= flow_run.state.state_details.scheduled_time
    assert state.is_pending()
    agent.get_flow_runner().submit_flow_run.assert_called_once()


@pytest.mark.parametrize("return_state", [Scheduled(), Running()])
async def test_agent_submit_run_aborts_if_server_returns_non_pending_state(
    orion_client, deployment, return_state
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    def mark_as_started(_, task_status):
        task_status.started()

    async with OrionAgent(prefetch_seconds=10) as agent:
        # Create a mock flow runner
        agent.get_flow_runner = MagicMock()
        agent.get_flow_runner.submit_flow_run = AsyncMock(side_effect=mark_as_started)
        agent.submitting_flow_run_ids.add(flow_run.id)
        agent.logger = MagicMock()

        agent.client.propose_state = AsyncMock(return_value=return_state)
        await agent.submit_run(flow_run)

    agent.get_flow_runner().submit_flow_run.assert_not_called()
    assert flow_run.id not in agent.submitting_flow_run_ids
    agent.logger.info.assert_called_with(
        f"Aborted submission of flow run '{flow_run.id}': "
        f"Server returned a non-pending state '{return_state.type.value}'"
    )


async def test_agent_submit_run_aborts_if_flow_run_is_missing(orion_client, deployment):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    # TODO: The client cannot delete flow runs yet, change the id instead
    flow_run.id = uuid4()

    def mark_as_started(_, task_status):
        task_status.started()

    async with OrionAgent(prefetch_seconds=10) as agent:
        # Create a mock flow runner
        agent.get_flow_runner = MagicMock()
        agent.get_flow_runner.submit_flow_run = AsyncMock(side_effect=mark_as_started)
        agent.submitting_flow_run_ids.add(flow_run.id)
        agent.logger = MagicMock()

        await agent.submit_run(flow_run)

    agent.get_flow_runner().submit_flow_run.assert_not_called()
    assert flow_run.id not in agent.submitting_flow_run_ids
    agent.logger.error.assert_called_with(
        f"Failed to update state of flow run '{flow_run.id}'",
        exc_info=True,
    )


async def test_agent_submit_run_aborts_without_raising_if_server_raises_abort(
    orion_client, deployment
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    def mark_as_started(_, task_status):
        task_status.started()

    async with OrionAgent(prefetch_seconds=10) as agent:
        # Create a mock flow runner
        agent.get_flow_runner = MagicMock()
        agent.get_flow_runner.submit_flow_run = AsyncMock(side_effect=mark_as_started)
        agent.submitting_flow_run_ids.add(flow_run.id)
        agent.logger = MagicMock()

        agent.client.propose_state = AsyncMock(side_effect=Abort("message"))
        await agent.submit_run(flow_run)

    agent.get_flow_runner().submit_flow_run.assert_not_called()
    assert flow_run.id not in agent.submitting_flow_run_ids
    agent.logger.info.assert_called_with(
        f"Aborted submission of flow run '{flow_run.id}'. "
        "Server sent an abort signal: message"
    )


async def test_agent_fails_flow_if_flow_runner_submission_fails(
    orion_client, deployment
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    submit_flow_run = AsyncMock(side_effect=ValueError("Hello!"))

    async with OrionAgent(prefetch_seconds=10) as agent:
        agent.get_flow_runner = MagicMock()
        agent.get_flow_runner().submit_flow_run = submit_flow_run
        agent.logger = MagicMock()
        await agent.get_and_submit_flow_runs()

    agent.get_flow_runner().submit_flow_run.assert_awaited_once_with(
        flow_run, task_status=ANY
    )
    agent.logger.error.assert_called_once_with(
        f"Flow runner failed to submit flow run '{flow_run.id}'", exc_info=True
    )

    state = (await orion_client.read_flow_run(flow_run.id)).state
    assert state.is_failed()
    result = await orion_client.resolve_datadoc(state.data)
    with pytest.raises(ValueError, match="Hello!"):
        raise result


async def test_agent_fails_flow_if_flow_runner_does_not_mark_as_started(
    orion_client, deployment
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    # This excludes calling `task_status.started()` which will throw an anyio error
    # when submission finishes without calling `started()`. The agent will treat
    # submission the same as if it had thrown an error.
    submit_flow_run = AsyncMock()

    async with OrionAgent(prefetch_seconds=10) as agent:
        agent.get_flow_runner = MagicMock()
        agent.get_flow_runner().submit_flow_run = submit_flow_run
        agent.logger = MagicMock()
        await agent.get_and_submit_flow_runs()

    agent.get_flow_runner().submit_flow_run.assert_awaited_once_with(
        flow_run, task_status=ANY
    )
    agent.logger.error.assert_called_once_with(
        f"Flow runner failed to submit flow run '{flow_run.id}'", exc_info=True
    )

    state = (await orion_client.read_flow_run(flow_run.id)).state
    assert state.is_failed()
    result = await orion_client.resolve_datadoc(state.data)
    with pytest.raises(
        RuntimeError, match="Child exited without calling task_status.started"
    ):
        raise result


async def test_agent_dispatches_null_flow_runner_to_subprocess_runner(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    flow_data = DataDocument.encode("cloudpickle", foo)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        flow_data=flow_data,
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment_id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
    )

    agent = OrionAgent(prefetch_seconds=10)
    assert agent.get_flow_runner(flow_run) == SubprocessFlowRunner(env={"foo": "bar"})


async def test_agent_dispatches_universal_flow_run_to_subproccess_runner(
    orion_client, deployment
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    agent = OrionAgent(prefetch_seconds=10)
    assert agent.get_flow_runner(flow_run) == SubprocessFlowRunner(env={"foo": "bar"})


async def test_agent_dispatches_to_given_runner(orion_client, deployment):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
        flow_runner=SubprocessFlowRunner(env={"foo": "bar"}),
    )

    agent = OrionAgent(prefetch_seconds=10)
    assert agent.get_flow_runner(flow_run) == SubprocessFlowRunner(env={"foo": "bar"})

from typing import Generator
from unittest.mock import call

import anyio
import pytest

from prefect.agent import OrionAgent
from prefect.blocks.core import Block
from prefect.client.orion import OrionClient
from prefect.exceptions import InfrastructureNotAvailable, InfrastructureNotFound
from prefect.infrastructure.base import Infrastructure
from prefect.orion.database.orm_models import ORMDeployment
from prefect.orion.schemas.core import Deployment
from prefect.states import Cancelled, Completed, Pending, Running, Scheduled
from prefect.testing.utilities import AsyncMock
from prefect.utilities.dispatch import get_registry_for_type


async def _create_test_deployment_from_orm(
    orion_client: OrionClient, orm_deployment: ORMDeployment, **kwargs
) -> Deployment:
    api_deployment = Deployment.from_orm(orm_deployment)
    updated_deployment = api_deployment.copy(update=kwargs)

    deployment_id = await orion_client.create_deployment(
        **updated_deployment.dict(
            exclude=api_deployment._reset_fields().union(
                {"is_schedule_active", "created_by", "updated_by"}
            )
        )
    )

    updated_deployment.id = deployment_id
    return updated_deployment


# Test cancellation is called for the correct flow runs  -------------------------------


async def test_agent_cancel_run_called_for_cancelling_run(
    orion_client: OrionClient, deployment: ORMDeployment
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        agent.cancel_run = AsyncMock()
        await agent.check_for_cancelled_flow_runs()

    agent.cancel_run.assert_awaited_once_with(flow_run)


@pytest.mark.parametrize(
    "state",
    [
        # Name not "Cancelling"
        Cancelled(),
        # Name "Cancelling" but type not "Cancelled"
        Completed(name="Cancelling"),
        # Type not Cancelled
        Scheduled(),
        Pending(),
        Running(),
    ],
)
async def test_agent_cancel_run_not_called_for_other_states(
    orion_client: OrionClient, deployment: ORMDeployment, state
):
    await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=state,
    )

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        agent.cancel_run = AsyncMock()
        await agent.check_for_cancelled_flow_runs()

    agent.cancel_run.assert_not_called()


async def test_agent_cancel_run_called_for_cancelling_run_with_multiple_work_queues(
    orion_client: OrionClient, deployment: ORMDeployment
):
    deployment.work_queue_name = "foo"
    await orion_client.update_deployment(deployment)

    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )

    async with OrionAgent(work_queues=["foo", "bar"], prefetch_seconds=10) as agent:
        agent.cancel_run = AsyncMock()
        await agent.check_for_cancelled_flow_runs()

    agent.cancel_run.assert_awaited_once_with(flow_run)


async def test_agent_cancel_run_called_for_each_cancelling_run_in_multiple_work_queues(
    orion_client: OrionClient, deployment: ORMDeployment
):
    deployment_foo = await _create_test_deployment_from_orm(
        orion_client, deployment, work_queue_name="foo"
    )
    deployment_bar = await _create_test_deployment_from_orm(
        orion_client, deployment, work_queue_name="bar"
    )

    flow_run_foo = await orion_client.create_flow_run_from_deployment(
        deployment_foo.id,
        state=Cancelled(name="Cancelling"),
    )
    flow_run_bar = await orion_client.create_flow_run_from_deployment(
        deployment_bar.id,
        state=Cancelled(name="Cancelling"),
    )

    async with OrionAgent(work_queues=["foo", "bar"], prefetch_seconds=10) as agent:
        agent.cancel_run = AsyncMock()
        await agent.check_for_cancelled_flow_runs()

    agent.cancel_run.assert_has_awaits(
        [call(flow_run_foo), call(flow_run_bar)], any_order=True
    )


async def test_agent_cancel_run_called_for_each_cancelling_run_in_a_work_queue(
    orion_client: OrionClient, deployment: ORMDeployment
):
    deployment_foo = await _create_test_deployment_from_orm(
        orion_client, deployment, work_queue_name="foo"
    )

    flow_run_1 = await orion_client.create_flow_run_from_deployment(
        deployment_foo.id,
        state=Cancelled(name="Cancelling"),
    )
    flow_run_2 = await orion_client.create_flow_run_from_deployment(
        deployment_foo.id,
        state=Cancelled(name="Cancelling"),
    )
    flow_run_3 = await orion_client.create_flow_run_from_deployment(
        deployment_foo.id,
        state=Cancelled(name="Cancelling"),
    )

    async with OrionAgent(work_queues=["foo"], prefetch_seconds=10) as agent:
        agent.cancel_run = AsyncMock()
        await agent.check_for_cancelled_flow_runs()

    agent.cancel_run.assert_has_awaits(
        [call(flow_run_1), call(flow_run_2), call(flow_run_3)], any_order=True
    )


async def test_agent_cancel_run_not_called_for_other_work_queues(
    orion_client: OrionClient, deployment
):
    await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )

    async with OrionAgent(
        work_queues=[f"not-{deployment.work_queue_name}"], prefetch_seconds=10
    ) as agent:
        agent.cancel_run = AsyncMock()
        await agent.check_for_cancelled_flow_runs()

    agent.cancel_run.assert_not_called()


# Test enforcement of cancellation  ----------------------------------------------------


@pytest.fixture
def mock_infrastructure_kill(monkeypatch) -> Generator[AsyncMock, None, None]:
    """
    Mocks all subtype implementations of `Infrastructure.kill`.
    """
    mock = AsyncMock()

    # Patch all infrastructure types
    types = get_registry_for_type(Block)
    for t in types.values():
        if not issubclass(t, Infrastructure):
            continue
        monkeypatch.setattr(t, "kill", mock, raising=False)

    yield mock


async def test_agent_cancel_run_kills_run_with_infrastructure_pid(
    orion_client: OrionClient,
    deployment: ORMDeployment,
    mock_infrastructure_kill: AsyncMock,
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )

    await orion_client.update_flow_run(flow_run.id, infrastructure_pid="test")

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        await agent.check_for_cancelled_flow_runs()

    mock_infrastructure_kill.assert_awaited_once_with("test")


async def test_agent_cancel_run_with_missing_infrastructure_pid(
    orion_client: OrionClient,
    deployment: ORMDeployment,
    mock_infrastructure_kill: AsyncMock,
    caplog,
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        await agent.check_for_cancelled_flow_runs()

    mock_infrastructure_kill.assert_not_awaited()

    # State name updated to prevent further attempts
    post_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert post_flow_run.state.name == "Cancelled"

    # Information broadcasted to user in logs and state message
    assert (
        "does not have an infrastructure pid attached. Cancellation cannot be guaranteed."
        in caplog.text
    )
    assert "missing infrastructure tracking information" in post_flow_run.state.message


@pytest.mark.usefixtures("mock_infrastructure_kill")
async def test_agent_cancel_run_updates_state_name(
    orion_client: OrionClient,
    deployment: ORMDeployment,
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )

    await orion_client.update_flow_run(flow_run.id, infrastructure_pid="test")

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        await agent.check_for_cancelled_flow_runs()

    post_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert post_flow_run.state.name == "Cancelled"


@pytest.mark.usefixtures("mock_infrastructure_kill")
async def test_agent_cancel_run_preserves_other_state_properties(
    orion_client: OrionClient,
    deployment: ORMDeployment,
):
    expected_changed_fields = {"name", "timestamp", "id"}

    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling", message="test"),
    )

    await orion_client.update_flow_run(flow_run.id, infrastructure_pid="test")

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        await agent.check_for_cancelled_flow_runs()

    post_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert post_flow_run.state.dict(
        exclude=expected_changed_fields
    ) == flow_run.state.dict(exclude=expected_changed_fields)


async def test_agent_cancel_run_with_infrastructure_not_available_during_kill(
    orion_client: OrionClient,
    deployment: ORMDeployment,
    mock_infrastructure_kill: AsyncMock,
    caplog,
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )

    await orion_client.update_flow_run(flow_run.id, infrastructure_pid="test")
    mock_infrastructure_kill.side_effect = InfrastructureNotAvailable("Test!")

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        await agent.check_for_cancelled_flow_runs()
        # Perform a second call to check that it is tracked locally that this agent
        # should not try again
        await agent.check_for_cancelled_flow_runs()

    # Only awaited once
    mock_infrastructure_kill.assert_awaited_once_with("test")

    # State name not updated; other agents may attempt the kill
    post_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert post_flow_run.state.name == "Cancelling"

    # Exception message is included with note on agent action
    assert "Test! Flow run cannot be cancelled by this agent." in caplog.text

    # State message is not changed
    assert post_flow_run.state.message is None


async def test_agent_cancel_run_with_infrastructure_not_found_during_kill(
    orion_client: OrionClient,
    deployment: ORMDeployment,
    mock_infrastructure_kill: AsyncMock,
    caplog,
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )

    await orion_client.update_flow_run(flow_run.id, infrastructure_pid="test")
    mock_infrastructure_kill.side_effect = InfrastructureNotFound("Test!")

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        await agent.check_for_cancelled_flow_runs()
        # Perform a second call to check that another cancellation attempt is not made
        await agent.check_for_cancelled_flow_runs()

    # Only awaited once
    mock_infrastructure_kill.assert_awaited_once_with("test")

    # State name updated to prevent further attempts
    post_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert post_flow_run.state.name == "Cancelled"

    # Exception message is included with note on agent action
    assert "Test! Marking flow run as cancelled." in caplog.text

    # No need for state message update
    assert post_flow_run.state.message is None


async def test_agent_cancel_run_with_unknown_error_during_kill(
    orion_client: OrionClient,
    deployment: ORMDeployment,
    mock_infrastructure_kill: AsyncMock,
    caplog,
):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )
    await orion_client.update_flow_run(flow_run.id, infrastructure_pid="test")
    mock_infrastructure_kill.side_effect = ValueError("Oh no!")

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        await agent.check_for_cancelled_flow_runs()
        await anyio.sleep(0.5)
        await agent.check_for_cancelled_flow_runs()

    # Multiple attempts should be made
    mock_infrastructure_kill.assert_has_awaits([call("test"), call("test")])

    # State name not updated
    post_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert post_flow_run.state.name == "Cancelling"

    assert (
        "Encountered exception while killing infrastructure for flow run" in caplog.text
    )
    assert "ValueError: Oh no!" in caplog.text
    assert "Traceback" in caplog.text


async def test_agent_cancel_run_without_infrastructure_support_for_kill(
    orion_client: OrionClient, deployment: ORMDeployment, caplog, monkeypatch
):

    # Patch all infrastructure types
    types = get_registry_for_type(Block)
    for t in types.values():
        if not issubclass(t, Infrastructure):
            continue
        monkeypatch.delattr(t, "kill", raising=False)

    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Cancelled(name="Cancelling"),
    )
    await orion_client.update_flow_run(flow_run.id, infrastructure_pid="test")

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        await agent.check_for_cancelled_flow_runs()

    # State name not updated; another agent may have a code version that supports
    # killing this flow run
    post_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert post_flow_run.state.name == "Cancelling"

    assert (
        "infrastructure 'process' does not support killing created infrastructure."
        in caplog.text
    )
    assert "Cancellation cannot be guaranteed." in caplog.text

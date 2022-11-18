from unittest.mock import MagicMock

import pendulum
import pytest

from prefect import flow
from prefect.agent import OrionAgent
from prefect.blocks.core import Block
from prefect.exceptions import Abort, FailedRun
from prefect.infrastructure.base import Infrastructure
from prefect.orion import models, schemas
from prefect.states import Completed, Pending, Running, Scheduled
from prefect.testing.utilities import AsyncMock
from prefect.utilities.dispatch import get_registry_for_type


@pytest.fixture
def prefect_caplog(caplog):
    # TODO: Determine a better pattern for this and expose for all tests
    import logging

    logger = logging.getLogger("prefect")
    logger.propagate = True

    try:
        yield caplog
    finally:
        logger.propagate = False


async def test_agent_start_will_not_run_without_start():
    agent = OrionAgent(work_queues=["foo"])
    mock = AsyncMock()
    with pytest.raises(RuntimeError, match="Agent is not started"):
        agent.client = mock
        await agent.get_and_submit_flow_runs()

    mock.assert_not_called()


async def test_agent_start_and_shutdown():
    async with OrionAgent(work_queues=["foo"]) as agent:
        assert agent.started
        assert agent.task_group is not None
        assert agent.client is not None
        agent.submitting_flow_run_ids.add("test")
    assert agent.submitting_flow_run_ids == set(), "Resets submitting flow run ids"
    assert agent.task_group is None, "Shuts down the task group"
    assert agent.client is None, "Shuts down the client"


async def test_agent_with_work_queue(orion_client, deployment):
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

    # Pull runs from the work queue to get expected runs
    work_queue = await orion_client.read_work_queue_by_name(deployment.work_queue_name)
    work_queue_runs = await orion_client.get_runs_in_work_queue(
        work_queue.id, scheduled_before=pendulum.now().add(seconds=10)
    )
    work_queue_flow_run_ids = {run.id for run in work_queue_runs}

    # Should only include scheduled runs in the past or next prefetch seconds
    # Should not include runs without deployments
    assert work_queue_flow_run_ids == set(flow_run_ids[1:4])

    agent = OrionAgent(work_queues=[work_queue.name], prefetch_seconds=10)

    async with agent:
        agent.submit_run = AsyncMock()  # do not actually run anything
        submitted_flow_runs = await agent.get_and_submit_flow_runs()

    submitted_flow_run_ids = {flow_run.id for flow_run in submitted_flow_runs}
    assert submitted_flow_run_ids == work_queue_flow_run_ids


async def test_agent_matches_work_queues_dynamically(
    session, work_queue, prefect_caplog
):
    name = "wq-1"
    assert await models.work_queues.read_work_queue_by_name(session=session, name=name)
    async with OrionAgent(work_queue_prefix=["wq-"]) as agent:
        assert name not in agent.work_queues
        await agent.get_and_submit_flow_runs()
        assert name in agent.work_queues

    assert f"Matched new work queues: {name}" in prefect_caplog.text


async def test_agent_matches_multiple_work_queues_dynamically(
    session, orion_client, prefect_caplog
):
    prod1 = "prod-deployment-1"
    prod2 = "prod-deployment-2"
    prod3 = "prod-deployment-3"
    dev1 = "dev-data-producer"
    await orion_client.create_work_queue(name=prod1)
    await orion_client.create_work_queue(name=prod2)

    async with OrionAgent(work_queue_prefix=["prod-"]) as agent:
        assert not agent.work_queues
        await agent.get_and_submit_flow_runs()
        assert prod1 in agent.work_queues
        assert prod2 in agent.work_queues

        # bypass work_queue caching
        agent._work_queue_cache_expiration = pendulum.now("UTC") - pendulum.duration(
            minutes=1
        )
        await orion_client.create_work_queue(name=prod3)
        await orion_client.create_work_queue(name=dev1)
        await agent.get_and_submit_flow_runs()
        assert prod3 in agent.work_queues
        assert (
            dev1 not in agent.work_queues
        ), "work queue matcher should not match partial names"


async def test_agent_matches_multiple_work_queue_prefixes(
    session, orion_client, prefect_caplog
):
    prod = "prod-deployment"
    dev = "dev-data-producer"
    await orion_client.create_work_queue(name=prod)
    await orion_client.create_work_queue(name=dev)

    async with OrionAgent(work_queue_prefix=["prod-", "dev-"]) as agent:
        assert not agent.work_queues
        await agent.get_and_submit_flow_runs()
        assert prod in agent.work_queues
        assert dev in agent.work_queues


async def test_matching_work_queues_handes_work_queue_deletion(
    session, work_queue, orion_client, prefect_caplog
):
    name = "wq-1"
    assert await models.work_queues.read_work_queue_by_name(session=session, name=name)
    async with OrionAgent(work_queue_prefix=["wq-"]) as agent:
        await agent.get_and_submit_flow_runs()
        assert name in agent.work_queues

        # bypass work_queue caching
        agent._work_queue_cache_expiration = pendulum.now("UTC") - pendulum.duration(
            minutes=1
        )
        await orion_client.delete_work_queue_by_id(work_queue.id)
        await agent.get_and_submit_flow_runs()
        assert name not in agent.work_queues

    assert f"Matched new work queues: {name}" in prefect_caplog.text
    assert f"Work queues no longer matched: {name}" in prefect_caplog.text


async def test_agent_creates_work_queue_if_doesnt_exist(session, prefect_caplog):
    name = "hello-there"
    assert not await models.work_queues.read_work_queue_by_name(
        session=session, name=name
    )
    async with OrionAgent(work_queues=[name]) as agent:
        await agent.get_and_submit_flow_runs()
    assert await models.work_queues.read_work_queue_by_name(session=session, name=name)

    assert f"Created work queue '{name}'." in prefect_caplog.text


async def test_agent_does_not_create_work_queues_if_matching_with_prefix(
    session, prefect_caplog
):
    name = "hello-there"
    assert not await models.work_queues.read_work_queue_by_name(
        session=session, name=name
    )
    async with OrionAgent(work_queues=[name]) as agent:
        agent.work_queue_prefix = ["goodbye-"]
        await agent.get_and_submit_flow_runs()
    assert not await models.work_queues.read_work_queue_by_name(
        session=session, name=name
    )
    assert f"Created work queue '{name}'." not in prefect_caplog.text


async def test_agent_gracefully_handles_error_when_creating_work_queue(
    session, monkeypatch, prefect_caplog
):
    """
    Mimics a race condition in which multiple agents were started against the
    same (nonexistent) queue. All agents would fail to read the queue and all
    would attempt to create it, but only one would create it successfully; the
    others would get an error because it already exists. In that case, we want to handle the error gracefully.
    """
    name = "hello-there"
    assert not await models.work_queues.read_work_queue_by_name(
        session=session, name=name
    )

    # prevent work queue creation
    async def bad_create(self, name):
        raise ValueError("No!")

    monkeypatch.setattr("prefect.client.OrionClient.create_work_queue", bad_create)

    async with OrionAgent(work_queues=[name]) as agent:
        await agent.get_and_submit_flow_runs()

    # work queue was not created
    assert not await models.work_queues.read_work_queue_by_name(
        session=session, name=name
    )

    assert "No!" in prefect_caplog.text


async def test_agent_caches_work_queues(orion_client, deployment, monkeypatch):
    work_queue = await orion_client.read_work_queue_by_name(deployment.work_queue_name)

    async def read_queue(name):
        return work_queue

    mock = AsyncMock(side_effect=read_queue)
    monkeypatch.setattr("prefect.client.OrionClient.read_work_queue_by_name", mock)

    async with OrionAgent(work_queues=[work_queue.name], prefetch_seconds=10) as agent:

        await agent.get_and_submit_flow_runs()
        mock.assert_awaited_once()

        await agent.get_and_submit_flow_runs()
        # the mock was not awaited again
        mock.assert_awaited_once()

        assert agent._work_queue_cache[0].id == work_queue.id


async def test_agent_with_work_queue_name_survives_queue_deletion(
    orion_client, deployment
):
    """Ensure that cached work queues don't create errors if deleted"""
    work_queue = await orion_client.read_work_queue_by_name(deployment.work_queue_name)

    async with OrionAgent(work_queues=[work_queue.name], prefetch_seconds=10) as agent:
        agent.submit_run = AsyncMock()  # do not actually run

        await agent.get_and_submit_flow_runs()

        # delete the work queue
        await orion_client.delete_work_queue_by_id(work_queue.id)

        # gracefully handled
        await agent.get_and_submit_flow_runs()


async def test_agent_internal_submit_run_called(orion_client, deployment):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
    )

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        agent.submit_run = AsyncMock()
        await agent.get_and_submit_flow_runs()

    agent.submit_run.assert_called_once_with(flow_run)


async def test_agent_runs_multiple_work_queues(orion_client, session, flow):
    # create two deployments
    deployment_a = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="deployment-a",
            flow_id=flow.id,
            work_queue_name="a",
        ),
    )
    deployment_b = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="deployment-b",
            flow_id=flow.id,
            work_queue_name="b",
        ),
    )
    await session.commit()

    # create two runs
    flow_run_a = await orion_client.create_flow_run_from_deployment(
        deployment_a.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
    )
    flow_run_b = await orion_client.create_flow_run_from_deployment(
        deployment_b.id,
        state=Scheduled(scheduled_time=pendulum.now("utc")),
    )

    async with OrionAgent(
        work_queues=[deployment_a.work_queue_name, deployment_b.work_queue_name],
        prefetch_seconds=10,
    ) as agent:
        agent.submit_run = AsyncMock()
        await agent.get_and_submit_flow_runs()

    # runs from both queues were submitted
    assert {flow_run_a.id, flow_run_b.id} == {
        agent.submit_run.call_args_list[0][0][0].id,
        agent.submit_run.call_args_list[1][0][0].id,
    }


class TestInfrastructureIntegration:
    @pytest.fixture
    def mock_infrastructure_run(self, monkeypatch) -> MagicMock:
        """
        Mocks all subtype implementations of `Infrastructure.run`.

        Yields a mock that is called with `self.dict()` when `run`
        is awaited. The mock provides a few utilities for testing
        error handling.

        `pre_start_side_effect` and `post_start_side_effect` may be
        set to callables to perform actions before or after the
        task is reported as started.

        `mark_as_started` may be set to `False` to prevent marking the
        task as started.
        """
        mock = MagicMock()
        mock.pre_start_side_effect = lambda: None
        mock.post_start_side_effect = lambda: None
        mock.mark_as_started = True

        async def mock_run(self, task_status=None):
            # Record the call immediately
            result = mock(self.dict())

            # Perform side-effects for testing error handling

            mock.pre_start_side_effect()

            if mock.mark_as_started:
                task_status.started()

            mock.post_start_side_effect()

            return result

        # Patch all infrastructure types
        types = get_registry_for_type(Block)
        for t in types.values():
            if not issubclass(t, Infrastructure):
                continue
            monkeypatch.setattr(t, "run", mock_run)

        yield mock

    @pytest.fixture
    def mock_propose_state(self, monkeypatch):
        mock = AsyncMock()
        monkeypatch.setattr("prefect.agent.propose_state", mock)

        yield mock

    async def test_agent_submits_using_the_retrieved_infrastructure(
        self, orion_client, deployment, mock_infrastructure_run
    ):
        infra_doc_id = deployment.infrastructure_document_id

        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc")),
        )
        flow = await orion_client.read_flow(deployment.flow_id)

        infra_document = await orion_client.read_block_document(infra_doc_id)
        infrastructure = Block._from_block_document(infra_document)
        async with OrionAgent(
            work_queues=[deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            await agent.get_and_submit_flow_runs()

        mock_infrastructure_run.assert_called_once_with(
            infrastructure.prepare_for_flow_run(
                flow_run, deployment=deployment, flow=flow
            ).dict()
        )

    async def test_agent_submit_run_sets_pending_state(
        self, orion_client, deployment, mock_infrastructure_run
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc")),
        )

        async with OrionAgent(
            work_queues=[deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            await agent.get_and_submit_flow_runs()

        flow_run = await orion_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_pending()
        mock_infrastructure_run.assert_called_once()

    async def test_agent_submit_run_waits_for_scheduled_time_before_submitting(
        self,
        orion_client,
        deployment,
        mock_infrastructure_run,
        monkeypatch,
        mock_anyio_sleep,
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc").add(seconds=10)),
        )

        async with OrionAgent(
            work_queues=[deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            agent.submitting_flow_run_ids.add(flow_run.id)
            with mock_anyio_sleep.assert_sleeps_for(10):
                await agent.submit_run(flow_run)

        state = (await orion_client.read_flow_run(flow_run.id)).state
        # Note that we include a 1 second buffer to account for rounding in the WAIT
        # instruction
        assert (
            state.timestamp.add(seconds=1)
            >= flow_run.state.state_details.scheduled_time
        ), "Pending state time should be after the scheduled time"
        assert state.is_pending()
        mock_infrastructure_run.assert_called_once()

    @pytest.mark.parametrize("return_state", [Scheduled(), Running()])
    async def test_agent_submit_run_aborts_if_server_returns_non_pending_state(
        self,
        orion_client,
        deployment,
        mock_infrastructure_run,
        return_state,
        mock_propose_state,
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc")),
        )

        async with OrionAgent(
            work_queues=[deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            agent.submitting_flow_run_ids.add(flow_run.id)
            agent.logger = MagicMock()

            mock_propose_state.return_value = return_state
            await agent.submit_run(flow_run)

        mock_infrastructure_run.assert_not_called()
        assert flow_run.id not in agent.submitting_flow_run_ids
        agent.logger.info.assert_called_with(
            f"Aborted submission of flow run '{flow_run.id}': "
            f"Server returned a non-pending state '{return_state.type.value}'"
        )

    async def test_agent_submit_run_aborts_if_flow_run_is_missing(
        self, orion_client, deployment, mock_infrastructure_run
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc")),
        )

        await orion_client.delete_flow_run(flow_run.id)

        async with OrionAgent(
            work_queues=[deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            agent.submitting_flow_run_ids.add(flow_run.id)
            agent.logger = MagicMock()

            await agent.submit_run(flow_run)

        mock_infrastructure_run.assert_not_called()
        assert flow_run.id not in agent.submitting_flow_run_ids
        agent.logger.error.assert_called_with(
            f"Failed to update state of flow run '{flow_run.id}'",
            exc_info=True,
        )

    async def test_agent_submit_run_aborts_without_raising_if_server_raises_abort(
        self, orion_client, deployment, mock_infrastructure_run, mock_propose_state
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc")),
        )

        async with OrionAgent(
            work_queues=[deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            agent.submitting_flow_run_ids.add(flow_run.id)
            agent.logger = MagicMock()
            mock_propose_state.side_effect = Abort("message")

            await agent.submit_run(flow_run)

        mock_infrastructure_run.assert_not_called()
        assert flow_run.id not in agent.submitting_flow_run_ids
        agent.logger.info.assert_called_with(
            f"Aborted submission of flow run '{flow_run.id}'. "
            "Server sent an abort signal: message"
        )

    async def test_agent_fails_flow_if_get_infrastructure_fails(
        self, orion_client, deployment, mock_infrastructure_run
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc")),
        )

        async with OrionAgent(
            work_queues=[deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            agent.submitting_flow_run_ids.add(flow_run.id)
            agent.logger = MagicMock()
            agent.get_infrastructure = AsyncMock(side_effect=ValueError("Bad!"))

            await agent.submit_run(flow_run)

        mock_infrastructure_run.assert_not_called()
        assert flow_run.id not in agent.submitting_flow_run_ids
        agent.logger.exception.assert_called_once_with(
            f"Failed to get infrastructure for flow run '{flow_run.id}'."
        )

        state = (await orion_client.read_flow_run(flow_run.id)).state
        assert state.is_failed()
        with pytest.raises(FailedRun, match="Submission failed. ValueError: Bad!"):
            await state.result()

    async def test_agent_fails_flow_if_infrastructure_submission_fails(
        self, orion_client, deployment, mock_infrastructure_run
    ):
        infra_doc_id = deployment.infrastructure_document_id
        infra_document = await orion_client.read_block_document(infra_doc_id)
        infrastructure = Block._from_block_document(infra_document)

        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc")),
        )
        flow = await orion_client.read_flow(deployment.flow_id)

        def raise_value_error():
            raise ValueError("Hello!")

        mock_infrastructure_run.pre_start_side_effect = raise_value_error

        async with OrionAgent(
            [deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            agent.logger = MagicMock()
            await agent.get_and_submit_flow_runs()

        mock_infrastructure_run.assert_called_once_with(
            infrastructure.prepare_for_flow_run(
                flow_run, deployment=deployment, flow=flow
            ).dict()
        )
        agent.logger.exception.assert_called_once_with(
            f"Failed to submit flow run '{flow_run.id}' to infrastructure."
        )

        state = (await orion_client.read_flow_run(flow_run.id)).state
        assert state.is_failed()
        with pytest.raises(FailedRun, match="Submission failed. ValueError: Hello!"):
            await state.result()

    async def test_agent_does_not_fail_flow_if_infrastructure_watch_fails(
        self, orion_client, deployment, mock_infrastructure_run
    ):
        infra_doc_id = deployment.infrastructure_document_id
        infra_document = await orion_client.read_block_document(infra_doc_id)
        infrastructure = Block._from_block_document(infra_document)

        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc")),
        )
        flow = await orion_client.read_flow(deployment.flow_id)

        def raise_value_error():
            raise ValueError("Hello!")

        mock_infrastructure_run.post_start_side_effect = raise_value_error

        async with OrionAgent(
            [deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            agent.logger = MagicMock()
            await agent.get_and_submit_flow_runs()

        mock_infrastructure_run.assert_called_once_with(
            infrastructure.prepare_for_flow_run(
                flow_run, deployment=deployment, flow=flow
            ).dict()
        )
        agent.logger.exception.assert_called_once_with(
            f"An error occured while monitoring flow run '{flow_run.id}'. "
            "The flow run will not be marked as failed, but an issue may have "
            "occurred."
        )

        state = (await orion_client.read_flow_run(flow_run.id)).state
        assert state.is_pending(), f"State should be PENDING: {state!r}"

    async def test_agent_logs_if_infrastructure_does_not_mark_as_started(
        self, orion_client, deployment, mock_infrastructure_run
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment.id,
            state=Scheduled(scheduled_time=pendulum.now("utc")),
        )

        # This excludes calling `task_status.started()` which will throw an anyio error
        # when submission finishes without calling `started()`. The agent will treat
        # submission the same as if it had thrown an error.
        mock_infrastructure_run.mark_as_started = False

        async with OrionAgent(
            work_queues=[deployment.work_queue_name], prefetch_seconds=10
        ) as agent:
            agent.logger = MagicMock()
            await agent.get_and_submit_flow_runs()

        agent.logger.error.assert_called_once_with(
            f"Infrastructure returned without reporting flow run '{flow_run.id}' "
            "as started or raising an error. This behavior is not expected and "
            "generally indicates improper implementation of infrastructure. The "
            "flow run will not be marked as failed, but an issue may have occurred."
        )


async def test_agent_displays_message_on_work_queue_pause(
    orion_client, prefect_caplog, deployment
):
    work_queue = await orion_client.read_work_queue_by_name(deployment.work_queue_name)

    async with OrionAgent(
        work_queues=[deployment.work_queue_name], prefetch_seconds=10
    ) as agent:
        agent.submit_run = AsyncMock()  # do not actually run

        await agent.get_and_submit_flow_runs()

        assert (
            f"Work queue 'wq' ({work_queue.id}) is paused." not in prefect_caplog.text
        ), "Message should not be displayed before pausing"

        await orion_client.update_work_queue(work_queue.id, is_paused=True)

        # clear agent cache
        agent._work_queue_cache_expiration = pendulum.now()

        # Should emit the paused message
        await agent.get_and_submit_flow_runs()

        assert f"Work queue 'wq' ({work_queue.id}) is paused." in prefect_caplog.text

"""Tests for the cancellation cleanup perpetual service."""

import logging
from collections.abc import Awaitable
from typing import Any, Callable
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.services.cancellation_cleanup as cancellation_cleanup_module
from prefect.client.schemas.worker_channel import CANCELLING_TIMEOUT_TEARDOWN
from prefect.server import models, schemas
from prefect.server.database import provide_database_interface
from prefect.server.schemas import states
from prefect.server.schemas.core import Deployment, Flow, FlowRun
from prefect.server.services.cancellation_cleanup import (
    CANCELLING_TIMEOUT_CANCELLED_MESSAGE,
    CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY,
    cancel_child_task_runs,
    cancel_subflow_run,
    enqueue_cancelling_timeout_teardowns,
)
from prefect.server.worker_communication.cleanup_queue.memory import WorkerCleanupQueue
from prefect.settings import (
    PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS,
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_QUEUE_STORAGE,
    temporary_settings,
)
from prefect.types._datetime import Duration, now

pytestmark = pytest.mark.clear_db

NON_TERMINAL_STATE_CONSTRUCTORS: dict[states.StateType, Any] = {
    states.StateType.SCHEDULED: states.Scheduled,
    states.StateType.PENDING: states.Pending,
    states.StateType.RUNNING: states.Running,
    states.StateType.PAUSED: states.Paused,
    states.StateType.CANCELLING: states.Cancelling,
}

TERMINAL_STATE_CONSTRUCTORS: dict[states.StateType, Any] = {
    states.StateType.COMPLETED: states.Completed,
    states.StateType.FAILED: states.Failed,
    states.StateType.CRASHED: states.Crashed,
    states.StateType.CANCELLED: states.Cancelled,
}

THE_PAST = now("UTC") - Duration(hours=5)
THE_ANCIENT_PAST = now("UTC") - Duration(days=100)


@pytest.fixture
async def cancelled_flow_run(session: AsyncSession, flow: Flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=states.Cancelled(), end_time=THE_PAST
            ),
        )


@pytest.fixture
async def old_cancelled_flow_run(session: AsyncSession, flow: Flow):
    async with session.begin():
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=states.Cancelled(), end_time=THE_ANCIENT_PAST
            ),
        )


@pytest.fixture
def cleanup_queue() -> WorkerCleanupQueue:
    queue = WorkerCleanupQueue()
    queue.clear()
    return queue


@pytest.fixture
async def cancelling_flow_run_maker(
    session: AsyncSession, flow: Flow, work_pool: Any
) -> Callable[..., Awaitable[Any]]:
    async def make_flow_run(
        *,
        state: states.State | None = None,
        infrastructure_pid: str | None = "infra-pid-1",
        use_default_work_queue: bool = True,
    ) -> Any:
        async with session.begin():
            return await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=state
                    or states.Cancelling(timestamp=now("UTC") - Duration(seconds=120)),
                    infrastructure_pid=infrastructure_pid,
                    work_queue_id=(
                        work_pool.default_queue_id if use_default_work_queue else None
                    ),
                ),
            )

    return make_flow_run


@pytest.fixture
async def orphaned_task_run_maker(session: AsyncSession):
    async def task_run_maker(flow_run: FlowRun, state_constructor: Any):
        async with session.begin():
            return await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=flow_run.id,
                    task_key="a task",
                    dynamic_key="a dynamic key",
                    state=state_constructor(),
                ),
            )

    return task_run_maker


@pytest.fixture
async def orphaned_subflow_run_maker(session: AsyncSession, flow: Flow):
    async def subflow_run_maker(flow_run: FlowRun, state_constructor: Any):
        async with session.begin():
            virtual_task = await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=flow_run.id,
                    task_key="a virtual task",
                    dynamic_key="a virtual dynamic key",
                    state=state_constructor(),
                ),
            )

            return await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    parent_task_run_id=virtual_task.id,
                    state=state_constructor(),
                    end_time=THE_PAST,
                ),
            )

    return subflow_run_maker


@pytest.fixture
async def orphaned_subflow_run_from_deployment_maker(
    session: AsyncSession, flow: Flow, deployment: Deployment
):
    async def subflow_run_maker(flow_run: FlowRun, state_constructor: Any):
        async with session.begin():
            virtual_task = await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=flow_run.id,
                    task_key="a virtual task for subflow from deployment",
                    dynamic_key="a virtual dynamic key for subflow from deployment",
                    state=state_constructor(),
                ),
            )

            return await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    parent_task_run_id=virtual_task.id,
                    state=state_constructor(),
                    end_time=THE_PAST,
                    deployment_id=deployment.id,
                    infrastructure_pid="my-pid-42",
                ),
            )

    return subflow_run_maker


async def test_all_state_types_are_tested():
    assert set(NON_TERMINAL_STATE_CONSTRUCTORS.keys()).union(
        set(TERMINAL_STATE_CONSTRUCTORS.keys())
    ) == set(states.StateType)


async def test_enqueue_cancelling_timeout_teardown_for_stuck_flow_run(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
    session: AsyncSession,
    work_pool: Any,
):
    flow_run = await cancelling_flow_run_maker(infrastructure_pid="infra-pid-1")
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        messages = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    await session.refresh(flow_run)
    assert flow_run.state is not None
    assert flow_run.state.type == states.StateType.CANCELLED
    assert flow_run.state.message == CANCELLING_TIMEOUT_CANCELLED_MESSAGE
    assert flow_run.end_time is not None
    cleanup_state_id = flow_run.state_id
    assert cleanup_state_id is not None
    assert flow_run.context[CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY].startswith(
        f"{cleanup_state_id}:"
    )

    assert len(messages) == 1
    message = messages[0]
    assert message.kind == CANCELLING_TIMEOUT_TEARDOWN
    assert message.work_pool_id == work_pool.id
    assert message.work_queue_id == work_pool.default_queue_id
    assert (
        message.idempotency_key
        == f"{CANCELLING_TIMEOUT_TEARDOWN}:{flow_run.id}:{cleanup_state_id}"
    )
    assert message.target == {
        "flow_run_id": str(flow_run.id),
        "infrastructure_pid": "infra-pid-1",
    }

    reserved = await cleanup_queue.reserve(work_pool_id=work_pool.id)
    assert reserved is not None
    assert reserved.message_id == message.message_id


async def test_enqueue_cancelling_timeout_teardown_marks_durable_cleanup_delivery_complete(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
    session: AsyncSession,
):
    flow_run = await cancelling_flow_run_maker(infrastructure_pid="infra-pid-1")
    db = provide_database_interface()

    with temporary_settings(
        {
            PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60,
            PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_QUEUE_STORAGE: (
                "tests.fake_durable_cleanup_queue"
            ),
        }
    ):
        messages = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )
        second_scan = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )
        marker = db.FlowRun.context[
            CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY
        ].as_string()
        marker_value = (
            cancellation_cleanup_module._cancelling_timeout_cleanup_marker_expression(
                db
            )
        )
        async with db.session_context() as marker_session:
            marker_result = await marker_session.execute(
                sa.select(marker == marker_value).where(db.FlowRun.id == flow_run.id)
            )
        assert marker_result.scalar_one()

    await session.refresh(flow_run)
    cleanup_state_id = flow_run.state_id
    assert cleanup_state_id is not None
    assert flow_run.context[CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY] == str(
        cleanup_state_id
    )
    assert len(messages) == 1
    assert second_scan == []


async def test_enqueue_cancelling_timeout_teardown_skips_recent_cancelling_run(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
    work_pool: Any,
):
    await cancelling_flow_run_maker(
        state=states.Cancelling(timestamp=now("UTC") - Duration(seconds=30))
    )
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        messages = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    assert messages == []
    assert await cleanup_queue.reserve(work_pool_id=work_pool.id) is None


@pytest.mark.parametrize(
    "state",
    [
        states.Running(timestamp=now("UTC") - Duration(seconds=120)),
        states.Cancelled(timestamp=now("UTC") - Duration(seconds=120)),
    ],
)
async def test_enqueue_cancelling_timeout_teardown_skips_non_cancelling_runs(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
    work_pool: Any,
    state: states.State,
):
    await cancelling_flow_run_maker(state=state)
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        messages = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    assert messages == []
    assert await cleanup_queue.reserve(work_pool_id=work_pool.id) is None


async def test_enqueue_cancelling_timeout_teardown_skips_unroutable_runs(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
    caplog: pytest.LogCaptureFixture,
    session: AsyncSession,
):
    flow_run = await cancelling_flow_run_maker(use_default_work_queue=False)
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        with caplog.at_level(
            logging.WARNING, logger="prefect.server.services.cancellation_cleanup"
        ):
            messages = await enqueue_cancelling_timeout_teardowns(
                db=db, cleanup_queue=cleanup_queue
            )

    assert messages == []
    assert "unroutable flow run" in caplog.text
    assert str(flow_run.id) in caplog.text
    await session.refresh(flow_run)
    assert flow_run.state is not None
    assert flow_run.state.type == states.StateType.CANCELLED
    assert flow_run.state.message == CANCELLING_TIMEOUT_CANCELLED_MESSAGE


async def test_enqueue_cancelling_timeout_teardown_allows_missing_infrastructure_pid(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
):
    flow_run = await cancelling_flow_run_maker(infrastructure_pid=None)
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        messages = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    assert len(messages) == 1
    assert messages[0].target == {
        "flow_run_id": str(flow_run.id),
        "infrastructure_pid": None,
    }


async def test_enqueue_cancelling_timeout_teardown_is_idempotent_for_repeated_scans(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
    session: AsyncSession,
    work_pool: Any,
):
    flow_run = await cancelling_flow_run_maker()
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        first = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )
        second = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    message_ids = {message.message_id for message in first + second}
    assert len(message_ids) == 1

    await session.refresh(flow_run)
    assert flow_run.state is not None
    assert flow_run.state.type == states.StateType.CANCELLED

    reserved = await cleanup_queue.reserve(work_pool_id=work_pool.id)
    assert reserved is not None
    assert reserved.message_id in message_ids
    assert await cleanup_queue.reserve(work_pool_id=work_pool.id) is None

    messages = await enqueue_cancelling_timeout_teardowns(
        db=db, cleanup_queue=cleanup_queue
    )
    assert messages == []
    assert await cleanup_queue.reserve(work_pool_id=work_pool.id) is None


async def test_enqueue_cancelling_timeout_teardown_reenqueues_after_memory_queue_restart(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    work_pool: Any,
):
    flow_run = await cancelling_flow_run_maker()
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        first = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )
        await session.refresh(flow_run)
        first_marker = flow_run.context[CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY]

        cleanup_queue.clear()
        monkeypatch.setattr(
            cancellation_cleanup_module,
            "IN_MEMORY_CLEANUP_QUEUE_MARKER_TOKEN",
            uuid4(),
        )
        second = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].message_id == first[0].message_id

    await session.refresh(flow_run)
    second_marker = flow_run.context[CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY]
    assert second_marker != first_marker
    assert second_marker.startswith(f"{flow_run.state_id}:")

    reserved = await cleanup_queue.reserve(work_pool_id=work_pool.id)
    assert reserved is not None
    assert reserved.message_id == first[0].message_id


async def test_enqueue_cancelling_timeout_teardown_retries_after_enqueue_failure(
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    work_pool: Any,
):
    cleanup_queue = WorkerCleanupQueue()
    original_enqueue = cleanup_queue.enqueue
    failures_remaining = 1

    async def fail_once_enqueue(**kwargs: Any):
        nonlocal failures_remaining
        if failures_remaining:
            failures_remaining -= 1
            raise RuntimeError("cleanup queue unavailable")
        return await original_enqueue(**kwargs)

    monkeypatch.setattr(cleanup_queue, "enqueue", fail_once_enqueue)
    flow_run = await cancelling_flow_run_maker()
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        with pytest.raises(RuntimeError, match="cleanup queue unavailable"):
            await enqueue_cancelling_timeout_teardowns(
                db=db, cleanup_queue=cleanup_queue
            )

        messages = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    await session.refresh(flow_run)
    assert flow_run.state is not None
    assert flow_run.state.type == states.StateType.CANCELLED
    assert flow_run.state.message == CANCELLING_TIMEOUT_CANCELLED_MESSAGE
    cleanup_state_id = flow_run.state_id
    assert cleanup_state_id is not None
    assert flow_run.context[CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY].startswith(
        f"{cleanup_state_id}:"
    )

    assert len(messages) == 1
    assert messages[0].idempotency_key == (
        f"{CANCELLING_TIMEOUT_TEARDOWN}:{flow_run.id}:{cleanup_state_id}"
    )
    reserved = await cleanup_queue.reserve(work_pool_id=work_pool.id)
    assert reserved is not None
    assert reserved.message_id == messages[0].message_id


async def test_enqueue_cancelling_timeout_teardown_uses_state_id_for_retry_attempts(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
    work_pool: Any,
):
    flow_run = await cancelling_flow_run_maker(infrastructure_pid="infra-pid-1")
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        first_messages = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    assert len(first_messages) == 1
    async with db.session_context() as first_state_session:
        first_retry_flow_run = await models.flow_runs.read_flow_run(
            session=first_state_session, flow_run_id=flow_run.id
        )
    assert first_retry_flow_run is not None
    first_cleanup_state_id = first_retry_flow_run.state_id
    assert first_cleanup_state_id is not None
    first_message = first_messages[0]
    assert (
        first_message.idempotency_key == f"{CANCELLING_TIMEOUT_TEARDOWN}:"
        f"{flow_run.id}:{first_cleanup_state_id}"
    )

    first_reservation = await cleanup_queue.reserve(work_pool_id=work_pool.id)
    assert first_reservation is not None
    await cleanup_queue.ack(
        work_pool_id=work_pool.id,
        message_id=first_reservation.message_id,
        reservation_token=first_reservation.reservation_token,
    )

    async with db.session_context(begin_transaction=True) as retry_session:
        await models.flow_runs.update_flow_run(
            session=retry_session,
            flow_run_id=flow_run.id,
            flow_run=schemas.actions.FlowRunUpdate(infrastructure_pid="infra-pid-2"),
        )
        retry_state_result = await models.flow_runs.set_flow_run_state(
            session=retry_session,
            flow_run_id=flow_run.id,
            state=states.Cancelling(timestamp=now("UTC") - Duration(seconds=120)),
            force=True,
        )

    assert retry_state_result.state is not None

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        second_messages = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    assert len(second_messages) == 1
    async with db.session_context() as second_state_session:
        second_retry_flow_run = await models.flow_runs.read_flow_run(
            session=second_state_session, flow_run_id=flow_run.id
        )
    assert second_retry_flow_run is not None
    second_cleanup_state_id = second_retry_flow_run.state_id
    assert second_cleanup_state_id is not None
    second_message = second_messages[0]
    assert second_message.message_id != first_message.message_id
    assert (
        second_message.idempotency_key == f"{CANCELLING_TIMEOUT_TEARDOWN}:"
        f"{flow_run.id}:{second_cleanup_state_id}"
    )
    assert second_message.target == {
        "flow_run_id": str(flow_run.id),
        "infrastructure_pid": "infra-pid-2",
    }

    second_reservation = await cleanup_queue.reserve(work_pool_id=work_pool.id)
    assert second_reservation is not None
    assert second_reservation.message_id == second_message.message_id


async def test_enqueue_cancelling_timeout_teardown_paginates_past_first_batch(
    cleanup_queue: WorkerCleanupQueue,
    cancelling_flow_run_maker: Callable[..., Awaitable[Any]],
):
    flow_runs = [await cancelling_flow_run_maker() for _ in range(201)]
    db = provide_database_interface()

    with temporary_settings(
        {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_CANCELLING_TIMEOUT_SECONDS: 60}
    ):
        messages = await enqueue_cancelling_timeout_teardowns(
            db=db, cleanup_queue=cleanup_queue
        )

    assert {message.target["flow_run_id"] for message in messages} == {
        str(flow_run.id) for flow_run in flow_runs
    }


@pytest.mark.parametrize("state_constructor", NON_TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_child_task_runs_cancels_nonterminal_tasks(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_task_run_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that cancel_child_task_runs cancels non-terminal task runs."""
    orphaned_task_run = await orphaned_task_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_child_task_runs(cancelled_flow_run.id, db=db)

    await session.refresh(orphaned_task_run)
    assert orphaned_task_run.state.type == "CANCELLED"


@pytest.mark.parametrize("state_constructor", NON_TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_subflow_run_cancels_nonterminal_subflows(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_subflow_run_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that cancel_subflow_run cancels non-terminal subflow runs."""
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_subflow_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_subflow_run(orphaned_subflow_run.id, db=db)

    await session.refresh(orphaned_subflow_run)
    assert orphaned_subflow_run.state.type == "CANCELLED"


@pytest.mark.parametrize("state_constructor", NON_TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_subflow_run_sets_cancelling_for_deployment_subflows(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_subflow_run_from_deployment_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that subflows from deployments get CANCELLING state (not CANCELLED)."""
    orphaned_subflow_run = await orphaned_subflow_run_from_deployment_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_subflow_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_subflow_run(orphaned_subflow_run.id, db=db)

    await session.refresh(orphaned_subflow_run)
    # Subflows from deployments should be set to CANCELLING (not CANCELLED)
    # so the infrastructure can be properly cleaned up
    assert orphaned_subflow_run.state.type == "CANCELLING"


@pytest.mark.parametrize("state_constructor", TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_child_task_runs_leaves_terminal_tasks_alone(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_task_run_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that cancel_child_task_runs doesn't modify terminal task runs."""
    orphaned_task_run = await orphaned_task_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_task_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_child_task_runs(cancelled_flow_run.id, db=db)

    await session.refresh(orphaned_task_run)
    # Terminal states should not be changed
    assert orphaned_task_run.state.type == state_constructor[0]


@pytest.mark.parametrize("state_constructor", TERMINAL_STATE_CONSTRUCTORS.items())
async def test_cancel_subflow_run_leaves_terminal_subflows_alone(
    session: AsyncSession,
    cancelled_flow_run: FlowRun,
    orphaned_subflow_run_maker: Callable[..., Any],
    state_constructor: tuple[states.StateType, Any],
):
    """Test that cancel_subflow_run doesn't modify terminal subflow runs."""
    orphaned_subflow_run = await orphaned_subflow_run_maker(
        cancelled_flow_run, state_constructor[1]
    )
    assert cancelled_flow_run.state.type == "CANCELLED"
    assert orphaned_subflow_run.state.type == state_constructor[0]

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_subflow_run(orphaned_subflow_run.id, db=db)

    await session.refresh(orphaned_subflow_run)
    # Terminal states should not be changed
    assert orphaned_subflow_run.state.type == state_constructor[0]


async def test_cancel_subflow_run_ignores_non_cancelled_parents(
    session: AsyncSession,
    flow: Flow,
):
    """Test that cancel_subflow_run doesn't cancel subflows whose parent isn't cancelled."""
    # Create a running parent flow run (not cancelled)
    async with session.begin():
        parent_flow = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=states.Running(),
            ),
        )
        virtual_task = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=parent_flow.id,
                task_key="virtual task",
                dynamic_key="dynamic key",
                state=states.Running(),
            ),
        )
        subflow = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                parent_task_run_id=virtual_task.id,
                state=states.Running(),
            ),
        )

    assert parent_flow.state.type == "RUNNING"
    assert subflow.state.type == "RUNNING"

    # Call the docket task function directly
    db = provide_database_interface()
    await cancel_subflow_run(subflow.id, db=db)

    await session.refresh(subflow)
    # Subflow should still be running since parent isn't cancelled
    assert subflow.state.type == "RUNNING"


async def test_cancel_child_task_runs_handles_deleted_flow_run(
    session: AsyncSession,
    flow: Flow,
):
    """Test that cancel_child_task_runs handles the case where flow run was deleted."""
    from uuid import uuid4

    # Call with a non-existent flow run ID - should not raise
    db = provide_database_interface()
    await cancel_child_task_runs(uuid4(), db=db)


async def test_cancel_subflow_run_handles_deleted_flow_run(
    session: AsyncSession,
    flow: Flow,
):
    """Test that cancel_subflow_run handles the case where flow run was deleted."""
    from uuid import uuid4

    # Call with a non-existent flow run ID - should not raise
    db = provide_database_interface()
    await cancel_subflow_run(uuid4(), db=db)

import pytest
import sqlalchemy as sa

from prefect.blocks.notifications import DebugPrintNotification
from prefect.orion import models, schemas
from prefect.orion.services.flow_run_notifications import FlowRunNotifications


@pytest.fixture(autouse=True)
async def notifier_block(orion_client):

    block = DebugPrintNotification()
    schema = await orion_client.read_block_schema_by_checksum(
        block._calculate_schema_checksum()
    )

    return await orion_client.create_block_document(
        block._to_block_document(
            name="Debug Print Notification", block_schema_id=schema.id
        )
    )


@pytest.fixture
async def completed_policy(session, notifier_block):
    policy = (
        await models.flow_run_notification_policies.create_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy=schemas.core.FlowRunNotificationPolicy(
                name="My Success Policy",
                state_names=["Completed"],
                tags=[],
                block_document_id=notifier_block.id,
            ),
        )
    )
    await session.commit()
    return policy


@pytest.fixture
async def completed_etl_policy(session, notifier_block):
    policy = (
        await models.flow_run_notification_policies.create_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy=schemas.core.FlowRunNotificationPolicy(
                name="My Success Policy",
                state_names=["Completed"],
                tags=["ETL"],
                block_document_id=notifier_block.id,
            ),
        )
    )
    await session.commit()
    return policy


@pytest.fixture
async def failed_policy(session, notifier_block):
    policy = (
        await models.flow_run_notification_policies.create_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy=schemas.core.FlowRunNotificationPolicy(
                name="My Success Policy",
                state_names=["Failed"],
                tags=[],
                block_document_id=notifier_block.id,
            ),
        )
    )
    await session.commit()
    return policy


async def test_service_clears_queue(
    session, db, flow_run, completed_policy, failed_policy
):
    # set a completed state
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
    )

    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run.id, state=schemas.states.Failed()
    )

    # 2 notifications in queue
    queued_notifications_query = await session.execute(
        sa.select(db.FlowRunNotificationQueue)
    )
    assert len(queued_notifications_query.scalars().fetchall()) == 2
    await session.commit()

    await FlowRunNotifications().start(loops=1)

    # no notifications in queue
    queued_notifications_query = await session.execute(
        sa.select(db.FlowRunNotificationQueue)
    )
    assert queued_notifications_query.scalars().fetchall() == []


async def test_service_sends_notifications(
    session, db, flow, flow_run, completed_policy, capsys
):
    # set a completed state
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
    )
    await session.commit()

    await FlowRunNotifications().start(loops=1)

    captured = capsys.readouterr()
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Completed`"
        in captured.out
    )


async def test_service_sends_multiple_notifications(
    session, db, flow, flow_run, completed_policy, failed_policy, capsys
):
    # set a completed state
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
    )
    # set a failed state
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run.id, state=schemas.states.Failed()
    )
    await session.commit()

    await FlowRunNotifications().start(loops=1)

    captured = capsys.readouterr()
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Completed`"
        in captured.out
    )
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Failed`" in captured.out
    )

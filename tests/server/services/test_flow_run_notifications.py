import pytest
import sqlalchemy as sa

from prefect.server import models, schemas
from prefect.server.services.flow_run_notifications import FlowRunNotifications
from prefect.settings import PREFECT_UI_URL, temporary_settings


@pytest.fixture
async def completed_policy(session, notifier_block):
    policy = (
        await models.flow_run_notification_policies.create_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy=schemas.core.FlowRunNotificationPolicy(
                state_names=["Completed"],
                tags=[],
                block_document_id=notifier_block._block_document_id,
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
                state_names=["Completed"],
                tags=["ETL"],
                block_document_id=notifier_block._block_document_id,
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
                state_names=["Failed"],
                tags=[],
                block_document_id=notifier_block._block_document_id,
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

    await FlowRunNotifications(handle_signals=False).start(loops=1)

    # no notifications in queue
    queued_notifications_query = await session.execute(
        sa.select(db.FlowRunNotificationQueue)
    )
    assert queued_notifications_query.scalars().fetchall() == []


async def test_service_sends_notification(
    session, db, flow, flow_run, completed_policy, capsys
):
    # set a completed state
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
    )
    await session.commit()

    await FlowRunNotifications(handle_signals=False).start(loops=1)

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
    # and set a failed state
    await models.flow_runs.set_flow_run_state(
        session=session,
        flow_run_id=flow_run.id,
        state=schemas.states.Failed(),
        force=True,
    )
    await session.commit()

    await FlowRunNotifications(handle_signals=False).start(loops=1)

    captured = capsys.readouterr()
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Completed`"
        in captured.out
    )
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Failed`" in captured.out
    )


async def test_service_does_not_send_notifications_without_policy(
    session, db, flow, flow_run, capsys
):
    # set a completed state
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
    )
    await session.commit()

    await FlowRunNotifications(handle_signals=False).start(loops=1)

    captured = capsys.readouterr()
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Completed`"
        not in captured.out
    )


async def test_service_sends_many_notifications_and_clears_queue(
    session, db, flow_run, completed_policy, capsys, flow
):
    COUNT = 200

    for _ in range(COUNT):
        # set a completed state repeatedly
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.states.Completed(),
            force=True,
        )

    queued_notifications_query = await session.execute(
        sa.select(db.FlowRunNotificationQueue)
    )
    assert len(queued_notifications_query.scalars().fetchall()) == COUNT
    await session.commit()

    await FlowRunNotifications(handle_signals=False).start(loops=1)

    # no notifications in queue
    queued_notifications_query = await session.execute(
        sa.select(db.FlowRunNotificationQueue)
    )
    assert queued_notifications_query.scalars().fetchall() == []

    captured = capsys.readouterr()
    assert (
        captured.out.count(
            f"Flow run {flow.name}/{flow_run.name} entered state `Completed`"
        )
        == COUNT
    )


async def test_service_only_sends_notifications_for_matching_policy(
    session, db, flow, flow_run, failed_policy, capsys
):
    # set a completed state
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
    )
    # and set a failed state
    await models.flow_runs.set_flow_run_state(
        session=session,
        flow_run_id=flow_run.id,
        state=schemas.states.Failed(),
        force=True,
    )
    await session.commit()

    await FlowRunNotifications(handle_signals=False).start(loops=1)

    captured = capsys.readouterr()
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Completed`"
        not in captured.out
    )
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Failed`" in captured.out
    )


@pytest.mark.parametrize(
    "provided_ui_url,expected_ui_url",
    [
        (None, "http://ephemeral-prefect/api"),
        ("http://some-url", "http://some-url"),
    ],
)
def test_get_ui_url_for_flow_run_id_with_ui_url(
    flow_run, provided_ui_url, expected_ui_url
):
    with temporary_settings({PREFECT_UI_URL: provided_ui_url}):
        url = FlowRunNotifications(handle_signals=False).get_ui_url_for_flow_run_id(
            flow_run_id=flow_run.id
        )
        assert url == expected_ui_url + "/flow-runs/flow-run/{flow_run_id}".format(
            flow_run_id=flow_run.id
        )


async def test_service_uses_message_template(
    session, db, flow, flow_run, completed_policy, capsys
):
    # modify the template
    await models.flow_run_notification_policies.update_flow_run_notification_policy(
        session=session,
        flow_run_notification_policy_id=completed_policy.id,
        flow_run_notification_policy=schemas.actions.FlowRunNotificationPolicyUpdate(
            message_template=(
                "Hi there {flow_run_name}! Also the url works: {flow_run_url}"
            )
        ),
    )

    # set a completed state
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
    )
    await session.commit()

    await FlowRunNotifications(handle_signals=False).start(loops=1)
    expected_url = FlowRunNotifications(
        handle_signals=False
    ).get_ui_url_for_flow_run_id(flow_run_id=flow_run.id)

    captured = capsys.readouterr()
    assert f"Hi there {flow_run.name}" in captured.out
    assert f"Also the url works: {expected_url}" in captured.out


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

    await FlowRunNotifications(handle_signals=False).start(loops=1)

    captured = capsys.readouterr()
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Completed`"
        in captured.out
    )
    assert (
        f"Flow run {flow.name}/{flow_run.name} entered state `Failed`" in captured.out
    )

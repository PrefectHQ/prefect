from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.blocks.notifications import DebugPrintNotification
from prefect.orion import models, schemas


@pytest.fixture
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
async def all_states_policy(session, notifier_block):
    policy = (
        await models.flow_run_notification_policies.create_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy=schemas.core.FlowRunNotificationPolicy(
                state_names=[],
                tags=[],
                block_document_id=notifier_block.id,
            ),
        )
    )
    await session.commit()
    return policy


@pytest.fixture
async def completed_policy(session, notifier_block):
    policy = (
        await models.flow_run_notification_policies.create_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy=schemas.core.FlowRunNotificationPolicy(
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
                state_names=["Failed"],
                tags=[],
                block_document_id=notifier_block.id,
            ),
        )
    )
    await session.commit()
    return policy


class TestCreateFlowRunNotificationPolicy:
    async def test_create_policy(self, session, notifier_block):
        policy = await models.flow_run_notification_policies.create_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy=schemas.core.FlowRunNotificationPolicy(
                state_names=["Completed"],
                tags=[],
                block_document_id=notifier_block.id,
            ),
        )
        await session.commit()
        assert policy.state_names == ["Completed"]


class TestReadFlowRunNotificationPolicy:
    async def test_read_policy(self, session, completed_policy):
        policy = await models.flow_run_notification_policies.read_flow_run_notification_policy(
            session=session, flow_run_notification_policy_id=completed_policy.id
        )
        assert policy.id == completed_policy.id

    async def test_read_policy_with_invalid_id(self, session):
        policy = await models.flow_run_notification_policies.read_flow_run_notification_policy(
            session=session, flow_run_notification_policy_id=uuid4()
        )
        assert policy is None


class TestReadFlowRunNotificationPolicies:
    @pytest.fixture(autouse=True)
    async def policies(self, session, completed_policy, failed_policy):
        # set failed policy to inactive
        await models.flow_run_notification_policies.update_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy_id=failed_policy.id,
            flow_run_notification_policy=schemas.actions.FlowRunNotificationPolicyUpdate(
                is_active=False
            ),
        )
        await session.commit()
        return completed_policy, failed_policy

    async def test_read_policies(self, session, policies):
        result = await models.flow_run_notification_policies.read_flow_run_notification_policies(
            session=session
        )

        await session.commit()
        assert len(result) == 2
        assert {r.id for r in result} == {p.id for p in policies}

    async def test_read_active_policies(self, session, completed_policy):
        result = await models.flow_run_notification_policies.read_flow_run_notification_policies(
            session=session,
            flow_run_notification_policy_filter=schemas.filters.FlowRunNotificationPolicyFilter(
                is_active=dict(eq_=True)
            ),
        )

        await session.commit()

        assert len(result) == 1
        assert result[0].id == completed_policy.id

    async def test_read_inactive_policies(self, session, failed_policy):
        result = await models.flow_run_notification_policies.read_flow_run_notification_policies(
            session=session,
            flow_run_notification_policy_filter=schemas.filters.FlowRunNotificationPolicyFilter(
                is_active=dict(eq_=False)
            ),
        )

        await session.commit()

        assert len(result) == 1
        assert result[0].id == failed_policy.id


class TestUpdateFlowRunNotificationPolicy:
    async def test_update_policy_states(self, session, completed_policy):
        await models.flow_run_notification_policies.update_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy_id=completed_policy.id,
            flow_run_notification_policy=schemas.actions.FlowRunNotificationPolicyUpdate(
                state_names=["My State"]
            ),
        )

        await session.commit()

        policy = await models.flow_run_notification_policies.read_flow_run_notification_policy(
            session=session, flow_run_notification_policy_id=completed_policy.id
        )
        assert policy.state_names == ["My State"]
        assert policy.is_active is True

    async def test_update_policy_active(self, session, completed_policy):
        await models.flow_run_notification_policies.update_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy_id=completed_policy.id,
            flow_run_notification_policy=schemas.actions.FlowRunNotificationPolicyUpdate(
                is_active=False
            ),
        )

        await session.commit()

        policy = await models.flow_run_notification_policies.read_flow_run_notification_policy(
            session=session, flow_run_notification_policy_id=completed_policy.id
        )
        assert policy.state_names == ["Completed"]
        assert policy.is_active is False


class TestDeleteFlowRunNotificationPolicy:
    async def test_delete_policy(self, session, completed_policy):
        await models.flow_run_notification_policies.delete_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy_id=completed_policy.id,
        )

        await session.commit()

        policy = await models.flow_run_notification_policies.read_flow_run_notification_policy(
            session=session, flow_run_notification_policy_id=completed_policy.id
        )
        assert policy is None


class TestQueueNotificationsFromPolicy:
    async def test_completed_notifications_are_queued(
        self, session, flow_run, completed_policy, db
    ):
        """one matching policy"""
        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # notification is queued
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        notifications = queued_notifications_query.scalars().fetchall()
        assert len(notifications) == 1
        assert notifications[0].flow_run_notification_policy_id == completed_policy.id
        assert notifications[0].flow_run_state_id == flow_run.state.id

    async def test_notifications_not_queued_for_non_matching_states(
        self, session, flow_run, completed_policy, db
    ):
        """no matching policy"""
        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

        # set a failed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Failed()
        )

        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

    async def test_notifications_are_queued_for_all_state_policies(
        self, session, flow_run, all_states_policy, db
    ):
        """one matching policy"""
        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # notification is queued
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        notifications = queued_notifications_query.scalars().fetchall()
        assert len(notifications) == 1
        assert notifications[0].flow_run_notification_policy_id == all_states_policy.id
        assert notifications[0].flow_run_state_id == flow_run.state.id

    async def test_notifications_queued_for_matching_states_only(
        self, session, flow_run, completed_policy, failed_policy, db
    ):
        """multiple policies, only one matches"""
        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

        # set a failed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Failed()
        )

        # notification is queued
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        notifications = queued_notifications_query.scalars().fetchall()
        assert len(notifications) == 1
        assert notifications[0].flow_run_notification_policy_id == failed_policy.id
        assert notifications[0].flow_run_state_id == flow_run.state.id

    async def test_notifications_not_queued_if_tags_dont_match(
        self, session, flow_run, completed_etl_policy, db
    ):
        """policy matches states but not tags"""
        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

    async def test_notifications_queued_if_tags_match(
        self, session, flow_run, completed_etl_policy, db
    ):
        """policy tags overlap"""
        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

        # add ETL to the flow run tags
        await models.flow_runs.update_flow_run(
            session=session,
            flow_run_id=flow_run.id,
            flow_run=schemas.actions.FlowRunUpdate(tags=["ETL", "another tag"]),
        )

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # notification is queued
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        notifications = queued_notifications_query.scalars().fetchall()
        assert len(notifications) == 1
        assert (
            notifications[0].flow_run_notification_policy_id == completed_etl_policy.id
        )
        assert notifications[0].flow_run_state_id == flow_run.state.id

    async def test_multiple_notifications_queued(
        self, session, flow_run, completed_policy, completed_etl_policy, db
    ):
        """multiple matching policies"""
        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

        # add ETL to the flow run tags
        await models.flow_runs.update_flow_run(
            session=session,
            flow_run_id=flow_run.id,
            flow_run=schemas.actions.FlowRunUpdate(tags=["ETL", "another tag"]),
        )

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # notification is queued
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        notifications = queued_notifications_query.scalars().fetchall()
        assert len(notifications) == 2

        assert {a.flow_run_notification_policy_id for a in notifications} == {
            completed_policy.id,
            completed_etl_policy.id,
        }
        assert notifications[0].flow_run_state_id == flow_run.state.id
        assert notifications[1].flow_run_state_id == flow_run.state.id

    async def test_inactive_notifications_not_queued(
        self, session, flow_run, completed_policy, db
    ):
        """policy matches states but is inactive"""
        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

        # set policy inactive
        await models.flow_run_notification_policies.update_flow_run_notification_policy(
            session=session,
            flow_run_notification_policy_id=completed_policy.id,
            flow_run_notification_policy=schemas.actions.FlowRunNotificationPolicyUpdate(
                is_active=False
            ),
        )

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

    async def test_queue_multiple_state_notifications(
        self, session, flow_run, completed_policy, failed_policy, db
    ):
        # no notifications in queue
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        assert queued_notifications_query.scalars().fetchall() == []

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )
        # set a failed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Failed()
        )

        # notifications are queued
        queued_notifications_query = await session.execute(
            sa.select(db.FlowRunNotificationQueue)
        )
        notifications = queued_notifications_query.scalars().fetchall()
        assert len(notifications) == 2

        assert {a.flow_run_notification_policy_id for a in notifications} == {
            completed_policy.id,
            failed_policy.id,
        }
        assert notifications[0].flow_run_state_id != notifications[1].flow_run_state_id

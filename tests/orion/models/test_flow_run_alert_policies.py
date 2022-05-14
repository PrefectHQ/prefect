from uuid import uuid4
import sqlalchemy as sa
import pytest

from prefect.blocks.notifications import DebugPrintNotification

from prefect.orion import models, schemas
from prefect.orion.models import flow_run_alert_policies
from prefect.orion.models.block_schemas import create_block_schema
from prefect.orion.models.block_types import create_block_type
from prefect.orion.models.block_documents import create_block_document


@pytest.fixture
async def notifier_block(orion_client):

    block = DebugPrintNotification()
    schema = await orion_client.read_block_schema_by_checksum(
        block.calculate_schema_checksum()
    )

    return await orion_client.create_block_document(
        block.to_block_document(
            name="Debug Print Notification", block_schema_id=schema.id
        )
    )


@pytest.fixture
async def all_states_policy(session, notifier_block):
    policy = await models.flow_run_alert_policies.create_flow_run_alert_policy(
        session=session,
        flow_run_alert_policy=schemas.core.FlowRunAlertPolicy(
            name="My Success Policy",
            state_names=[],
            tags=[],
            block_document_id=notifier_block.id,
        ),
    )
    await session.commit()
    return policy


@pytest.fixture
async def completed_policy(session, notifier_block):
    policy = await models.flow_run_alert_policies.create_flow_run_alert_policy(
        session=session,
        flow_run_alert_policy=schemas.core.FlowRunAlertPolicy(
            name="My Success Policy",
            state_names=["Completed"],
            tags=[],
            block_document_id=notifier_block.id,
        ),
    )
    await session.commit()
    return policy


@pytest.fixture
async def completed_etl_policy(session, notifier_block):
    policy = await models.flow_run_alert_policies.create_flow_run_alert_policy(
        session=session,
        flow_run_alert_policy=schemas.core.FlowRunAlertPolicy(
            name="My Success Policy",
            state_names=["Completed"],
            tags=["ETL"],
            block_document_id=notifier_block.id,
        ),
    )
    await session.commit()
    return policy


@pytest.fixture
async def failed_policy(session, notifier_block):
    policy = await models.flow_run_alert_policies.create_flow_run_alert_policy(
        session=session,
        flow_run_alert_policy=schemas.core.FlowRunAlertPolicy(
            name="My Success Policy",
            state_names=["Failed"],
            tags=[],
            block_document_id=notifier_block.id,
        ),
    )
    await session.commit()
    return policy


class TestCreateFlowRunAlertPolicy:
    async def test_create_policy(self, session, notifier_block):
        policy = await models.flow_run_alert_policies.create_flow_run_alert_policy(
            session=session,
            flow_run_alert_policy=schemas.core.FlowRunAlertPolicy(
                name="My Success Policy",
                state_names=["Completed"],
                tags=[],
                block_document_id=notifier_block.id,
            ),
        )
        await session.commit()
        assert policy.name == "My Success Policy"
        assert policy.state_names == ["Completed"]


class TestReadFlowRunAlertPolicy:
    async def test_read_policy(self, session, completed_policy):
        policy = await models.flow_run_alert_policies.read_flow_run_alert_policy(
            session=session, flow_run_alert_policy_id=completed_policy.id
        )
        assert policy.id == completed_policy.id
        assert policy.name == completed_policy.name

    async def test_read_policy_with_invalid_id(self, session):
        policy = await models.flow_run_alert_policies.read_flow_run_alert_policy(
            session=session, flow_run_alert_policy_id=uuid4()
        )
        assert policy is None


class TestUpdateFlowRunAlertPolicy:
    async def test_update_policy_states(self, session, completed_policy):
        await models.flow_run_alert_policies.update_flow_run_alert_policy(
            session=session,
            flow_run_alert_policy_id=completed_policy.id,
            flow_run_alert_policy=schemas.actions.FlowRunAlertPolicyUpdate(
                state_names=["My State"]
            ),
        )

        await session.commit()

        policy = await models.flow_run_alert_policies.read_flow_run_alert_policy(
            session=session, flow_run_alert_policy_id=completed_policy.id
        )
        assert policy.state_names == ["My State"]
        assert policy.is_active is True

    async def test_update_policy_active(self, session, completed_policy):
        await models.flow_run_alert_policies.update_flow_run_alert_policy(
            session=session,
            flow_run_alert_policy_id=completed_policy.id,
            flow_run_alert_policy=schemas.actions.FlowRunAlertPolicyUpdate(
                is_active=False
            ),
        )

        await session.commit()

        policy = await models.flow_run_alert_policies.read_flow_run_alert_policy(
            session=session, flow_run_alert_policy_id=completed_policy.id
        )
        assert policy.state_names == ["Completed"]
        assert policy.is_active is False


class TestDeleteFlowRunAlertPolicy:
    async def test_delete_policy(self, session, completed_policy):
        await models.flow_run_alert_policies.delete_flow_run_alert_policy(
            session=session,
            flow_run_alert_policy_id=completed_policy.id,
        )

        await session.commit()

        policy = await models.flow_run_alert_policies.read_flow_run_alert_policy(
            session=session, flow_run_alert_policy_id=completed_policy.id
        )
        assert policy is None


class TestQueueAlertsFromPolicy:
    async def test_completed_alerts_are_queued(
        self, session, flow_run, completed_policy, db
    ):
        """one matching policy"""
        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # alert is queued
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        alerts = queued_alerts_query.scalars().fetchall()
        assert len(alerts) == 1
        assert alerts[0].flow_run_alert_policy_id == completed_policy.id
        assert alerts[0].flow_run_state_id == flow_run.state.id

    async def test_alerts_not_queued_for_non_matching_states(
        self, session, flow_run, completed_policy, db
    ):
        """no matching policy"""
        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

        # set a failed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Failed()
        )

        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

    async def test_alerts_are_queued_for_all_state_policies(
        self, session, flow_run, all_states_policy, db
    ):
        """one matching policy"""
        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # alert is queued
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        alerts = queued_alerts_query.scalars().fetchall()
        assert len(alerts) == 1
        assert alerts[0].flow_run_alert_policy_id == all_states_policy.id
        assert alerts[0].flow_run_state_id == flow_run.state.id

    async def test_alerts_queued_for_matching_states_only(
        self, session, flow_run, completed_policy, failed_policy, db
    ):
        """multiple policies, only one matches"""
        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

        # set a failed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Failed()
        )

        # alert is queued
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        alerts = queued_alerts_query.scalars().fetchall()
        assert len(alerts) == 1
        assert alerts[0].flow_run_alert_policy_id == failed_policy.id
        assert alerts[0].flow_run_state_id == flow_run.state.id

    async def test_alerts_not_queued_if_tags_dont_match(
        self, session, flow_run, completed_etl_policy, db
    ):
        """policy matches states but not tags"""
        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

    async def test_alerts_queued_if_tags_match(
        self, session, flow_run, completed_etl_policy, db
    ):
        """policy tags overlap"""
        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

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

        # alert is queued
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        alerts = queued_alerts_query.scalars().fetchall()
        assert len(alerts) == 1
        assert alerts[0].flow_run_alert_policy_id == completed_etl_policy.id
        assert alerts[0].flow_run_state_id == flow_run.state.id

    async def test_multiple_alerts_queued(
        self, session, flow_run, completed_policy, completed_etl_policy, db
    ):
        """multiple matching policies"""
        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

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

        # alert is queued
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        alerts = queued_alerts_query.scalars().fetchall()
        assert len(alerts) == 2

        assert {a.flow_run_alert_policy_id for a in alerts} == {
            completed_policy.id,
            completed_etl_policy.id,
        }
        assert alerts[0].flow_run_state_id == flow_run.state.id
        assert alerts[1].flow_run_state_id == flow_run.state.id

    async def test_inactive_alerts_not_queued(
        self, session, flow_run, completed_policy, db
    ):
        """policy matches states but is inactive"""
        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

        # set policy inactive
        await models.flow_run_alert_policies.update_flow_run_alert_policy(
            session=session,
            flow_run_alert_policy_id=completed_policy.id,
            flow_run_alert_policy=schemas.actions.FlowRunAlertPolicyUpdate(
                is_active=False
            ),
        )

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )

        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

    async def test_queue_multiple_state_alerts(
        self, session, flow_run, completed_policy, failed_policy, db
    ):
        # no alerts in queue
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        assert queued_alerts_query.scalars().fetchall() == []

        # set a completed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Completed()
        )
        # set a failed state
        await models.flow_runs.set_flow_run_state(
            session=session, flow_run_id=flow_run.id, state=schemas.states.Failed()
        )

        # alerts are queued
        queued_alerts_query = await session.execute(sa.select(db.FlowRunAlertQueue))
        alerts = queued_alerts_query.scalars().fetchall()
        assert len(alerts) == 2

        assert {a.flow_run_alert_policy_id for a in alerts} == {
            completed_policy.id,
            failed_policy.id,
        }
        assert alerts[0].flow_run_state_id != alerts[1].flow_run_state_id

from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.blocks.notifications import DebugPrintNotification
from prefect.orion import models, schemas
from prefect.orion.schemas.core import FlowRunNotificationPolicy


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


class TestCreateFlowRunNotificationPolicy:
    async def test_create_policy(self, client, notifier_block):
        response = await client.post(
            "/flow_run_notification_policies/",
            json=dict(
                schemas.actions.FlowRunNotificationPolicyCreate(
                    name="My Success Policy",
                    state_names=["Completed"],
                    tags=[],
                    block_document_id=notifier_block.id,
                ).dict(json_compatible=True),
            ),
        )
        assert response.status_code == 201
        policy = FlowRunNotificationPolicy.parse_obj(response.json())
        assert policy.name == "My Success Policy"
        assert policy.state_names == ["Completed"]


class TestReadFlowRunNotificationPolicy:
    async def test_read_policy(self, client, completed_policy):

        response = await client.get(
            f"/flow_run_notification_policies/{completed_policy.id}"
        )
        assert response.status_code == 200
        policy = FlowRunNotificationPolicy.parse_obj(response.json())

        assert policy.id == completed_policy.id
        assert policy.name == completed_policy.name

    async def test_read_policy_with_invalid_id(self, client):
        response = await client.get(f"/flow_run_notification_policies/{uuid4()}")
        assert response.status_code == 404


class TestUpdateFlowRunNotificationPolicy:
    async def test_update_policy_states(self, client, session, completed_policy):
        response = await client.patch(
            f"/flow_run_notification_policies/{completed_policy.id}",
            json=schemas.actions.FlowRunNotificationPolicyUpdate(
                state_names=["My State"]
            ).dict(json_compatible=True, exclude_unset=True),
        )
        assert response.status_code == 204

        policy_id = completed_policy.id
        session.expire_all()
        policy = await models.flow_run_notification_policies.read_flow_run_notification_policy(
            session=session, flow_run_notification_policy_id=policy_id
        )
        assert policy.state_names == ["My State"]
        assert policy.is_active is True

    async def test_update_policy_active(self, session, client, completed_policy):
        response = await client.patch(
            f"/flow_run_notification_policies/{completed_policy.id}",
            json=schemas.actions.FlowRunNotificationPolicyUpdate(is_active=False).dict(
                json_compatible=True, exclude_unset=True
            ),
        )
        assert response.status_code == 204

        policy_id = completed_policy.id
        session.expire_all()
        policy = await models.flow_run_notification_policies.read_flow_run_notification_policy(
            session=session, flow_run_notification_policy_id=policy_id
        )
        assert policy.state_names == ["Completed"]
        assert policy.is_active is False

    async def test_update_missing_policy(self, client, completed_policy):
        response = await client.patch(
            f"/flow_run_notification_policies/{uuid4()}",
            json=schemas.actions.FlowRunNotificationPolicyUpdate(is_active=False).dict(
                json_compatible=True, exclude_unset=True
            ),
        )
        assert response.status_code == 404


class TestDeleteFlowRunNotificationPolicy:
    async def test_delete_policy(self, client, completed_policy):
        response = await client.delete(
            f"/flow_run_notification_policies/{completed_policy.id}"
        )
        assert response.status_code == 204

    async def test_delete_missing_policy(self, client):
        response = await client.delete(f"/flow_run_notification_policies/{uuid4()}")
        assert response.status_code == 404

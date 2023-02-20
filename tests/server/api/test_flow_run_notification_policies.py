from typing import List
from uuid import uuid4

import pydantic
import pytest

from prefect.server import models, schemas
from prefect.server.schemas.core import FlowRunNotificationPolicy


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


class TestCreateFlowRunNotificationPolicy:
    async def test_create_policy(self, client, notifier_block):
        response = await client.post(
            "/flow_run_notification_policies/",
            json=dict(
                schemas.actions.FlowRunNotificationPolicyCreate(
                    state_names=["Completed"],
                    tags=[],
                    block_document_id=notifier_block._block_document_id,
                ).dict(json_compatible=True),
            ),
        )
        assert response.status_code == 201
        policy = FlowRunNotificationPolicy.parse_obj(response.json())
        assert policy.state_names == ["Completed"]

    async def test_create_policy_with_message(self, client, notifier_block):
        response = await client.post(
            "/flow_run_notification_policies/",
            json=dict(
                schemas.actions.FlowRunNotificationPolicyCreate(
                    state_names=["Completed"],
                    tags=[],
                    block_document_id=notifier_block._block_document_id,
                    message_template="Hello there {flow_run_name}",
                ).dict(json_compatible=True),
            ),
        )
        policy = FlowRunNotificationPolicy.parse_obj(response.json())
        assert policy.message_template == "Hello there {flow_run_name}"


class TestReadFlowRunNotificationPolicy:
    async def test_read_policy(self, client, completed_policy):
        response = await client.get(
            f"/flow_run_notification_policies/{completed_policy.id}"
        )
        assert response.status_code == 200
        policy = FlowRunNotificationPolicy.parse_obj(response.json())

        assert policy.id == completed_policy.id

    async def test_read_policy_with_invalid_id(self, client):
        response = await client.get(f"/flow_run_notification_policies/{uuid4()}")
        assert response.status_code == 404


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

    async def test_read_policies(self, client, policies):
        response = await client.post("/flow_run_notification_policies/filter")
        assert response.status_code == 200
        result = pydantic.parse_obj_as(List[FlowRunNotificationPolicy], response.json())

        assert len(result) == 2
        assert {r.id for r in result} == {p.id for p in policies}

    async def test_read_active_policies(self, client, completed_policy):
        response = await client.post(
            "/flow_run_notification_policies/filter",
            json=dict(
                flow_run_notification_policy_filter=dict(is_active=dict(eq_=True))
            ),
        )
        assert response.status_code == 200
        result = pydantic.parse_obj_as(List[FlowRunNotificationPolicy], response.json())

        assert len(result) == 1
        assert result[0].id == completed_policy.id

    async def test_read_inactive_policies(self, client, failed_policy):
        response = await client.post(
            "/flow_run_notification_policies/filter",
            json=dict(
                flow_run_notification_policy_filter=dict(is_active=dict(eq_=False))
            ),
        )
        assert response.status_code == 200
        result = pydantic.parse_obj_as(List[FlowRunNotificationPolicy], response.json())

        assert len(result) == 1
        assert result[0].id == failed_policy.id


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

    async def test_update_policy_message_template(
        self, session, client, completed_policy
    ):
        response = await client.patch(
            f"/flow_run_notification_policies/{completed_policy.id}",
            json=schemas.actions.FlowRunNotificationPolicyUpdate(
                message_template="Hi there {flow_run_name}"
            ).dict(json_compatible=True, exclude_unset=True),
        )
        assert response.status_code == 204

        policy_id = completed_policy.id
        session.expire_all()
        policy = await models.flow_run_notification_policies.read_flow_run_notification_policy(
            session=session, flow_run_notification_policy_id=policy_id
        )
        assert policy.message_template == "Hi there {flow_run_name}"

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

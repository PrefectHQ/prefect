import json
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_iam

from prefect.infrastructure.provisioners.ecs import IamPolicyResource, IamUserResource


@pytest.fixture
def iam_policy_resource():
    return IamPolicyResource()


@pytest.fixture(autouse=True)
def iam_mock():
    mock = mock_iam()
    mock.start()

    yield

    mock.stop()


@pytest.fixture
def existing_iam_policy():
    iam_client = boto3.client("iam")
    policy = iam_client.create_policy(
        PolicyName="prefect-ecs-policy",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PrefectEcsPolicy",
                        "Effect": "Allow",
                        "Action": [
                            "ecs:DescribeTasks",
                        ],
                        "Resource": "*",
                    }
                ],
            }
        ),
    )

    yield

    iam_client.delete_policy(PolicyArn=policy["Policy"]["Arn"])


class TestIamPolicyResource:
    async def test_requires_provisioning_no_policy(self, iam_policy_resource):
        # Check if provisioning is needed
        needs_provisioning = await iam_policy_resource.requires_provisioning()

        assert needs_provisioning

    @pytest.mark.usefixtures("existing_iam_policy")
    async def test_requires_provisioning_with_policy(self, iam_policy_resource):
        needs_provisioning = await iam_policy_resource.requires_provisioning()

        assert not needs_provisioning

    async def test_provision(self, iam_policy_resource):
        advance_mock = MagicMock()
        iam_client = boto3.client("iam")
        iam_client.create_user(UserName="prefect-ecs-user")

        # Provision IAM policy
        await iam_policy_resource.provision(advance=advance_mock)

        # Check if the IAM policy exists
        policies = iam_client.list_policies(Scope="Local")["Policies"]
        policy_names = [policy["PolicyName"] for policy in policies]

        assert "prefect-ecs-policy" in policy_names

        advance_mock.assert_called_once()

    @pytest.mark.usefixtures("existing_iam_policy")
    async def test_provision_preexisting_policy(self):
        advance_mock = MagicMock()

        iam_policy_resource = IamPolicyResource()
        result = await iam_policy_resource.provision(advance=advance_mock)
        assert result is None
        advance_mock.assert_not_called()

    @pytest.mark.usefixtures("existing_iam_policy")
    async def test_get_task_count_policy_exists(self, iam_policy_resource):
        count = await iam_policy_resource.get_task_count()

        assert count == 0

    async def test_get_task_count_policy_does_not_exist(self, iam_policy_resource):
        count = await iam_policy_resource.get_task_count()

        assert count == 1

    @pytest.mark.usefixtures("existing_iam_policy")
    async def test_get_planned_actions_policy_exists(self, iam_policy_resource):
        actions = await iam_policy_resource.get_planned_actions()

        assert actions is None

    async def test_get_planned_actions_policy_does_not_exist(self, iam_policy_resource):
        actions = await iam_policy_resource.get_planned_actions()

        assert (
            actions
            == "Creating and attaching an IAM policy for managing ECS tasks:"
            f" [blue]{iam_policy_resource._policy_name}[/]"
        )


@pytest.fixture
def iam_user_resource():
    return IamUserResource(user_name="prefect-ecs-user")


@pytest.fixture
def existing_iam_user():
    iam_client = boto3.client("iam")
    iam_client.create_user(UserName="prefect-ecs-user")

    yield

    iam_client.delete_user(UserName="prefect-ecs-user")


class TestIamUserResource:
    async def test_requires_provisioning_no_user(self, iam_user_resource):
        needs_provisioning = await iam_user_resource.requires_provisioning()

        assert needs_provisioning

    @pytest.mark.usefixtures("existing_iam_user")
    async def test_requires_provisioning_with_user(self, iam_user_resource):
        needs_provisioning = await iam_user_resource.requires_provisioning()

        assert not needs_provisioning

    async def test_provision(self, iam_user_resource):
        advance_mock = MagicMock()
        iam_client = boto3.client("iam")

        # Provision IAM user
        await iam_user_resource.provision(advance=advance_mock)

        # Check if the IAM user exists
        users = iam_client.list_users()["Users"]
        user_names = [user["UserName"] for user in users]

        assert "prefect-ecs-user" in user_names

        advance_mock.assert_called_once()

    @pytest.mark.usefixtures("existing_iam_user")
    async def test_provision_preexisting_user(self):
        advance_mock = MagicMock()

        iam_user_resource = IamUserResource(user_name="prefect-ecs-user")
        result = await iam_user_resource.provision(advance=advance_mock)
        assert result is None
        advance_mock.assert_not_called()

    @pytest.mark.usefixtures("existing_iam_user")
    async def test_get_task_count_user_exists(self, iam_user_resource):
        count = await iam_user_resource.get_task_count()

        assert count == 0

    async def test_get_task_count_user_does_not_exist(self, iam_user_resource):
        count = await iam_user_resource.get_task_count()

        assert count == 1

    @pytest.mark.usefixtures("existing_iam_user")
    async def test_get_planned_actions_user_exists(self, iam_user_resource):
        actions = await iam_user_resource.get_planned_actions()

        assert actions is None

    async def test_get_planned_actions_user_does_not_exist(self, iam_user_resource):
        actions = await iam_user_resource.get_planned_actions()

        assert (
            actions
            == "Creating an IAM user for managing ECS tasks:"
            f" [blue]{iam_user_resource._user_name}[/]"
        )

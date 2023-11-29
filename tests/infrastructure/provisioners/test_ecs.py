from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_iam

from prefect.infrastructure.provisioners.ecs import IamPolicyResource


@pytest.fixture
def iam_policy_resource():
    return IamPolicyResource()


@pytest.fixture(autouse=True)
def iam_mock():
    mock = mock_iam()
    mock.start()

    yield

    mock.stop()


class TestIamPolicyResource:
    async def test_requires_provisioning_no_policy(self, iam_policy_resource):
        # Check if provisioning is needed
        needs_provisioning = await iam_policy_resource.requires_provisioning()

        assert needs_provisioning

    async def test_requires_provisioning_with_policy(self, iam_policy_resource):
        # Create a mock IAM policy
        iam_client = boto3.client("iam")
        iam_client.create_policy(
            PolicyName="prefect-ecs-policy",
            PolicyDocument="""\
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "PrefectEcsPolicy",
                            "Effect": "Allow",
                            "Action": [
                                "ec2:AuthorizeSecurityGroupIngress",
                                "ec2:CreateSecurityGroup",
                                "ec2:CreateTags",
                                "ec2:DescribeNetworkInterfaces",
                                "ec2:DescribeSecurityGroups",
                                "ec2:DescribeSubnets",
                                "ec2:DescribeVpcs",
                                "ecs:CreateCluster",
                                "ecs:DeregisterTaskDefinition",
                                "ecs:DescribeClusters",
                                "ecs:DescribeTaskDefinition",
                                "ecs:DescribeTasks",
                                "ecs:ListAccountSettings",
                                "ecs:ListClusters",
                                "ecs:ListTaskDefinitions",
                                "ecs:RegisterTaskDefinition",
                                "ecs:RunTask",
                                "ecs:StopTask",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                                "logs:DescribeLogGroups",
                                "logs:GetLogEvents"
                            ],
                            "Resource": "*"
                        }
                    ]
                }
            """,
        )

        # Check if provisioning is needed
        needs_provisioning = await iam_policy_resource.requires_provisioning()

        assert not needs_provisioning

    async def test_provision(self, iam_policy_resource):
        advance_mock = MagicMock()
        iam_client = boto3.client("iam")
        iam_client.create_user(UserName="prefect-ecs-user")

        # Provision IAM policy
        await iam_policy_resource.provision(
            "work_pool_name", base_job_template={}, advance=advance_mock
        )

        # Check if the IAM policy exists
        policies = iam_client.list_policies(Scope="Local")["Policies"]
        policy_names = [policy["PolicyName"] for policy in policies]

        assert "prefect-ecs-policy" in policy_names

        # Check if the IAM policy is attached to the user
        attached_policies = iam_client.list_attached_user_policies(
            UserName="prefect-ecs-user"
        )["AttachedPolicies"]
        attached_policy_arns = [policy["PolicyArn"] for policy in attached_policies]

        assert any(
            policy_arn.endswith(":policy/prefect-ecs-policy")
            for policy_arn in attached_policy_arns
        )
        assert advance_mock.call_count == iam_policy_resource.num_tasks

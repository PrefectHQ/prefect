import json
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_ec2, mock_ecs, mock_iam

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.infrastructure.provisioners.ecs import (
    AuthenticationResource,
    ClusterResource,
    CredentialsBlockResource,
    IamPolicyResource,
    IamUserResource,
    VpcResource,
)
from prefect.settings import PREFECT_API_BLOCKS_REGISTER_ON_START, temporary_settings


@pytest.fixture
def iam_policy_resource():
    return IamPolicyResource()


@pytest.fixture(autouse=True)
def iam_mock():
    mock = mock_iam()
    mock.start()

    yield

    mock.stop()


@pytest.fixture(autouse=True)
def ecs_mock():
    mock = mock_ecs()
    mock.start()

    yield

    mock.stop()


@pytest.fixture(autouse=True)
def ec2_mock():
    mock = mock_ec2()
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


@pytest.fixture
def credentials_block_resource():
    return CredentialsBlockResource(
        user_name="prefect-ecs-user", block_document_name="work-pool-aws-credentials"
    )


@pytest.fixture
def register_block_types():
    with temporary_settings({PREFECT_API_BLOCKS_REGISTER_ON_START: True}):
        yield


@pytest.fixture
async def existing_credentials_block(
    register_block_types, prefect_client: PrefectClient
):
    block_type = await prefect_client.read_block_type_by_slug(slug="aws-credentials")
    block_schema = await prefect_client.get_most_recent_block_schema_for_block_type(
        block_type_id=block_type.id
    )
    assert block_schema is not None
    block_document = await prefect_client.create_block_document(
        block_document=BlockDocumentCreate(
            name="work-pool-aws-credentials",
            data={
                "aws_access_key_id": "ACCESS_KEY_ID",
                "aws_secret_access_key": "SECRET_ACCESS_KEY",
                "region_name": "us-west-2",
            },
            block_type_id=block_type.id,
            block_schema_id=block_schema.id,
        )
    )

    yield

    await prefect_client.delete_block_document(block_document_id=block_document.id)


class TestCredentialsBlockResource:
    async def test_requires_provisioning_no_block(self, credentials_block_resource):
        needs_provisioning = await credentials_block_resource.requires_provisioning()

        assert needs_provisioning

    @pytest.mark.usefixtures("existing_credentials_block")
    async def test_requires_provisioning_with_block(self, credentials_block_resource):
        needs_provisioning = await credentials_block_resource.requires_provisioning()

        assert not needs_provisioning

    @pytest.mark.usefixtures("existing_iam_user", "register_block_types")
    async def test_provision(self, prefect_client, credentials_block_resource):
        advance_mock = MagicMock()

        base_job_template = {
            "variables": {
                "type": "object",
                "properties": {"aws_credentials": {}},
            }
        }

        # Provision credentials block
        await credentials_block_resource.provision(
            base_job_template=base_job_template,
            advance=advance_mock,
            client=prefect_client,
        )
        # Check if the block document exists
        block_document = await prefect_client.read_block_document_by_name(
            "work-pool-aws-credentials", "aws-credentials"
        )

        assert isinstance(block_document.data["aws_access_key_id"], str)
        assert isinstance(block_document.data["aws_secret_access_key"], str)

        assert base_job_template["variables"]["properties"]["aws_credentials"] == {
            "default": {"$ref": {"block_document_id": str(block_document.id)}},
        }

        advance_mock.assert_called()

    @pytest.mark.usefixtures("existing_credentials_block")
    async def test_provision_preexisting_block(self, prefect_client):
        advance_mock = MagicMock()

        base_job_template = {
            "variables": {
                "type": "object",
                "properties": {"aws_credentials": {}},
            }
        }

        credentials_block_resource = CredentialsBlockResource(
            user_name="prefect-ecs-user",
            block_document_name="work-pool-aws-credentials",
        )
        await credentials_block_resource.provision(
            base_job_template=base_job_template,
            advance=advance_mock,
            client=prefect_client,
        )
        block_document = await prefect_client.read_block_document_by_name(
            "work-pool-aws-credentials", "aws-credentials"
        )

        assert base_job_template["variables"]["properties"]["aws_credentials"] == {
            "default": {"$ref": {"block_document_id": str(block_document.id)}},
        }

        advance_mock.assert_not_called()

    @pytest.mark.usefixtures("existing_credentials_block")
    async def test_get_task_count_block_exists(self, credentials_block_resource):
        count = await credentials_block_resource.get_task_count()

        assert count == 0

    async def test_get_task_count_block_does_not_exist(
        self, credentials_block_resource
    ):
        count = await credentials_block_resource.get_task_count()

        assert count == 2

    @pytest.mark.usefixtures("existing_credentials_block")
    async def test_get_planned_actions_block_exists(self, credentials_block_resource):
        actions = await credentials_block_resource.get_planned_actions()

        assert actions is None

    async def test_get_planned_actions_block_does_not_exist(
        self, credentials_block_resource
    ):
        actions = await credentials_block_resource.get_planned_actions()

        assert actions == "Storing generated AWS credentials in a block"


@pytest.fixture
def authentication_resource():
    return AuthenticationResource(work_pool_name="work-pool")


class TestAuthenticationResource:
    async def test_requires_provisioning(self, authentication_resource):
        needs_provisioning = await authentication_resource.requires_provisioning()

        assert needs_provisioning

    @pytest.mark.usefixtures("existing_iam_user", "existing_iam_policy")
    async def test_needs_provisioning_existing_user_and_policy(
        self, authentication_resource
    ):
        needs_provisioning = await authentication_resource.requires_provisioning()

        assert needs_provisioning

    @pytest.mark.usefixtures(
        "existing_iam_user", "existing_iam_policy", "existing_credentials_block"
    )
    async def test_needs_provisioning_existing_user_policy_and_block(
        self, authentication_resource
    ):
        needs_provisioning = await authentication_resource.requires_provisioning()

        assert not needs_provisioning

    async def test_get_task_count(self, authentication_resource):
        count = await authentication_resource.get_task_count()

        assert count == 4

    async def test_get_planned_actions(self, authentication_resource):
        actions = await authentication_resource.get_planned_actions()

        assert (
            "Creating an IAM user for managing ECS tasks: [blue]prefect-ecs-user[/]"
            in actions
        )
        assert (
            "Creating and attaching an IAM policy for managing ECS tasks:"
            " [blue]prefect-ecs-policy[/]"
            in actions
        )
        assert "Storing generated AWS credentials in a block" in actions

    @pytest.mark.usefixtures("existing_iam_user", "existing_iam_policy")
    async def test_get_planned_actions_existing_user(self, authentication_resource):
        actions = await authentication_resource.get_planned_actions()

        assert actions == "Storing generated AWS credentials in a block"

    @pytest.mark.usefixtures("register_block_types")
    async def test_provision(self, authentication_resource, prefect_client):
        advance_mock = MagicMock()
        base_job_template = {
            "variables": {
                "type": "object",
                "properties": {"aws_credentials": {}},
            }
        }

        await authentication_resource.provision(
            base_job_template=base_job_template, advance=advance_mock
        )

        block_document = await prefect_client.read_block_document_by_name(
            "work-pool-aws-credentials", "aws-credentials"
        )

        assert isinstance(block_document.data["aws_access_key_id"], str)
        assert isinstance(block_document.data["aws_secret_access_key"], str)

        assert base_job_template["variables"]["properties"]["aws_credentials"] == {
            "default": {"$ref": {"block_document_id": str(block_document.id)}},
        }

        assert advance_mock.call_count == 4


@pytest.fixture
def cluster_resource():
    return ClusterResource(cluster_name="prefect-ecs-cluster")


@pytest.fixture
def existing_cluster():
    ecs_client = boto3.client("ecs")
    ecs_client.create_cluster(clusterName="prefect-ecs-cluster")

    yield

    ecs_client.delete_cluster(cluster="prefect-ecs-cluster")


class TestClusterResource:
    async def test_requires_provisioning_no_cluster(self, cluster_resource):
        needs_provisioning = await cluster_resource.requires_provisioning()

        assert needs_provisioning

    @pytest.mark.usefixtures("existing_cluster")
    async def test_requires_provisioning_with_cluster(self, cluster_resource):
        needs_provisioning = await cluster_resource.requires_provisioning()

        assert not needs_provisioning

    async def test_get_task_count(self, cluster_resource):
        count = await cluster_resource.get_task_count()

        assert count == 1

    @pytest.mark.usefixtures("existing_cluster")
    async def test_get_task_count_cluster_exists(self, cluster_resource):
        count = await cluster_resource.get_task_count()

        assert count == 0

    @pytest.mark.usefixtures("existing_cluster")
    async def test_get_planned_actions_cluster_exists(self, cluster_resource):
        actions = await cluster_resource.get_planned_actions()

        assert actions is None

    async def test_get_planned_actions_cluster_does_not_exist(self, cluster_resource):
        actions = await cluster_resource.get_planned_actions()

        assert (
            actions
            == "Creating an ECS cluster for running Prefect flows:"
            " [blue]prefect-ecs-cluster[/]"
        )

    async def test_provision(self, cluster_resource):
        advance_mock = MagicMock()
        ecs_client = boto3.client("ecs")

        base_job_template = {
            "variables": {
                "type": "object",
                "properties": {"cluster": {}},
            }
        }

        await cluster_resource.provision(
            base_job_template=base_job_template,
            advance=advance_mock,
        )

        clusters = ecs_client.list_clusters()["clusterArns"]
        assert (
            f"arn:aws:ecs:us-east-1:123456789012:cluster/{cluster_resource._cluster_name}"
            in clusters
        )

        assert base_job_template["variables"]["properties"]["cluster"] == {
            "default": "prefect-ecs-cluster",
        }

        advance_mock.assert_called_once()


@pytest.fixture
def vpc_resource():
    return VpcResource()


@pytest.fixture
def no_default_vpc():
    ec2 = boto3.resource("ec2")
    default_vpc = None
    for vpc in ec2.vpcs.all():
        if vpc.is_default:
            default_vpc = vpc
            break

    if not default_vpc:
        return

    default_vpc.delete()


@pytest.fixture
def existing_vpc(no_default_vpc):
    ec2 = boto3.resource("ec2")
    ec2.create_vpc(CidrBlock="172.31.0.0/16")

    yield


@pytest.fixture
def existing_prefect_vpc(no_default_vpc):
    ec2 = boto3.resource("ec2")
    vpc = ec2.create_vpc(CidrBlock="172.31.0.0/16")
    vpc.create_tags(Tags=[{"Key": "Name", "Value": "prefect-ecs-vpc"}])

    yield


class TestVpcResource:
    @pytest.mark.usefixtures("no_default_vpc")
    async def test_get_task_count(self, vpc_resource):
        count = await vpc_resource.get_task_count()

        assert count == 5

    async def test_get_task_count_default_vpc(self, vpc_resource):
        count = await vpc_resource.get_task_count()

        assert count == 0

    @pytest.mark.usefixtures("existing_prefect_vpc")
    async def test_get_task_count_existing_prefect_vpc(self, vpc_resource):
        count = await vpc_resource.get_task_count()

        assert count == 0

    @pytest.mark.usefixtures("existing_vpc")
    async def test_get_task_count_existing_vpc(self, vpc_resource):
        count = await vpc_resource.get_task_count()

        assert count == 5

    async def test_requires_provisioning_default_vpc_exists(self, vpc_resource):
        requires_provisioning = await vpc_resource.requires_provisioning()

        assert not requires_provisioning

    @pytest.mark.usefixtures("existing_prefect_vpc")
    async def test_requires_provisioning_prefect_created_vpc_exists(self, vpc_resource):
        requires_provisioning = await vpc_resource.requires_provisioning()

        assert not requires_provisioning

    @pytest.mark.usefixtures("no_default_vpc")
    async def test_requires_provisioning_no_default_vpc(self, vpc_resource):
        requires_provisioning = await vpc_resource.requires_provisioning()

        assert requires_provisioning

    @pytest.mark.usefixtures("existing_vpc")
    async def test_requires_provisioning_existing_vpc(self, vpc_resource):
        requires_provisioning = await vpc_resource.requires_provisioning()

        assert requires_provisioning

    @pytest.mark.usefixtures("no_default_vpc")
    async def test_get_planned_actions_requires_provisioning(self, vpc_resource):
        actions = await vpc_resource.get_planned_actions()

        assert (
            actions
            == "Creating a VPC with CIDR [blue]172.31.0.0/16[/] for running"
            " ECS tasks: [blue]prefect-ecs-vpc[/]"
        )

    async def test_get_planned_actions_does_not_require_provisioning(
        self, vpc_resource
    ):
        actions = await vpc_resource.get_planned_actions()

        assert actions is None

    @pytest.mark.usefixtures("no_default_vpc")
    async def test_provision(self, vpc_resource):
        base_job_template = {
            "variables": {
                "type": "object",
                "properties": {"vpc_id": {}},
            }
        }

        advance_mock = MagicMock()

        await vpc_resource.provision(
            base_job_template=base_job_template,
            advance=advance_mock,
        )

        assert isinstance(
            base_job_template["variables"]["properties"]["vpc_id"]["default"], str
        )

        ec2 = boto3.resource("ec2")
        vpc = ec2.Vpc(base_job_template["variables"]["properties"]["vpc_id"]["default"])
        assert vpc.cidr_block == "172.31.0.0/16"
        assert vpc.tags[0]["Key"] == "Name"
        assert vpc.tags[0]["Value"] == "prefect-ecs-vpc"

        assert len(list(vpc.subnets.all())) == 3
        assert len(list(vpc.internet_gateways.all())) == 1
        # One route table is created by default, and the other is created for the internet gateway
        assert len(list(vpc.route_tables.all())) == 2
        # One security group is created by default, and the other is created to restrict traffic to the VPC
        assert len(list(vpc.security_groups.all())) == 2

        advance_mock.assert_called()

    @pytest.mark.usefixtures("existing_prefect_vpc")
    async def test_provision_existing_prefect_vpc(self, vpc_resource):
        base_job_template = {
            "variables": {
                "type": "object",
                "properties": {"vpc_id": {}},
            }
        }

        advance_mock = MagicMock()

        await vpc_resource.provision(
            base_job_template=base_job_template,
            advance=advance_mock,
        )

        ec2 = boto3.resource("ec2")
        prefect_vpc = None
        for vpc in ec2.vpcs.all():
            if vpc.tags[0]["Value"] == "prefect-ecs-vpc":
                prefect_vpc = vpc
                break

        assert (
            base_job_template["variables"]["properties"]["vpc_id"]["default"]
            == prefect_vpc.id
        )
        advance_mock.assert_not_called()

    @pytest.mark.usefixtures("existing_vpc")
    async def test_provision_existing_vpc(self, vpc_resource):
        base_job_template = {
            "variables": {
                "type": "object",
                "properties": {"vpc_id": {}},
            }
        }

        advance_mock = MagicMock()

        await vpc_resource.provision(
            base_job_template=base_job_template,
            advance=advance_mock,
        )

        ec2 = boto3.resource("ec2")
        vpc = ec2.Vpc(base_job_template["variables"]["properties"]["vpc_id"]["default"])
        # The CIDR block is different to avoid a collision with the existing VPC
        assert vpc.cidr_block == "172.32.0.0/16"

    async def test_provision_default_vpc(self, vpc_resource):
        base_job_template = {
            "variables": {
                "type": "object",
                "properties": {"vpc_id": {}},
            }
        }

        advance_mock = MagicMock()

        await vpc_resource.provision(
            base_job_template=base_job_template,
            advance=advance_mock,
        )

        assert "default" not in base_job_template["variables"]["properties"]["vpc_id"]
        advance_mock.assert_not_called()

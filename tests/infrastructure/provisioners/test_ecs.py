import json
from textwrap import dedent
from unittest.mock import ANY, MagicMock, call, patch

import boto3
import pytest
from moto import mock_aws

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.infrastructure.provisioners import (
    get_infrastructure_provisioner_for_work_pool_type,
)
from prefect.infrastructure.provisioners.ecs import (
    AuthenticationResource,
    ClusterResource,
    ContainerRepositoryResource,
    CredentialsBlockResource,
    ElasticContainerServicePushProvisioner,
    ExecutionRoleResource,
    IamPolicyResource,
    IamUserResource,
    VpcResource,
)


@pytest.fixture(autouse=True)
def start_mocking_aws(monkeypatch):
    monkeypatch.setenv(
        "MOTO_IAM_LOAD_MANAGED_POLICIES", "true"
    )  # tell moto to explicitly load managed policies
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        yield


@pytest.fixture
def iam_policy_resource() -> IamPolicyResource:
    return IamPolicyResource(policy_name="prefect-ecs-policy")


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


@pytest.fixture
def mock_run_process():
    with patch("prefect.infrastructure.provisioners.ecs.run_process") as mock:
        yield mock


@pytest.fixture
def mock_ainstall_packages():
    with patch("prefect.infrastructure.provisioners.ecs.ainstall_packages") as mock:
        yield mock


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
        await iam_policy_resource.provision(
            advance=advance_mock,
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PrefectEcsPolicy",
                        "Effect": "Allow",
                        "Action": [
                            "ec2:AuthorizeSecurityGroupIngress",
                        ],
                        "Resource": "*",
                    }
                ],
            },
        )

        # Check if the IAM policy exists
        policies = iam_client.list_policies(Scope="Local")["Policies"]
        policy_names = [policy["PolicyName"] for policy in policies]

        assert "prefect-ecs-policy" in policy_names

        advance_mock.assert_called_once()

    @pytest.mark.usefixtures("existing_iam_policy")
    async def test_provision_preexisting_policy(self):
        advance_mock = MagicMock()

        iam_policy_resource = IamPolicyResource(policy_name="prefect-ecs-policy")
        result = await iam_policy_resource.provision(
            advance=advance_mock, policy_document={}
        )
        # returns existing policy ARN
        assert result == "arn:aws:iam::123456789012:policy/prefect-ecs-policy"
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

        assert actions == []

    async def test_get_planned_actions_policy_does_not_exist(self, iam_policy_resource):
        actions = await iam_policy_resource.get_planned_actions()

        assert actions == [
            "Creating and attaching an IAM policy for managing ECS tasks:"
            f" [blue]{iam_policy_resource._policy_name}[/]"
        ]


@pytest.fixture
def iam_user_resource():
    return IamUserResource(user_name="prefect-ecs-user")


@pytest.fixture
def existing_iam_user():
    iam_client = boto3.client("iam")
    iam_client.create_user(UserName="prefect-ecs-user")

    yield

    iam_client.delete_user(UserName="prefect-ecs-user")


@pytest.fixture
def existing_execution_role():
    iam_client = boto3.client("iam")
    iam_client.create_role(
        RoleName="PrefectEcsTaskExecutionRole",
        AssumeRolePolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PrefectEcsExecutionRole",
                        "Effect": "Allow",
                        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        ),
    )

    yield

    iam_client.delete_role(RoleName="PrefectEcsTaskExecutionRole")


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

        assert actions == []

    async def test_get_planned_actions_user_does_not_exist(self, iam_user_resource):
        actions = await iam_user_resource.get_planned_actions()

        assert actions == [
            "Creating an IAM user for managing ECS tasks:"
            f" [blue]{iam_user_resource._user_name}[/]"
        ]


@pytest.fixture
def credentials_block_resource():
    return CredentialsBlockResource(
        user_name="prefect-ecs-user", block_document_name="work-pool-aws-credentials"
    )


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

        assert actions == []

    async def test_get_planned_actions_block_does_not_exist(
        self, credentials_block_resource
    ):
        actions = await credentials_block_resource.get_planned_actions()

        assert actions == ["Storing generated AWS credentials in a block"]


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
        "existing_iam_user",
        "existing_iam_policy",
        "existing_credentials_block",
        "existing_execution_role",
    )
    async def test_needs_provisioning_existing_resources(self, authentication_resource):
        needs_provisioning = await authentication_resource.requires_provisioning()

        assert not needs_provisioning

    async def test_get_task_count(self, authentication_resource):
        count = await authentication_resource.get_task_count()

        assert count == 5

    async def test_get_planned_actions(self, authentication_resource):
        actions = await authentication_resource.get_planned_actions()

        assert (
            "Creating an IAM user for managing ECS tasks: [blue]prefect-ecs-user[/]"
            in actions
        )
        assert (
            "Creating and attaching an IAM policy for managing ECS tasks:"
            " [blue]prefect-ecs-policy[/]" in actions
        )
        assert "Storing generated AWS credentials in a block" in actions

    @pytest.mark.usefixtures("existing_iam_user", "existing_iam_policy")
    async def test_get_planned_actions_existing_user(self, authentication_resource):
        actions = await authentication_resource.get_planned_actions()

        assert actions == [
            (
                "Creating an IAM role assigned to ECS tasks:"
                " [blue]PrefectEcsTaskExecutionRole[/]"
            ),
            "Storing generated AWS credentials in a block",
        ]

    @pytest.mark.usefixtures("register_block_types")
    async def test_provision(self, authentication_resource, prefect_client):
        advance_mock = MagicMock()
        base_job_template = {
            "variables": {
                "type": "object",
                "properties": {"aws_credentials": {}, "execution_role_arn": {}},
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

        assert advance_mock.call_count == 5


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

        assert actions == []

    async def test_get_planned_actions_cluster_does_not_exist(self, cluster_resource):
        actions = await cluster_resource.get_planned_actions()

        assert actions == [
            "Creating an ECS cluster for running Prefect flows:"
            " [blue]prefect-ecs-cluster[/]"
        ]

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

    # Delete all subnets in the default VPC
    for subnet in default_vpc.subnets.all():
        subnet.delete()

    # Delete all non-default security groups in the default VPC
    for sg in default_vpc.security_groups.all():
        if sg.group_name != "default":
            sg.delete()

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

        assert count == 4

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

        assert count == 4

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

        assert actions == [
            "Creating a VPC with CIDR [blue]172.31.0.0/16[/] for running"
            " ECS tasks: [blue]prefect-ecs-vpc[/]"
        ]

    async def test_get_planned_actions_does_not_require_provisioning(
        self, vpc_resource
    ):
        actions = await vpc_resource.get_planned_actions()

        assert actions == []

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


class TestElasticContainerServicePushProvisioner:
    @pytest.fixture
    def provisioner(self):
        return ElasticContainerServicePushProvisioner()

    @pytest.fixture
    def mock_console(self):
        return MagicMock()

    @pytest.fixture
    def mock_confirm(self):
        with patch("prefect.infrastructure.provisioners.ecs.Confirm") as mock:
            yield mock

    @pytest.fixture
    def mock_importlib(self):
        with patch("prefect.infrastructure.provisioners.ecs.importlib") as mock:
            yield mock

    async def test_prompt_boto3_installation(
        self, provisioner, mock_confirm, mock_run_process, mock_ainstall_packages
    ):
        await provisioner._prompt_boto3_installation()
        mock_ainstall_packages.assert_called_once_with(["boto3"])

    def test_is_boto3_installed(self, provisioner, mock_importlib):
        assert provisioner.is_boto3_installed()
        mock_importlib.import_module.assert_called_once()

    @pytest.mark.usefixtures("register_block_types")
    async def test_provision_boto3_not_installed_interactive(
        self,
        provisioner,
        mock_confirm,
        mock_run_process: MagicMock,
        mock_importlib,
        mock_ainstall_packages,
    ):
        mock_confirm.ask.side_effect = [
            True,
            False,
            True,
        ]  # install boto3, do not customize, proceed with provisioning

        mock_importlib.import_module.side_effect = [ModuleNotFoundError, boto3]

        provisioner.console.is_interactive = True
        await provisioner.provision(
            work_pool_name="test-work-pool",
            base_job_template={
                "variables": {
                    "type": "object",
                    "properties": {
                        "vpc_id": {},
                        "cluster": {},
                        "aws_credentials": {},
                        "execution_role_arn": {},
                    },
                }
            },
        )

        mock_confirm.ask.calls = [
            call(
                (
                    "boto3 is required to configure your AWS account. Would you like to"
                    " install it?"
                ),
                console=ANY,
            ),
            call(
                "Proceed with infrastructure provisioning?",
                console=ANY,
            ),
        ]
        mock_ainstall_packages.assert_called_once_with(["boto3"])
        assert mock_run_process.mock_calls == [
            call(
                "docker login -u AWS -p 123456789012-auth-token"
                " https://123456789012.dkr.ecr.us-east-1.amazonaws.com"
            ),
        ]

    async def test_provision_boto3_not_installed_non_interactive(
        self, provisioner, mock_confirm, mock_importlib
    ):
        mock_importlib.import_module.side_effect = [ModuleNotFoundError, boto3]

        with pytest.raises(RuntimeError):
            await provisioner.provision(
                work_pool_name="test-work-pool",
                base_job_template={
                    "variables": {
                        "type": "object",
                        "properties": {
                            "vpc_id": {},
                            "cluster": {},
                            "aws_credentials": {},
                            "execution_role_arn": {},
                        },
                    }
                },
            )

        mock_confirm.ask.assert_not_called()

    async def test_provision_boto3_installed_interactive(
        self, provisioner, mock_console, mock_confirm
    ):
        mock_console.is_interactive = True
        mock_confirm.ask.side_effect = [False, False]

        provisioner.console.is_interactive = True
        provisioner.is_boto3_installed = MagicMock(return_value=True)

        result = await provisioner.provision("test-work-pool", {})

        assert result == {}

        assert mock_confirm.ask.call_count == 2
        expected_call_1 = call(
            (
                "Would you like to customize the resource names for your"
                " infrastructure? This includes an IAM user, IAM policy, ECS cluster,"
                " VPC, ECS security group, and ECR repository."
            ),
        )
        expected_call_2 = call("Proceed with infrastructure provisioning?", console=ANY)
        assert mock_confirm.ask.call_args_list[0] == expected_call_1
        assert mock_confirm.ask.call_args_list[1] == expected_call_2

    @pytest.mark.usefixtures("register_block_types", "no_default_vpc")
    async def test_provision_interactive_with_default_names(
        self, provisioner, mock_confirm, prefect_client, mock_run_process, capsys
    ):
        provisioner.console.is_interactive = True
        mock_confirm.ask.side_effect = [
            False,
            True,
        ]  # do not customize, proceed with provisioning

        result = await provisioner.provision(
            "test-work-pool",
            {
                "variables": {
                    "type": "object",
                    "properties": {
                        "vpc_id": {},
                        "cluster": {},
                        "aws_credentials": {},
                        "execution_role_arn": {},
                    },
                }
            },
        )

        ec2 = boto3.resource("ec2")
        vpc = ec2.Vpc(result["variables"]["properties"]["vpc_id"]["default"])
        assert vpc is not None

        ecs = boto3.client("ecs")
        clusters = ecs.list_clusters()["clusterArns"]
        assert (
            f"arn:aws:ecs:us-east-1:123456789012:cluster/{result['variables']['properties']['cluster']['default']}"
            in clusters
        )

        block_document = await prefect_client.read_block_document_by_name(
            "test-work-pool-aws-credentials", "aws-credentials"
        )
        assert result["variables"]["properties"]["aws_credentials"] == {
            "default": {"$ref": {"block_document_id": str(block_document.id)}},
        }

        mock_run_process.assert_called_with(
            "docker login -u AWS -p 123456789012-auth-token"
            " https://123456789012.dkr.ecr.us-east-1.amazonaws.com"
        )

        captured = capsys.readouterr()
        assert "Your default Docker build namespace has been set" in captured.out

        assert (
            result["variables"]["properties"]["cluster"]["default"]
            == "prefect-ecs-cluster"
        )

    @pytest.mark.usefixtures("register_block_types", "no_default_vpc")
    async def test_provision_interactive_with_custom_names(
        self,
        provisioner,
        mock_confirm,
        prefect_client,
        mock_run_process,
        capsys,
        monkeypatch,
    ):
        provisioner.console.is_interactive = True
        mock_confirm.ask.side_effect = [
            True,  # customize
            True,  # proceed with provisioning
        ]

        def prompt_mocks(*args, **kwargs):
            if "Enter a name for the IAM user" in args[0]:
                return "custom-iam-user"
            elif "Enter a name for the IAM policy" in args[0]:
                return "custom-iam-policy"
            elif "Enter a name for the ECS cluster" in args[0]:
                return "custom-ecs-cluster"
            elif "Enter a name for the AWS credentials block" in args[0]:
                return "custom-aws-credentials"
            elif "Enter a name for the VPC" in args[0]:
                return "custom-vpc"
            elif "Enter a name for the ECS security group" in args[0]:
                return "custom-ecs-security-group"
            elif "Enter a name for the ECR repository" in args[0]:
                return "custom-ecr-repository"
            else:
                raise ValueError(f"Unexpected prompt: {args[0]}")

        mock_prompt = MagicMock(side_effect=prompt_mocks)

        monkeypatch.setattr(
            "prefect.infrastructure.provisioners.ecs.prompt", mock_prompt
        )

        result = await provisioner.provision(
            "test-work-pool",
            {
                "variables": {
                    "type": "object",
                    "properties": {
                        "vpc_id": {},
                        "cluster": {},
                        "aws_credentials": {},
                        "execution_role_arn": {},
                    },
                }
            },
        )

        ec2 = boto3.resource("ec2")
        vpc = ec2.Vpc(result["variables"]["properties"]["vpc_id"]["default"])
        assert vpc is not None

        ecs = boto3.client("ecs")
        clusters = ecs.list_clusters()["clusterArns"]
        assert (
            f"arn:aws:ecs:us-east-1:123456789012:cluster/{result['variables']['properties']['cluster']['default']}"
            in clusters
        )

        block_document = await prefect_client.read_block_document_by_name(
            "custom-aws-credentials", "aws-credentials"
        )
        assert result["variables"]["properties"]["aws_credentials"] == {
            "default": {"$ref": {"block_document_id": str(block_document.id)}},
        }

        mock_run_process.assert_called_with(
            "docker login -u AWS -p 123456789012-auth-token"
            " https://123456789012.dkr.ecr.us-east-1.amazonaws.com"
        )

        captured = capsys.readouterr()
        assert "Your default Docker build namespace has been set" in captured.out

        assert (
            result["variables"]["properties"]["cluster"]["default"]
            == "custom-ecs-cluster"
        )

    async def test_provision_interactive_reject_provisioning(
        self, provisioner, mock_confirm
    ):
        provisioner.console.is_interactive = True
        mock_confirm.ask.side_effect = [
            False,
            False,
        ]  # do not customize, do not proceed with provisioning

        original_base_template = {
            "variables": {
                "type": "object",
                "properties": {
                    "vpc_id": {},
                    "cluster": {},
                    "aws_credentials": {},
                    "execution_role_arn": {},
                },
            }
        }
        unchanged_base_job_template = await provisioner.provision(
            "test-work-pool", original_base_template
        )

        assert unchanged_base_job_template == original_base_template

    @pytest.mark.usefixtures(
        "register_block_types", "no_default_vpc", "mock_run_process"
    )
    async def test_provision_idempotent(self, provisioner, mock_confirm):
        provisioner.console.is_interactive = True
        mock_confirm.ask.side_effect = [
            False,
            True,
            False,
            True,
        ]  # do not customize, proceed with provisioning (for each)

        result_1 = await provisioner.provision(
            "test-work-pool",
            {
                "variables": {
                    "type": "object",
                    "properties": {
                        "vpc_id": {},
                        "cluster": {},
                        "aws_credentials": {},
                        "execution_role_arn": {},
                    },
                }
            },
        )

        result_2 = await provisioner.provision(
            "test-work-pool",
            {
                "variables": {
                    "type": "object",
                    "properties": {
                        "vpc_id": {},
                        "cluster": {},
                        "aws_credentials": {},
                        "execution_role_arn": {},
                    },
                }
            },
        )

        assert result_1 == result_2

    async def test_raises_runtime_error_on_failure(self, provisioner):
        """
        Cause a failure by not registering the block types and ensure that a RuntimeError is raised.
        """
        with pytest.raises(
            RuntimeError, match=r'Unable to find block type "aws-credentials"'
        ):
            await provisioner.provision(
                "test-work-pool",
                {
                    "variables": {
                        "type": "object",
                        "properties": {
                            "vpc_id": {},
                            "cluster": {},
                            "aws_credentials": {},
                            "execution_role_arn": {},
                        },
                    }
                },
            )


def test_resolve_provisoner():
    assert isinstance(
        get_infrastructure_provisioner_for_work_pool_type("ecs:push"),
        ElasticContainerServicePushProvisioner,
    )


@pytest.fixture
def execution_role_resource():
    return ExecutionRoleResource(execution_role_name="PrefectEcsTaskExecutionRole")


class TestExecutionRoleResource:
    async def test_get_task_count_requires_provisioning(self, execution_role_resource):
        count = await execution_role_resource.get_task_count()

        assert count == 1

    @pytest.mark.usefixtures("existing_execution_role")
    async def test_get_task_count_does_not_require_provisioning(
        self, execution_role_resource
    ):
        count = await execution_role_resource.get_task_count()

        assert count == 0

    async def test_requires_provisioning_true(self, execution_role_resource):
        requires_provisioning = await execution_role_resource.requires_provisioning()

        assert requires_provisioning is True

    @pytest.mark.usefixtures("existing_execution_role")
    async def test_requires_provisioning_false(self, execution_role_resource):
        requires_provisioning = await execution_role_resource.requires_provisioning()

        assert requires_provisioning is False

    async def test_get_planned_actions_requires_provisioning(
        self, execution_role_resource
    ):
        actions = await execution_role_resource.get_planned_actions()

        assert actions == [
            "Creating an IAM role assigned to ECS tasks:"
            " [blue]PrefectEcsTaskExecutionRole[/]"
        ]

    @pytest.mark.usefixtures("existing_execution_role")
    async def test_get_planned_actions_does_not_require_provisioning(
        self, execution_role_resource
    ):
        actions = await execution_role_resource.get_planned_actions()

        assert actions == []

    async def test_provision_requires_provisioning(self, execution_role_resource):
        advance_mock = MagicMock()

        arn = await execution_role_resource.provision(
            base_job_template={
                "variables": {
                    "type": "object",
                    "properties": {
                        "execution_role_arn": {},
                    },
                }
            },
            advance=advance_mock,
        )

        assert arn == "arn:aws:iam::123456789012:role/PrefectEcsTaskExecutionRole"
        advance_mock.assert_called_once()

    @pytest.mark.usefixtures("existing_execution_role")
    async def test_provision_does_not_require_provisioning(
        self, execution_role_resource
    ):
        advance_mock = MagicMock()

        arn = await execution_role_resource.provision(
            base_job_template={
                "variables": {
                    "type": "object",
                    "properties": {
                        "execution_role_arn": {},
                    },
                }
            },
            advance=advance_mock,
        )

        assert arn == "arn:aws:iam::123456789012:role/PrefectEcsTaskExecutionRole"
        advance_mock.assert_not_called()


@pytest.fixture
def container_repository_resource():
    return ContainerRepositoryResource(
        work_pool_name="test-work-pool", repository_name="prefect-flows"
    )


@pytest.fixture
def existing_ecr_repository():
    ecr_client = boto3.client("ecr")
    ecr_client.create_repository(repositoryName="prefect-flows")

    yield

    ecr_client.delete_repository(repositoryName="prefect-flows")


class TestContainerRepositoryResource:
    async def test_get_task_count_requires_provisioning(
        self, container_repository_resource
    ):
        assert await container_repository_resource.get_task_count() == 3

    @pytest.mark.usefixtures("existing_ecr_repository")
    async def test_get_task_count_does_not_require_provisioning(
        self, container_repository_resource
    ):
        assert await container_repository_resource.get_task_count() == 0

    async def test_requires_provisioning(self, container_repository_resource):
        assert await container_repository_resource.requires_provisioning() is True

    @pytest.mark.usefixtures("existing_ecr_repository")
    async def test_requires_provisioning_existing_repository(
        self, container_repository_resource
    ):
        assert await container_repository_resource.requires_provisioning() is False

    async def test_get_planned_actions_requires_provisioning(
        self, container_repository_resource
    ):
        assert await container_repository_resource.get_planned_actions() == [
            "Creating an ECR repository for storing Prefect images:"
            " [blue]prefect-flows[/]"
        ]

    @pytest.mark.usefixtures("existing_ecr_repository")
    async def test_get_planned_actions_does_not_require_provisioning(
        self, container_repository_resource
    ):
        assert await container_repository_resource.get_planned_actions() == []

    async def test_provision_requires_provisioning(
        self, container_repository_resource, mock_run_process
    ):
        advance_mock = MagicMock()
        await container_repository_resource.provision(
            base_job_template={},
            advance=advance_mock,
        )

        advance_mock.assert_called()

        ecr = boto3.client("ecr")
        new_repository = ecr.describe_repositories(repositoryNames=["prefect-flows"])
        assert new_repository["repositories"][0]["repositoryName"] == "prefect-flows"
        mock_run_process.assert_called_once_with(
            "docker login -u AWS -p 123456789012-auth-token"
            " https://123456789012.dkr.ecr.us-east-1.amazonaws.com"
        )

    @pytest.mark.usefixtures("existing_ecr_repository")
    async def test_provision_does_not_require_provisioning(
        self, container_repository_resource
    ):
        advance_mock = MagicMock()

        await container_repository_resource.provision(
            base_job_template={},
            advance=advance_mock,
        )

        advance_mock.assert_not_called()

    @pytest.mark.usefixtures("mock_run_process")
    async def test_update_next_steps(self, container_repository_resource):
        advance_mock = MagicMock()

        await container_repository_resource.provision(
            base_job_template={},
            advance=advance_mock,
        )

        assert container_repository_resource.next_steps[0] == dedent(
            """\

            Your default Docker build namespace has been set to [blue]'123456789012.dkr.ecr.us-east-1.amazonaws.com'[/].

            To build and push a Docker image to your newly created repository, use [blue]'prefect-flows'[/] as your image name:
            """
        )
        assert container_repository_resource.next_steps[1].renderable.code == dedent(
            """\
                from prefect import flow
                from prefect.docker import DockerImage


                @flow(log_prints=True)
                def my_flow(name: str = "world"):
                    print(f"Hello {name}! I'm a flow running on ECS!")


                if __name__ == "__main__":
                    my_flow.deploy(
                        name="my-deployment",
                        work_pool_name="test-work-pool",
                        image=DockerImage(
                            name="prefect-flows:latest",
                            platform="linux/amd64",
                        )
                    )"""
        )

    @pytest.mark.usefixtures("existing_ecr_repository")
    async def test_no_next_steps_when_no_provision(self, container_repository_resource):
        advance_mock = MagicMock()

        await container_repository_resource.provision(
            base_job_template={},
            advance=advance_mock,
        )

        assert container_repository_resource.next_steps == []

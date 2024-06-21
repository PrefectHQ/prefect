import base64
import contextlib
import contextvars
import importlib
import ipaddress
import json
import shlex
import sys
from copy import deepcopy
from functools import partial
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import anyio
from anyio import run_process
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.syntax import Syntax

from prefect.cli._prompts import prompt
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.client.utilities import inject_client
from prefect.exceptions import ObjectNotFound
from prefect.settings import (
    PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE,
    update_current_profile,
)
from prefect.utilities.collections import get_from_dict
from prefect.utilities.importtools import lazy_import

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient

boto3 = lazy_import("boto3")

current_console = contextvars.ContextVar("console", default=Console())


@contextlib.contextmanager
def console_context(value: Console):
    token = current_console.set(value)
    try:
        yield
    finally:
        current_console.reset(token)


class IamPolicyResource:
    """
    Represents an IAM policy resource for managing ECS tasks.

    Args:
        policy_name: The name of the IAM policy. Defaults to "prefect-ecs-policy".
    """

    def __init__(
        self,
        policy_name: str,
    ):
        self._iam_client = boto3.client("iam")
        self._policy_name = policy_name

        self._requires_provisioning = None

    async def get_task_count(self) -> int:
        """
        Returns the number of tasks that will be executed to provision this resource.

        Returns:
            int: The number of tasks to be provisioned.
        """
        return 1 if await self.requires_provisioning() else 0

    def _get_policy_by_name(self, name):
        paginator = self._iam_client.get_paginator("list_policies")
        page_iterator = paginator.paginate(Scope="Local")

        for page in page_iterator:
            for policy in page["Policies"]:
                if policy["PolicyName"] == name:
                    return policy
        return None

    async def requires_provisioning(self) -> bool:
        """
        Check if this resource requires provisioning.

        Returns:
            bool: True if provisioning is required, False otherwise.
        """
        if self._requires_provisioning is not None:
            return self._requires_provisioning
        policy = await anyio.to_thread.run_sync(
            partial(self._get_policy_by_name, self._policy_name)
        )
        if policy is not None:
            self._requires_provisioning = False
            return False

        self._requires_provisioning = True
        return True

    async def get_planned_actions(self) -> List[str]:
        """
        Returns a description of the planned actions for provisioning this resource.

        Returns:
            Optional[str]: A description of the planned actions for provisioning the resource,
                or None if provisioning is not required.
        """
        if await self.requires_provisioning():
            return [
                "Creating and attaching an IAM policy for managing ECS tasks:"
                f" [blue]{self._policy_name}[/]"
            ]
        return []

    async def provision(
        self,
        policy_document: Dict[str, Any],
        advance: Callable[[], None],
    ):
        """
        Provisions an IAM policy.

        Args:
            advance: A callback function to indicate progress.

        Returns:
            str: The ARN (Amazon Resource Name) of the created IAM policy.
        """
        if await self.requires_provisioning():
            console = current_console.get()
            console.print("Creating IAM policy")
            policy = await anyio.to_thread.run_sync(
                partial(
                    self._iam_client.create_policy,
                    PolicyName=self._policy_name,
                    PolicyDocument=json.dumps(policy_document),
                )
            )
            policy_arn = policy["Policy"]["Arn"]
            advance()
            return policy_arn
        else:
            policy = await anyio.to_thread.run_sync(
                partial(self._get_policy_by_name, self._policy_name)
            )
            # This should never happen, but just in case
            assert policy is not None, "Could not find expected policy"
            return policy["Arn"]

    @property
    def next_steps(self):
        return []


class IamUserResource:
    """
    Represents an IAM user resource for managing ECS tasks.

    Args:
        user_name: The desired name of the IAM user.
    """

    def __init__(self, user_name: str):
        self._iam_client = boto3.client("iam")
        self._user_name = user_name
        self._requires_provisioning = None

    async def get_task_count(self) -> int:
        """
        Returns the number of tasks that will be executed to provision this resource.

        Returns:
            int: The number of tasks to be provisioned.
        """
        return 1 if await self.requires_provisioning() else 0

    async def requires_provisioning(self) -> bool:
        """
        Check if this resource requires provisioning.

        Returns:
            bool: True if provisioning is required, False otherwise.
        """
        if self._requires_provisioning is None:
            try:
                await anyio.to_thread.run_sync(
                    partial(self._iam_client.get_user, UserName=self._user_name)
                )
                self._requires_provisioning = False
            except self._iam_client.exceptions.NoSuchEntityException:
                self._requires_provisioning = True

        return self._requires_provisioning

    async def get_planned_actions(self) -> List[str]:
        """
        Returns a description of the planned actions for provisioning this resource.

        Returns:
            Optional[str]: A description of the planned actions for provisioning the resource,
                or None if provisioning is not required.
        """
        if await self.requires_provisioning():
            return [
                "Creating an IAM user for managing ECS tasks:"
                f" [blue]{self._user_name}[/]"
            ]
        return []

    async def provision(
        self,
        advance: Callable[[], None],
    ):
        """
        Provisions an IAM user.

        Args:
            advance: A callback function to indicate progress.
        """
        console = current_console.get()
        if await self.requires_provisioning():
            console.print("Provisioning IAM user")
            await anyio.to_thread.run_sync(
                partial(self._iam_client.create_user, UserName=self._user_name)
            )
            advance()

    @property
    def next_steps(self):
        return []


class CredentialsBlockResource:
    def __init__(self, user_name: str, block_document_name: str):
        self._block_document_name = block_document_name
        self._user_name = user_name
        self._requires_provisioning = None

    async def get_task_count(self):
        """
        Returns the number of tasks that will be executed to provision this resource.

        Returns:
            int: The number of tasks to be provisioned.
        """
        return 2 if await self.requires_provisioning() else 0

    @inject_client
    async def requires_provisioning(
        self, client: Optional["PrefectClient"] = None
    ) -> bool:
        if self._requires_provisioning is None:
            try:
                assert client is not None
                await client.read_block_document_by_name(
                    self._block_document_name, "aws-credentials"
                )
                self._requires_provisioning = False
            except ObjectNotFound:
                self._requires_provisioning = True
        return self._requires_provisioning

    async def get_planned_actions(self) -> List[str]:
        """
        Returns a description of the planned actions for provisioning this resource.

        Returns:
            Optional[str]: A description of the planned actions for provisioning the resource,
                or None if provisioning is not required.
        """
        if await self.requires_provisioning():
            return ["Storing generated AWS credentials in a block"]
        return []

    @inject_client
    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
        client: Optional["PrefectClient"] = None,
    ):
        """
        Provisions an AWS credentials block.

        Will generate new credentials if the block does not already exist. Updates
        the `aws_credentials` variable in the job template to reference the block.

        Args:
            base_job_template: The base job template.
            advance: A callback function to indicate progress.
            client: A Prefect client to use for interacting with the Prefect API.
        """
        assert client is not None, "Client injection failed"
        if not await self.requires_provisioning():
            block_doc = await client.read_block_document_by_name(
                self._block_document_name, "aws-credentials"
            )
        else:
            console = current_console.get()
            console.print("Generating AWS credentials")
            iam_client = boto3.client("iam")
            access_key_data = await anyio.to_thread.run_sync(
                partial(iam_client.create_access_key, UserName=self._user_name)
            )
            access_key = access_key_data["AccessKey"]
            advance()
            console.print("Creating AWS credentials block")
            assert client is not None

            try:
                credentials_block_type = await client.read_block_type_by_slug(
                    "aws-credentials"
                )
            except ObjectNotFound as exc:
                raise RuntimeError(
                    dedent(
                        """\
                    Unable to find block type "aws-credentials".
                    To register the `aws-credentials` block type, run:

                            pip install prefect-aws
                            prefect blocks register -m prefect_aws

                    """
                    )
                ) from exc

            credentials_block_schema = (
                await client.get_most_recent_block_schema_for_block_type(
                    block_type_id=credentials_block_type.id
                )
            )
            assert (
                credentials_block_schema is not None
            ), f"Unable to find schema for block type {credentials_block_type.slug}"

            block_doc = await client.create_block_document(
                block_document=BlockDocumentCreate(
                    name=self._block_document_name,
                    data={
                        "aws_access_key_id": access_key["AccessKeyId"],
                        "aws_secret_access_key": access_key["SecretAccessKey"],
                        "region_name": boto3.session.Session().region_name,
                    },
                    block_type_id=credentials_block_type.id,
                    block_schema_id=credentials_block_schema.id,
                )
            )
            advance()
        base_job_template["variables"]["properties"]["aws_credentials"]["default"] = {
            "$ref": {"block_document_id": str(block_doc.id)}
        }

    @property
    def next_steps(self):
        return []


class AuthenticationResource:
    def __init__(
        self,
        work_pool_name: str,
        user_name: str = "prefect-ecs-user",
        policy_name: str = "prefect-ecs-policy",
        credentials_block_name: Optional[str] = None,
    ):
        self._user_name = user_name
        self._credentials_block_name = (
            credentials_block_name or f"{work_pool_name}-aws-credentials"
        )
        self._policy_name = policy_name
        self._policy_document = {
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
                        "ecs:TagResource",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogGroups",
                        "logs:GetLogEvents",
                    ],
                    "Resource": "*",
                }
            ],
        }
        self._iam_user_resource = IamUserResource(user_name=user_name)
        self._iam_policy_resource = IamPolicyResource(policy_name=policy_name)
        self._credentials_block_resource = CredentialsBlockResource(
            user_name=user_name, block_document_name=self._credentials_block_name
        )
        self._execution_role_resource = ExecutionRoleResource()

    @property
    def resources(self):
        return [
            self._execution_role_resource,
            self._iam_user_resource,
            self._iam_policy_resource,
            self._credentials_block_resource,
        ]

    async def get_task_count(self):
        """
        Returns the number of tasks that will be executed to provision this resource.

        Returns:
            int: The number of tasks to be provisioned.
        """
        return sum([await resource.get_task_count() for resource in self.resources])

    async def requires_provisioning(self) -> bool:
        """
        Check if this resource requires provisioning.

        Returns:
            bool: True if provisioning is required, False otherwise.
        """
        return any(
            [await resource.requires_provisioning() for resource in self.resources]
        )

    async def get_planned_actions(self) -> List[str]:
        """
        Returns a description of the planned actions for provisioning this resource.

        Returns:
            Optional[str]: A description of the planned actions for provisioning the resource,
                or None if provisioning is not required.
        """
        return [
            action
            for resource in self.resources
            for action in await resource.get_planned_actions()
        ]

    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        """
        Provisions the authentication resources.

        Args:
            base_job_template: The base job template of the work pool to provision
                infrastructure for.
            advance: A callback function to indicate progress.
        """
        # Provision task execution role
        role_arn = await self._execution_role_resource.provision(
            base_job_template=base_job_template, advance=advance
        )
        # Update policy document with the role ARN
        self._policy_document["Statement"].append(
            {
                "Sid": "AllowPassRoleForEcs",
                "Effect": "Allow",
                "Action": "iam:PassRole",
                "Resource": role_arn,
            }
        )
        # Provision the IAM user
        await self._iam_user_resource.provision(advance=advance)
        # Provision the IAM policy
        policy_arn = await self._iam_policy_resource.provision(
            policy_document=self._policy_document, advance=advance
        )
        # Attach the policy to the user
        if policy_arn:
            iam_client = boto3.client("iam")
            await anyio.to_thread.run_sync(
                partial(
                    iam_client.attach_user_policy,
                    UserName=self._user_name,
                    PolicyArn=policy_arn,
                )
            )
        await self._credentials_block_resource.provision(
            base_job_template=base_job_template,
            advance=advance,
        )

    @property
    def next_steps(self):
        return [
            next_step
            for resource in self.resources
            for next_step in resource.next_steps
        ]


class ClusterResource:
    def __init__(self, cluster_name: str = "prefect-ecs-cluster"):
        self._ecs_client = boto3.client("ecs")
        self._cluster_name = cluster_name
        self._requires_provisioning = None

    async def get_task_count(self):
        """
        Returns the number of tasks that will be executed to provision this resource.

        Returns:
            int: The number of tasks to be provisioned.
        """
        return 1 if await self.requires_provisioning() else 0

    async def requires_provisioning(self) -> bool:
        """
        Check if this resource requires provisioning.

        Returns:
            bool: True if provisioning is required, False otherwise.
        """
        if self._requires_provisioning is None:
            response = await anyio.to_thread.run_sync(
                partial(
                    self._ecs_client.describe_clusters, clusters=[self._cluster_name]
                )
            )
            if response["clusters"] and response["clusters"][0]["status"] == "ACTIVE":
                self._requires_provisioning = False
            else:
                self._requires_provisioning = True
        return self._requires_provisioning

    async def get_planned_actions(self) -> List[str]:
        """
        Returns a description of the planned actions for provisioning this resource.

        Returns:
            Optional[str]: A description of the planned actions for provisioning the resource,
                or None if provisioning is not required.
        """
        if await self.requires_provisioning():
            return [
                "Creating an ECS cluster for running Prefect flows:"
                f" [blue]{self._cluster_name}[/]"
            ]
        return []

    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        """
        Provisions an ECS cluster.

        Will update the `cluster` variable in the job template to reference the cluster.

        Args:
            base_job_template: The base job template of the work pool to provision
                infrastructure for.
            advance: A callback function to indicate progress.
        """
        if await self.requires_provisioning():
            console = current_console.get()
            console.print("Provisioning ECS cluster")
            await anyio.to_thread.run_sync(
                partial(self._ecs_client.create_cluster, clusterName=self._cluster_name)
            )
            advance()

        base_job_template["variables"]["properties"]["cluster"][
            "default"
        ] = self._cluster_name

    @property
    def next_steps(self):
        return []


class VpcResource:
    def __init__(
        self,
        vpc_name: str = "prefect-ecs-vpc",
        ecs_security_group_name: str = "prefect-ecs-security-group",
    ):
        self._ec2_client = boto3.client("ec2")
        self._ec2_resource = boto3.resource("ec2")
        self._vpc_name = vpc_name
        self._requires_provisioning = None
        self._ecs_security_group_name = ecs_security_group_name

    async def get_task_count(self):
        """
        Returns the number of tasks that will be executed to provision this resource.

        Returns:
            int: The number of tasks to be provisioned.
        """
        return 4 if await self.requires_provisioning() else 0

    async def _default_vpc_exists(self):
        response = await anyio.to_thread.run_sync(self._ec2_client.describe_vpcs)
        default_vpc = next(
            (
                vpc
                for vpc in response["Vpcs"]
                if vpc["IsDefault"] and vpc["State"] == "available"
            ),
            None,
        )
        return default_vpc is not None

    async def _get_prefect_created_vpc(self):
        vpcs = await anyio.to_thread.run_sync(
            partial(
                self._ec2_resource.vpcs.filter,
                Filters=[{"Name": "tag:Name", "Values": [self._vpc_name]}],
            )
        )
        return next(iter(vpcs), None)

    async def _get_existing_vpc_cidrs(self):
        response = await anyio.to_thread.run_sync(self._ec2_client.describe_vpcs)
        return [vpc["CidrBlock"] for vpc in response["Vpcs"]]

    async def _find_non_overlapping_cidr(self, default_cidr="172.31.0.0/16"):
        """Find a non-overlapping CIDR block"""
        response = await anyio.to_thread.run_sync(self._ec2_client.describe_vpcs)
        existing_cidrs = [vpc["CidrBlock"] for vpc in response["Vpcs"]]

        base_ip = ipaddress.ip_network(default_cidr)
        new_cidr = base_ip
        while True:
            if any(
                new_cidr.overlaps(ipaddress.ip_network(cidr)) for cidr in existing_cidrs
            ):
                # Increase the network address by the size of the network
                new_network_address = int(new_cidr.network_address) + 2 ** (
                    32 - new_cidr.prefixlen
                )
                try:
                    new_cidr = ipaddress.ip_network(
                        f"{ipaddress.IPv4Address(new_network_address)}/{new_cidr.prefixlen}"
                    )
                except ValueError:
                    raise Exception(
                        "Unable to find a non-overlapping CIDR block in the default"
                        " range"
                    )
            else:
                return str(new_cidr)

    async def requires_provisioning(self) -> bool:
        """
        Check if this resource requires provisioning.

        Returns:
            bool: True if provisioning is required, False otherwise.
        """
        if self._requires_provisioning is not None:
            return self._requires_provisioning

        if await self._default_vpc_exists():
            self._requires_provisioning = False
            return False

        if await self._get_prefect_created_vpc() is not None:
            self._requires_provisioning = False
            return False

        self._requires_provisioning = True
        return True

    async def get_planned_actions(self) -> List[str]:
        """
        Returns a description of the planned actions for provisioning this resource.

        Returns:
            Optional[str]: A description of the planned actions for provisioning the resource,
                or None if provisioning is not required.
        """
        if await self.requires_provisioning():
            new_vpc_cidr = await self._find_non_overlapping_cidr()
            return [
                f"Creating a VPC with CIDR [blue]{new_vpc_cidr}[/] for running"
                f" ECS tasks: [blue]{self._vpc_name}[/]"
            ]
        return []

    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        """
        Provisions a VPC.

        Chooses a CIDR block to avoid conflicting with any existing VPCs. Will update
        the `vpc_id` variable in the job template to reference the VPC.

        Args:
            base_job_template: The base job template of the work pool to provision
                infrastructure for.
            advance: A callback function to indicate progress.
        """
        if await self.requires_provisioning():
            console = current_console.get()
            console.print("Provisioning VPC")
            new_vpc_cidr = await self._find_non_overlapping_cidr()
            vpc = await anyio.to_thread.run_sync(
                partial(self._ec2_resource.create_vpc, CidrBlock=new_vpc_cidr)
            )
            await anyio.to_thread.run_sync(vpc.wait_until_available)
            await anyio.to_thread.run_sync(
                partial(
                    vpc.create_tags,
                    Resources=[vpc.id],
                    Tags=[
                        {
                            "Key": "Name",
                            "Value": self._vpc_name,
                        },
                    ],
                )
            )
            advance()

            console.print("Creating internet gateway")
            internet_gateway = await anyio.to_thread.run_sync(
                self._ec2_resource.create_internet_gateway
            )
            await anyio.to_thread.run_sync(
                partial(
                    vpc.attach_internet_gateway, InternetGatewayId=internet_gateway.id
                )
            )
            advance()

            console.print("Setting up subnets")
            vpc_network = ipaddress.ip_network(new_vpc_cidr)
            subnet_cidrs = list(
                vpc_network.subnets(new_prefix=vpc_network.prefixlen + 2)
            )

            # Create subnets
            azs = (
                await anyio.to_thread.run_sync(
                    self._ec2_client.describe_availability_zones
                )
            )["AvailabilityZones"]
            zones = [az["ZoneName"] for az in azs]
            subnets = []
            for i, subnet_cidr in enumerate(subnet_cidrs[0:3]):
                subnets.append(
                    await anyio.to_thread.run_sync(
                        partial(
                            vpc.create_subnet,
                            CidrBlock=str(subnet_cidr),
                            AvailabilityZone=zones[i],
                        )
                    )
                )

            # Create a Route Table for the public subnet and add a route to the Internet Gateway
            public_route_table = await anyio.to_thread.run_sync(vpc.create_route_table)
            await anyio.to_thread.run_sync(
                partial(
                    public_route_table.create_route,
                    DestinationCidrBlock="0.0.0.0/0",
                    GatewayId=internet_gateway.id,
                )
            )
            await anyio.to_thread.run_sync(
                partial(
                    public_route_table.associate_with_subnet, SubnetId=subnets[0].id
                )
            )
            await anyio.to_thread.run_sync(
                partial(
                    public_route_table.associate_with_subnet, SubnetId=subnets[1].id
                )
            )
            await anyio.to_thread.run_sync(
                partial(
                    public_route_table.associate_with_subnet, SubnetId=subnets[2].id
                )
            )
            advance()

            console.print("Setting up security group")
            # Create a security group to block all inbound traffic
            await anyio.to_thread.run_sync(
                partial(
                    self._ec2_resource.create_security_group,
                    GroupName=self._ecs_security_group_name,
                    Description=(
                        "Block all inbound traffic and allow all outbound traffic"
                    ),
                    VpcId=vpc.id,
                )
            )
            advance()
        else:
            vpc = await self._get_prefect_created_vpc()

        if vpc is not None:
            base_job_template["variables"]["properties"]["vpc_id"]["default"] = str(
                vpc.id
            )

    @property
    def next_steps(self):
        return []


class ContainerRepositoryResource:
    def __init__(self, work_pool_name: str, repository_name: str = "prefect-flows"):
        self._ecr_client = boto3.client("ecr")
        self._repository_name = repository_name
        self._requires_provisioning = None
        self._work_pool_name = work_pool_name
        self._next_steps = []

    async def get_task_count(self):
        """
        Returns the number of tasks that will be executed to provision this resource.

        Returns:
            int: The number of tasks to be provisioned.
        """
        return 3 if await self.requires_provisioning() else 0

    async def _get_prefect_created_registry(self):
        try:
            registries = await anyio.to_thread.run_sync(
                partial(
                    self._ecr_client.describe_repositories,
                    repositoryNames=[self._repository_name],
                )
            )
            return next(iter(registries), None)
        except self._ecr_client.exceptions.RepositoryNotFoundException:
            return None

    async def requires_provisioning(self) -> bool:
        """
        Check if this resource requires provisioning.

        Returns:
            bool: True if provisioning is required, False otherwise.
        """
        if self._requires_provisioning is not None:
            return self._requires_provisioning

        if await self._get_prefect_created_registry() is not None:
            self._requires_provisioning = False
            return False

        self._requires_provisioning = True
        return True

    async def get_planned_actions(self) -> List[str]:
        """
        Returns a description of the planned actions for provisioning this resource.

        Returns:
            Optional[str]: A description of the planned actions for provisioning the resource,
                or None if provisioning is not required.
        """
        if await self.requires_provisioning():
            return [
                "Creating an ECR repository for storing Prefect images:"
                f" [blue]{self._repository_name}[/]"
            ]
        return []

    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        """
        Provisions an ECR repository.

        Args:
            base_job_template: The base job template of the work pool to provision
                infrastructure for.
            advance: A callback function to indicate progress.
        """
        if await self.requires_provisioning():
            console = current_console.get()
            console.print("Provisioning ECR repository")
            response = await anyio.to_thread.run_sync(
                partial(
                    self._ecr_client.create_repository,
                    repositoryName=self._repository_name,
                )
            )
            advance()
            console.print("Authenticating with ECR")
            auth_token = self._ecr_client.get_authorization_token()
            user, passwd = (
                base64.b64decode(
                    auth_token["authorizationData"][0]["authorizationToken"]
                )
                .decode()
                .split(":")
            )
            proxy_endpoint = auth_token["authorizationData"][0]["proxyEndpoint"]
            await run_process(f"docker login -u {user} -p {passwd} {proxy_endpoint}")
            advance()
            console.print("Setting default Docker build namespace")
            namespace = response["repository"]["repositoryUri"].split("/")[0]
            update_current_profile({PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE: namespace})
            self._update_next_steps(namespace)
            advance()

    def _update_next_steps(self, repository_uri: str):
        self._next_steps.extend(
            [
                dedent(
                    f"""\

                    Your default Docker build namespace has been set to [blue]{repository_uri!r}[/].

                    To build and push a Docker image to your newly created repository, use [blue]{self._repository_name!r}[/] as your image name:
                    """
                ),
                Panel(
                    Syntax(
                        dedent(
                            f"""\
                                from prefect import flow
                                from prefect.docker import DockerImage


                                @flow(log_prints=True)
                                def my_flow(name: str = "world"):
                                    print(f"Hello {{name}}! I'm a flow running on ECS!")


                                if __name__ == "__main__":
                                    my_flow.deploy(
                                        name="my-deployment",
                                        work_pool_name="{self._work_pool_name}",
                                        image=DockerImage(
                                            name="{self._repository_name}:latest",
                                            platform="linux/amd64",
                                        )
                                    )"""
                        ),
                        "python",
                        background_color="default",
                    ),
                    title="example_deploy_script.py",
                    expand=False,
                ),
            ]
        )

    @property
    def next_steps(self):
        return self._next_steps


class ExecutionRoleResource:
    def __init__(self, execution_role_name: str = "PrefectEcsTaskExecutionRole"):
        self._iam_client = boto3.client("iam")
        self._execution_role_name = execution_role_name
        self._trust_policy_document = json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        )
        self._requires_provisioning = None

    async def get_task_count(self):
        """
        Returns the number of tasks that will be executed to provision this resource.

        Returns:
            int: The number of tasks to be provisioned.
        """
        return 1 if await self.requires_provisioning() else 0

    async def requires_provisioning(self) -> bool:
        """
        Check if this resource requires provisioning.

        Returns:
            bool: True if provisioning is required, False otherwise.
        """
        if self._requires_provisioning is None:
            try:
                await anyio.to_thread.run_sync(
                    partial(
                        self._iam_client.get_role, RoleName=self._execution_role_name
                    )
                )
                self._requires_provisioning = False
            except self._iam_client.exceptions.NoSuchEntityException:
                self._requires_provisioning = True

        return self._requires_provisioning

    async def get_planned_actions(self) -> List[str]:
        """
        Returns a description of the planned actions for provisioning this resource.

        Returns:
            Optional[str]: A description of the planned actions for provisioning the resource,
                or None if provisioning is not required.
        """
        if await self.requires_provisioning():
            return [
                "Creating an IAM role assigned to ECS tasks:"
                f" [blue]{self._execution_role_name}[/]"
            ]
        return []

    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        """
        Provisions an IAM role.

        Args:
            base_job_template: The base job template of the work pool to provision
                infrastructure for.
            advance: A callback function to indicate progress.
        """
        if await self.requires_provisioning():
            console = current_console.get()
            console.print("Provisioning execution role")
            response = await anyio.to_thread.run_sync(
                partial(
                    self._iam_client.create_role,
                    RoleName=self._execution_role_name,
                    Description="Role for ECS tasks to access ECR and other resources.",
                    AssumeRolePolicyDocument=self._trust_policy_document,
                )
            )
            await anyio.to_thread.run_sync(
                partial(
                    self._iam_client.attach_role_policy,
                    RoleName=self._execution_role_name,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
                )
            )
            advance()
        else:
            response = await anyio.to_thread.run_sync(
                partial(self._iam_client.get_role, RoleName=self._execution_role_name)
            )

        base_job_template["variables"]["properties"]["execution_role_arn"][
            "default"
        ] = response["Role"]["Arn"]
        return response["Role"]["Arn"]

    @property
    def next_steps(self):
        return []


class ElasticContainerServicePushProvisioner:
    """
    An infrastructure provisioner for ECS push work pools.
    """

    def __init__(self):
        self._console = Console()

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, value):
        self._console = value

    async def _prompt_boto3_installation(self):
        global boto3
        await run_process(
            [shlex.quote(sys.executable), "-m", "pip", "install", "boto3"]
        )
        boto3 = importlib.import_module("boto3")

    @staticmethod
    def is_boto3_installed():
        """
        Check if boto3 is installed.
        """
        try:
            importlib.import_module("boto3")
            return True
        except ModuleNotFoundError:
            return False

    def _generate_resources(
        self,
        work_pool_name: str,
        user_name: str = "prefect-ecs-user",
        policy_name: str = "prefect-ecs-policy",
        credentials_block_name: Optional[str] = None,
        cluster_name: str = "prefect-ecs-cluster",
        vpc_name: str = "prefect-ecs-vpc",
        ecs_security_group_name: str = "prefect-ecs-security-group",
        repository_name: str = "prefect-flows",
    ):
        return [
            AuthenticationResource(
                work_pool_name=work_pool_name,
                user_name=user_name,
                policy_name=policy_name,
                credentials_block_name=credentials_block_name,
            ),
            ClusterResource(cluster_name=cluster_name),
            VpcResource(
                vpc_name=vpc_name,
                ecs_security_group_name=ecs_security_group_name,
            ),
            ContainerRepositoryResource(
                work_pool_name=work_pool_name,
                repository_name=repository_name,
            ),
        ]

    async def provision(
        self,
        work_pool_name: str,
        base_job_template: dict,
    ) -> Dict[str, Any]:
        """
        Provisions the infrastructure for an ECS push work pool.

        Args:
            work_pool_name: The name of the work pool to provision infrastructure for.
            base_job_template: The base job template of the work pool to provision
                infrastructure for.

        Returns:
            dict: An updated copy base job template.
        """
        if not self.is_boto3_installed():
            if self.console.is_interactive and Confirm.ask(
                "boto3 is required to configure your AWS account. Would you like to"
                " install it?"
            ):
                await self._prompt_boto3_installation()
            else:
                raise RuntimeError(
                    "boto3 is required to configure your AWS account. Please install it"
                    " and try again."
                )

        try:
            if self.console.is_interactive and Confirm.ask(
                "Would you like to customize the resource names for your"
                " infrastructure? This includes an IAM user, IAM policy, ECS cluster,"
                " VPC, ECS security group, and ECR repository."
            ):
                user_name = prompt(
                    "Enter a name for the IAM user (manages ECS tasks)",
                    default="prefect-ecs-user",
                )
                policy_name = prompt(
                    (
                        "Enter a name for the IAM policy (defines ECS task execution"
                        " and image management permissions)"
                    ),
                    default="prefect-ecs-policy",
                )
                cluster_name = prompt(
                    "Enter a name for the ECS cluster (hosts ECS tasks)",
                    default="prefect-ecs-cluster",
                )
                credentials_name = prompt(
                    (
                        "Enter a name for the AWS credentials block (stores AWS"
                        " credentials for managing ECS tasks)"
                    ),
                    default=f"{work_pool_name}-aws-credentials",
                )
                vpc_name = prompt(
                    (
                        "Enter a name for the VPC (provides network isolation for ECS"
                        " tasks)"
                    ),
                    default="prefect-ecs-vpc",
                )
                ecs_security_group_name = prompt(
                    (
                        "Enter a name for the ECS security group (controls task network"
                        " traffic)"
                    ),
                    default="prefect-ecs-security-group",
                )
                repository_name = prompt(
                    (
                        "Enter a name for the ECR repository (stores Docker images for"
                        " ECS tasks)"
                    ),
                    default="prefect-flows",
                )

                provision_preview = Panel(
                    dedent(
                        f"""\
                            Custom names for infrastructure resources for
                            [blue]{work_pool_name}[/]:

                            - IAM user: [blue]{user_name}[/]
                            - IAM policy: [blue]{policy_name}[/]
                            - ECS cluster: [blue]{cluster_name}[/]
                            - AWS credentials block: [blue]{credentials_name}[/]
                            - VPC: [blue]{vpc_name}[/]
                            - ECS security group: [blue]{ecs_security_group_name}[/]
                            - ECR repository: [blue]{repository_name}[/]
                            """
                    ),
                    expand=False,
                )

                self.console.print(provision_preview)

                resources = self._generate_resources(
                    work_pool_name=work_pool_name,
                    user_name=user_name,
                    policy_name=policy_name,
                    credentials_block_name=credentials_name,
                    cluster_name=cluster_name,
                    vpc_name=vpc_name,
                    ecs_security_group_name=ecs_security_group_name,
                    repository_name=repository_name,
                )

            else:
                resources = self._generate_resources(work_pool_name=work_pool_name)

            with Progress(
                SpinnerColumn(),
                TextColumn(
                    "Checking your AWS account for infrastructure that needs to be"
                    " provisioned..."
                ),
                transient=True,
                console=self.console,
            ) as progress:
                inspect_aws_account_task = progress.add_task(
                    "inspect_aws_account", total=1
                )
                num_tasks = sum(
                    [await resource.get_task_count() for resource in resources]
                )
                progress.update(inspect_aws_account_task, completed=1)

            if num_tasks > 0:
                message = (
                    "Provisioning infrastructure for your work pool"
                    f" [blue]{work_pool_name}[/] will require: \n"
                )
                for resource in resources:
                    planned_actions = await resource.get_planned_actions()
                    for action in planned_actions:
                        message += f"\n\t - {action}"

                self.console.print(Panel(message))

                if self._console.is_interactive:
                    if not Confirm.ask(
                        "Proceed with infrastructure provisioning?",
                        console=self._console,
                    ):
                        return base_job_template
            else:
                self.console.print(
                    "No additional infrastructure required for work pool"
                    f" [blue]{work_pool_name}[/]"
                )
                # don't return early, we still need to update the base job template
                # provision calls will be no-ops, but update the base job template

            base_job_template_copy = deepcopy(base_job_template)
            next_steps = []
            with Progress(console=self._console, disable=num_tasks == 0) as progress:
                task = progress.add_task(
                    "Provisioning Infrastructure",
                    total=num_tasks,
                )
                for resource in resources:
                    with console_context(progress.console):
                        await resource.provision(
                            advance=partial(progress.advance, task),
                            base_job_template=base_job_template_copy,
                        )
                    next_steps.append(resource.next_steps)

            if next_steps:
                for step in next_steps:
                    for item in step:
                        self._console.print(item)

            if num_tasks > 0:
                self._console.print(
                    "Infrastructure successfully provisioned!", style="green"
                )

            return base_job_template_copy
        except Exception as exc:
            if hasattr(exc, "response"):
                # Catching boto3 ClientError
                response = getattr(exc, "response", {})
                error_message = get_from_dict(response, "Error.Message") or str(exc)
                raise RuntimeError(error_message) from exc
            # Catching any other exception
            raise RuntimeError(str(exc)) from exc

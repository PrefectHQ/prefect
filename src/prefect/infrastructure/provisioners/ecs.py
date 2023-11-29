import asyncio
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
from typing import Any, Callable, Dict, Optional

from anyio import run_process
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.prompt import Confirm

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.client.utilities import inject_client
from prefect.exceptions import ObjectNotFound
from prefect.utilities.importtools import lazy_import

boto3 = docker = lazy_import("boto3")

current_console = contextvars.ContextVar("console", default=Console())


@contextlib.contextmanager
def console_context(value: Console):
    token = current_console.set(value)
    try:
        yield
    finally:
        current_console.reset(token)


class IamPolicyResource:
    def __init__(
        self,
        policy_name: str = "prefect-ecs-policy",
        attached_user_name: str = "prefect-ecs-user",
    ):
        self._iam_client = boto3.client("iam")
        self._policy_name = policy_name
        self._attached_user_name = attached_user_name
        self._policy_document = dedent(
            json.dumps(
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
                                "logs:GetLogEvents",
                            ],
                            "Resource": "*",
                        }
                    ],
                }
            )
        )
        self._requires_provisioning = None

    async def get_task_count(self):
        return 1 if await self.requires_provisioning() else 0

    async def requires_provisioning(self) -> bool:
        if self._requires_provisioning is not None:
            return self._requires_provisioning
        paginator = self._iam_client.get_paginator("list_policies")
        page_iterator = paginator.paginate(Scope="Local")

        for page in page_iterator:
            for policy in page["Policies"]:
                if policy["PolicyName"] == self._policy_name:
                    self._requires_provisioning = False
                    return False

        self._requires_provisioning = True
        return True

    async def get_planned_actions(self) -> Optional[str]:
        if await self.requires_provisioning():
            return (
                "Creating and attaching an IAM policy for managing ECS tasks:"
                f" [blue]{self._policy_name}[/]"
            )

    async def provision(
        self,
        advance: Callable[[], None],
    ):
        if await self.requires_provisioning():
            console = current_console.get()
            console.print("Creating IAM policy")
            policy = self._iam_client.create_policy(
                PolicyName=self._policy_name,
                PolicyDocument=self._policy_document,
            )
            policy_arn = policy["Policy"]["Arn"]
            advance()
            return policy_arn


class IamUserResource:
    def __init__(self, user_name: str):
        self._iam_client = boto3.client("iam")
        self._user_name = user_name
        self._requires_provisioning = None

    async def get_task_count(self):
        return 1 if await self.requires_provisioning() else 0

    async def requires_provisioning(self) -> bool:
        if self._requires_provisioning is None:
            try:
                await asyncio.to_thread(
                    self._iam_client.get_user, UserName=self._user_name
                )
                self._requires_provisioning = False
            except self._iam_client.exceptions.NoSuchEntityException:
                self._requires_provisioning = True

        return self._requires_provisioning

    async def get_planned_actions(self) -> Optional[str]:
        if await self.requires_provisioning():
            return (
                "Creating an IAM user for managing ECS tasks:"
                f" [blue]{self._user_name}[/]"
            )

    async def provision(
        self,
        advance: Callable[[], None],
    ):
        console = current_console.get()
        if await self.requires_provisioning():
            console.print("Provisioning IAM user")
            self._iam_client.create_user(UserName=self._user_name)
            advance()


class CredentialsBlockResource:
    def __init__(self, user_name: str, block_document_name: str):
        self._block_document_name = block_document_name
        self._user_name = user_name
        self._requires_provisioning = None

    async def get_task_count(self):
        return 2 if await self.requires_provisioning() else 0

    @inject_client
    async def requires_provisioning(
        self, client: Optional[PrefectClient] = None
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

    async def get_planned_actions(self) -> Optional[str]:
        if await self.requires_provisioning():
            return "Storing generated AWS credentials in a block"

    @inject_client
    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
        client: Optional[PrefectClient] = None,
    ):
        assert client is not None, "Client injection failed"
        if not await self.requires_provisioning():
            block_doc = await client.read_block_document_by_name(
                self._block_document_name, "aws-credentials"
            )
        else:
            console = current_console.get()
            console.print("Generating AWS credentials")
            iam_client = boto3.client("iam")
            access_key_data = iam_client.create_access_key(UserName=self._user_name)
            access_key = access_key_data["AccessKey"]
            advance()
            console.print("Creating AWS credentials block")
            assert client is not None
            credentials_block_type = await client.read_block_type_by_slug(
                "aws-credentials"
            )

            credentials_block_schema = (
                await client.get_most_recent_block_schema_for_block_type(
                    block_type_id=credentials_block_type.id
                )
            )

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
            "$ref": {"block_document_id": block_doc.id}
        }


class AuthenticationResource:
    def __init__(
        self,
        work_pool_name: str,
        user_name: str = "prefect-ecs-user",
        policy_name: str = "prefect-ecs-policy",
    ):
        self._user_name = user_name
        self._policy_name = policy_name
        self._iam_user_resource = IamUserResource(user_name=user_name)
        self._iam_policy_resource = IamPolicyResource(policy_name=policy_name)
        self._credentials_block_resource = CredentialsBlockResource(
            user_name=user_name, block_document_name=f"{work_pool_name}-aws-credentials"
        )

    @property
    def resources(self):
        return [
            self._iam_user_resource,
            self._iam_policy_resource,
            self._credentials_block_resource,
        ]

    async def get_task_count(self):
        return sum(
            [
                await resource.get_task_count()
                for resource in self.resources
                if resource != self._credentials_block_resource
            ]
        )

    async def requires_provisioning(self) -> bool:
        return any(
            [await resource.requires_provisioning() for resource in self.resources]
        )

    async def get_planned_actions(self) -> Optional[str]:
        planned_actions = [
            await resource.get_planned_actions() for resource in self.resources
        ]
        if not planned_actions:
            return None
        return "\n\t - ".join(
            [
                planned_action
                for planned_action in planned_actions
                if planned_action is not None
            ]
        )

    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        # Provision the IAM user
        await self._iam_user_resource.provision(advance=advance)
        # Provision the IAM policy
        policy_arn = await self._iam_policy_resource.provision(advance=advance)
        # Attach the policy to the user
        if policy_arn:
            iam_client = boto3.client("iam")
            iam_client.attach_user_policy(
                UserName=self._user_name,
                PolicyArn=policy_arn,
            )
        if await self._credentials_block_resource.requires_provisioning():
            await self._credentials_block_resource.provision(
                base_job_template=base_job_template,
                advance=advance,
            )


class ClusterResource:
    def __init__(self, cluster_name: str = "prefect-ecs-cluster"):
        self._ecs_client = boto3.client("ecs")
        self._cluster_name = cluster_name
        self._requires_provisioning = None

    async def get_task_count(self):
        return 1 if await self.requires_provisioning() else 0

    async def requires_provisioning(self) -> bool:
        if self._requires_provisioning is None:
            response = self._ecs_client.describe_clusters(clusters=[self._cluster_name])
            if response["clusters"] and response["clusters"][0]["status"] == "ACTIVE":
                self._requires_provisioning = False
            else:
                self._requires_provisioning = True
        return self._requires_provisioning

    async def get_planned_actions(self) -> Optional[str]:
        if await self.requires_provisioning():
            return (
                "Creating an ECS cluster for running Prefect flows:"
                f" [blue]{self._cluster_name}[/]"
            )

    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        console = current_console.get()
        console.print("Provisioning ECS cluster")
        self._ecs_client.create_cluster(clusterName=self._cluster_name)
        base_job_template["variables"]["properties"]["cluster"][
            "default"
        ] = self._cluster_name

        advance()


class VpcResource:
    def __init__(self, vpc_name: str = "prefect-ecs-vpc"):
        self._ec2_client = boto3.client("ec2")
        self._ec2_resource = boto3.resource("ec2")
        self._vpc_name = vpc_name
        self._new_vpc_cidr = self._find_non_overlapping_cidr()
        self._requires_provisioning = None

    async def get_task_count(self):
        return 5 if await self.requires_provisioning() else 0

    def _get_existing_vpc_cidrs(self):
        response = self._ec2_client.describe_vpcs()
        return [vpc["CidrBlock"] for vpc in response["Vpcs"]]

    def _find_non_overlapping_cidr(self, default_cidr="172.31.0.0/16"):
        """Find a non-overlapping CIDR block"""
        response = self._ec2_client.describe_vpcs()
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
        if self._requires_provisioning is not None:
            return self._requires_provisioning

        response = self._ec2_client.describe_vpcs()
        default_vpc = next(
            (
                vpc
                for vpc in response["Vpcs"]
                if vpc["IsDefault"] and vpc["State"] == "available"
            ),
            None,
        )
        if default_vpc:
            self._requires_provisioning = False
            return False

        prefect_created_vpc = next(
            (
                vpc
                for vpc in response["Vpcs"]
                if vpc["Tags"]
                and any(
                    tag["Key"] == "Name" and tag["Value"] == self._vpc_name
                    for tag in vpc["Tags"]
                )
            ),
            None,
        )
        if prefect_created_vpc:
            self._requires_provisioning = False
            return False

        self._requires_provisioning = True
        return True

    async def get_planned_actions(self) -> Optional[str]:
        if await self.requires_provisioning():
            return (
                f"Creating a VPC with CIDR [blue]{self._new_vpc_cidr}[/] for running"
                f" ECS tasks: [blue]{self._vpc_name}[/]"
            )

    async def provision(
        self,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        console = current_console.get()
        console.print("Provisioning VPC")
        vpc = self._ec2_resource.create_vpc(CidrBlock=self._new_vpc_cidr)
        vpc.wait_until_available()
        vpc.create_tags(
            Resources=[vpc.id],
            Tags=[
                {
                    "Key": "Name",
                    "Value": self._vpc_name,
                },
            ],
        )
        advance()

        console.print("Creating internet gateway")
        internet_gateway = self._ec2_resource.create_internet_gateway()
        vpc.attach_internet_gateway(InternetGatewayId=internet_gateway.id)
        advance()

        console.print("Setting up subnets")
        vpc_network = ipaddress.ip_network(self._new_vpc_cidr)
        subnet_cidrs = list(vpc_network.subnets(new_prefix=vpc_network.prefixlen + 2))

        # Create subnets
        subnets = [
            vpc.create_subnet(CidrBlock=str(subnet_cidr))
            for subnet_cidr in subnet_cidrs
        ]

        # Create a Route Table for the public subnet and add a route to the Internet Gateway
        public_route_table = vpc.create_route_table()
        public_route_table.create_route(
            DestinationCidrBlock="0.0.0.0/0", GatewayId=internet_gateway.id
        )
        public_route_table.associate_with_subnet(SubnetId=subnets[0].id)
        public_route_table.associate_with_subnet(SubnetId=subnets[1].id)
        public_route_table.associate_with_subnet(SubnetId=subnets[2].id)
        advance()

        console.print("Setting up security group")
        # Create a security group to block all inbound traffic
        self._ec2_resource.create_security_group(
            GroupName="prefect-ecs-security-group",
            Description="Block all inbound traffic and allow all outbound traffic",
            VpcId=vpc.id,
        )
        advance()

        base_job_template["variables"]["properties"]["vpc_id"]["default"] = str(vpc.id)


class ElasticContainerServicePushProvisioner:
    def __init__(self):
        self._console = Console()
        self._user_name = "prefect-ecs-user"

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
        try:
            return True
        except ImportError:
            return False

    def _generate_resources(self, work_pool_name: str):
        return [
            AuthenticationResource(work_pool_name=work_pool_name),
            ClusterResource(),
            VpcResource(),
        ]

    async def provision(
        self,
        work_pool_name: str,
        base_job_template: dict,
    ) -> Dict[str, Any]:
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

        resources = self._generate_resources(work_pool_name=work_pool_name)

        message = (
            f"Provisioning infrastructure for your work pool [blue]{work_pool_name}[/]"
            " will require: \n"
        )
        for resource in resources:
            planned_actions = await resource.get_planned_actions()
            if planned_actions:
                message += f"\n\t - {planned_actions}"

        self.console.print(Panel(message))

        if self._console.is_interactive:
            if not Confirm.ask(
                "Proceed with infrastructure provisioning?", console=self._console
            ):
                return base_job_template

        base_job_template_copy = deepcopy(base_job_template)
        with Progress(console=self._console) as progress:
            task = progress.add_task(
                "Provisioning Infrastructure",
                total=sum([await resource.get_task_count() for resource in resources]),
            )
            for resource in resources:
                with console_context(progress.console):
                    await resource.provision(
                        advance=partial(progress.advance, task),
                        base_job_template=base_job_template_copy,
                    )

        return base_job_template_copy

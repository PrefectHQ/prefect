import importlib
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


class IamPolicyResource:
    def __init__(
        self,
        policy_name: str = "prefect-ecs-policy",
        attached_user_name: str = "prefect-ecs-user",
    ):
        self._console = Console()
        self._iam_client = boto3.client("iam")
        self._policy_name = policy_name
        self._attached_user_name = attached_user_name
        self._policy_document = dedent(
            """\
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
                            "ec2:DeleteSecurityGroup",
                            "ecs:CreateCluster",
                            "ecs:DeleteCluster",
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
            """
        )

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, value):
        self._console = value

    @property
    def num_tasks(self):
        return 2

    async def check_if_needs_provisioning(self, work_pool_name: str) -> bool:
        try:
            self._iam_client.get_policy(PolicyArn=self._policy_name)
            return False
        except self._iam_client.exceptions.NoSuchEntityException:
            return True

    def get_planned_actions(self) -> str:
        return (
            "Creating and attaching an IAM policy for managing ECS tasks:"
            f" [blue]{self._policy_name}[/]"
        )

    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        self.console.print("Provisioning IAM policy")
        policy = self._iam_client.create_policy(
            PolicyName=self._policy_name,
            PolicyDocument=self._policy_document,
        )
        policy_arn = policy["Policy"]["Arn"]
        advance()
        self.console.print("Attaching IAM policy to user")
        self._iam_client.attach_user_policy(
            UserName=self._attached_user_name,
            PolicyArn=policy_arn,
        )
        advance()


class IamUserResource:
    def __init__(self, user_name: str = "prefect-ecs-user"):
        self._console = Console()
        self._iam_client = boto3.client("iam")
        self._user_name = user_name
        self._role_name = "prefect-ecs-role"
        self._policy_name = "prefect-ecs-policy"
        self._child_resources = [IamPolicyResource(self._policy_name)]

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, value):
        self._console = value

    @property
    def num_tasks(self):
        return 1 + sum(resource.num_tasks for resource in self._child_resources)

    async def check_if_needs_provisioning(self, work_pool_name: str) -> bool:
        try:
            self._iam_client.get_user(UserName=self._user_name)
            return False
        except self._iam_client.exceptions.NoSuchEntityException:
            return True

    def get_planned_actions(self) -> str:
        message = (
            f"Creating an IAM user for managing ECS tasks: [blue]{self._user_name}[/]"
        )
        for resource in self._child_resources:
            message += f"\n\t - {resource.get_planned_actions()}"
        return message

    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        self._console.print("Provisioning IAM user")
        self._iam_client.create_user(UserName=self._user_name)
        advance()
        for resource in self._child_resources:
            resource.console = self._console
            await resource.provision(work_pool_name, base_job_template, advance)


class ClusterResource:
    def __init__(self, cluster_name: str = "prefect-ecs-cluster"):
        self._console = Console()
        self._ecs_client = boto3.client("ecs")
        self._cluster_name = cluster_name

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, value):
        self._console = value

    @property
    def num_tasks(self):
        return 1

    async def check_if_needs_provisioning(self, work_pool_name: str) -> bool:
        response = self._ecs_client.describe_clusters(clusters=[self._cluster_name])
        if response["clusters"] and response["clusters"][0]["status"] == "ACTIVE":
            return False
        else:
            return True

    def get_planned_actions(self) -> str:
        return (
            "Creating an ECS cluster for running Prefect tasks:"
            f" [blue]{self._cluster_name}[/]"
        )

    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
    ):
        self.console.print("Provisioning ECS cluster")
        self._ecs_client.create_cluster(clusterName=self._cluster_name)
        base_job_template["variables"]["properties"]["cluster"][
            "default"
        ] = self._cluster_name

        advance()


class CredentialsResource:
    def __init__(self, user_name: str):
        self._console = Console()
        self._iam_client = boto3.client("iam")
        self._user_name = user_name

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, value):
        self._console = value

    @property
    def num_tasks(self):
        return 2

    @inject_client
    async def check_if_needs_provisioning(
        self, work_pool_name: str, client: Optional[PrefectClient] = None
    ) -> bool:
        try:
            assert client is not None
            await client.read_block_document_by_name(
                f"{work_pool_name}-push-pool-credentials", "aws-credentials"
            )
            return False
        except ObjectNotFound:
            return True

    def get_planned_actions(self) -> str:
        return "Generating AWS credentials and storing them in a block"

    @inject_client
    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        advance: Callable[[], None],
        client: Optional[PrefectClient] = None,
    ):
        self.console.print("Generating AWS credentials")
        access_key_data = self._iam_client.create_access_key(UserName=self._user_name)
        access_key = access_key_data["AccessKey"]
        advance()
        self.console.print("Creating AWS credentials block")
        assert client is not None
        credentials_block_type = await client.read_block_type_by_slug("aws-credentials")

        credentials_block_schema = (
            await client.get_most_recent_block_schema_for_block_type(
                block_type_id=credentials_block_type.id
            )
        )

        block_doc = await client.create_block_document(
            block_document=BlockDocumentCreate(
                name=f"{work_pool_name}-push-pool-credentials",
                data={
                    "aws_access_key_id": access_key["AccessKeyId"],
                    "aws_secret_access_key": access_key["SecretAccessKey"],
                    "region_name": boto3.session.Session().region_name,
                },
                block_type_id=credentials_block_type.id,
                block_schema_id=credentials_block_schema.id,
            )
        )
        base_job_template["variables"]["properties"]["aws_credentials"]["default"] = {
            "$ref": {"block_document_id": block_doc.id}
        }

        advance()


class ElasticContainerServiceProvisioner:
    def __init__(self):
        self._console = Console()
        self._user_name = "prefect-ecs-user"
        self._resources = [
            IamUserResource(self._user_name),
            ClusterResource(),
            # TODO: Add VPC resource here
            # TODO: Add security group resource here
            CredentialsResource(self._user_name),
        ]

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

        resources_to_provision = [
            resource
            for resource in self._resources
            if await resource.check_if_needs_provisioning(work_pool_name)
        ]

        if not resources_to_provision:
            return base_job_template

        message = (
            f"Provisioning infrastructure for your work pool [blue]{work_pool_name}[/]"
            " will require: \n"
        )
        for resource in resources_to_provision:
            message += f"\n\t - {resource.get_planned_actions()}"

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
                total=sum(resource.num_tasks for resource in resources_to_provision),
            )
            for resource in resources_to_provision:
                resource.console = progress.console
                await resource.provision(
                    advance=partial(progress.advance, task),
                    work_pool_name=work_pool_name,
                    base_job_template=base_job_template_copy,
                )

        return base_job_template_copy

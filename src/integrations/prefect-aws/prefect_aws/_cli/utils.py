"""Utility functions for AWS operations and CLI helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

import boto3
import typer
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from typing_extensions import overload

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolUpdate

try:
    from importlib.resources import files
except ImportError:
    # Python < 3.9 fallback
    from importlib_resources import files

if TYPE_CHECKING:
    from mypy_boto3_cloudformation.client import CloudFormationClient
    from mypy_boto3_ec2.client import EC2Client
    from mypy_boto3_ecs.client import ECSClient
    from mypy_boto3_sts.client import STSClient

console = Console()

# Tags that identify stacks deployed by this CLI
CLI_TAGS = {
    "ManagedBy": "prefect-aws-cli",
    "DeploymentType": "ecs-worker",
}


def get_template_path(template_name: str) -> str:
    """Get the path to a CloudFormation template.

    Args:
        template_name: Name of the template file (e.g., 'service.json')

    Returns:
        Path to the template file
    """
    try:
        template_files = files("prefect_aws.templates.ecs")
        template_path = template_files / template_name
        return str(template_path)
    except (ImportError, FileNotFoundError) as e:
        typer.echo(f"Error: Could not find template {template_name}: {e}", err=True)
        raise typer.Exit(1)


def load_template(template_name: str) -> dict[str, Any]:
    """Load a CloudFormation template from the templates directory.

    Args:
        template_name: Name of the template file

    Returns:
        Template content as a dictionary
    """
    try:
        template_files = files("prefect_aws.templates.ecs")
        template_content = (template_files / template_name).read_text()
        return json.loads(template_content)
    except (ImportError, FileNotFoundError, json.JSONDecodeError) as e:
        typer.echo(f"Error loading template {template_name}: {e}", err=True)
        raise typer.Exit(1)


@overload
def get_aws_client(
    service: Literal["sts"],
    region: str | None = None,
    profile: str | None = None,
) -> STSClient:
    pass


@overload
def get_aws_client(
    service: Literal["ecs"],
    region: str | None = None,
    profile: str | None = None,
) -> ECSClient:
    pass


@overload
def get_aws_client(
    service: Literal["cloudformation"],
    region: str | None = None,
    profile: str | None = None,
) -> CloudFormationClient:
    pass


@overload
def get_aws_client(
    service: Literal["ec2"],
    region: str | None = None,
    profile: str | None = None,
) -> EC2Client:
    pass


def get_aws_client(
    service: Literal["sts", "ecs", "cloudformation", "ec2"],
    region: str | None = None,
    profile: str | None = None,
):
    """Get an AWS client with error handling.

    Args:
        service: AWS service name (e.g., 'cloudformation', 'ecs')
        region: AWS region
        profile: AWS profile name

    Returns:
        Boto3 client
    """
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        return session.client(service)
    except NoCredentialsError:
        typer.echo(
            "Error: AWS credentials not found. Please configure your credentials.",
            err=True,
        )
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error creating AWS client: {e}", err=True)
        raise typer.Exit(1)


def validate_aws_credentials(
    region: str | None = None, profile: str | None = None
) -> bool:
    """Validate that AWS credentials are available and working.

    Args:
        region: AWS region
        profile: AWS profile name

    Returns:
        True if credentials are valid
    """
    try:
        sts = get_aws_client("sts", region, profile)
        sts.get_caller_identity()
        return True
    except Exception:
        return False


def add_cli_tags(work_pool_name: str, stack_type: str) -> list[dict[str, str]]:
    """Add CLI-specific tags to a CloudFormation stack.

    Args:
        work_pool_name: Name of the work pool
        stack_type: Type of stack ('service' or 'events')

    Returns:
        List of tags for CloudFormation
    """
    tags = [{"Key": k, "Value": v} for k, v in CLI_TAGS.items()]
    tags.extend(
        [
            {"Key": "StackType", "Value": stack_type},
            {"Key": "WorkPoolName", "Value": work_pool_name},
            {"Key": "CreatedAt", "Value": datetime.now(timezone.utc).isoformat()},
        ]
    )
    return tags


def list_cli_deployed_stacks(cf_client) -> list[dict[str, Any]]:
    """List all stacks deployed by this CLI.

    Args:
        cf_client: CloudFormation client

    Returns:
        List of stack information dictionaries
    """
    try:
        paginator = cf_client.get_paginator("describe_stacks")
        cli_stacks = []

        for page in paginator.paginate():
            for stack in page["Stacks"]:
                if stack["StackStatus"] in ["DELETE_COMPLETE"]:
                    continue

                tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}

                # Check if stack was deployed by CLI
                if (
                    tags.get("ManagedBy") == CLI_TAGS["ManagedBy"]
                    and tags.get("DeploymentType") == CLI_TAGS["DeploymentType"]
                ):
                    stack_info = {
                        "StackName": stack["StackName"],
                        "StackStatus": stack["StackStatus"],
                        "CreationTime": stack["CreationTime"],
                        "WorkPoolName": tags.get("WorkPoolName", "Unknown"),
                        "StackType": tags.get("StackType", "Unknown"),
                        "Description": stack.get("Description", ""),
                    }
                    if "LastUpdatedTime" in stack:
                        stack_info["LastUpdatedTime"] = stack["LastUpdatedTime"]

                    cli_stacks.append(stack_info)

        return cli_stacks
    except ClientError as e:
        typer.echo(f"Error listing stacks: {e}", err=True)
        raise typer.Exit(1)


def validate_stack_is_cli_managed(cf_client, stack_name: str) -> bool:
    """Validate that a stack was deployed by this CLI.

    Args:
        cf_client: CloudFormation client
        stack_name: Name of the stack

    Returns:
        True if stack was deployed by CLI
    """
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        stack = response["Stacks"][0]
        tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}

        return (
            tags.get("ManagedBy") == CLI_TAGS["ManagedBy"]
            and tags.get("DeploymentType") == CLI_TAGS["DeploymentType"]
        )
    except ClientError:
        return False


def deploy_stack(
    cf_client,
    stack_name: str,
    template_body: str,
    parameters: list[dict[str, str]],
    tags: list[dict[str, str]],
    capabilities: list[str] | None = None,
    wait: bool = True,
) -> None:
    """Deploy or update a CloudFormation stack.

    Args:
        cf_client: CloudFormation client
        stack_name: Name of the stack
        template_body: CloudFormation template as JSON string
        parameters: List of parameter dictionaries
        tags: List of tag dictionaries
        capabilities: IAM capabilities if required
        wait: Whether to wait for the stack operation to complete
    """
    if capabilities is None:
        capabilities = ["CAPABILITY_NAMED_IAM"]

    operation = "create"
    try:
        # Check if stack exists
        try:
            cf_client.describe_stacks(StackName=stack_name)
            stack_exists = True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ValidationError":
                stack_exists = False
            else:
                raise

        operation = "update" if stack_exists else operation

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]{operation.capitalize()}ing stack {stack_name}..."
            )

            if stack_exists:
                try:
                    cf_client.update_stack(
                        StackName=stack_name,
                        TemplateBody=template_body,
                        Parameters=parameters,
                        Tags=tags,
                        Capabilities=capabilities,
                    )
                except ClientError as e:
                    if "No updates are to be performed" in str(e):
                        progress.update(
                            task,
                            description=f"[green]Stack {stack_name} is already up to date",
                        )
                        return
                    raise
            else:
                cf_client.create_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Tags=tags,
                    Capabilities=capabilities,
                )

            if wait:
                # Wait for operation to complete
                waiter_name = f"stack_{operation}_complete"
                waiter = cf_client.get_waiter(waiter_name)

                progress.update(
                    task, description=f"[yellow]Waiting for {operation} to complete..."
                )
                waiter.wait(
                    StackName=stack_name, WaiterConfig={"Delay": 10, "MaxAttempts": 120}
                )

                progress.update(
                    task,
                    description=f"[green]Stack {stack_name} {operation}d successfully!",
                )
            else:
                progress.update(
                    task,
                    description=f"[green]Stack {stack_name} {operation} initiated. Check status with: prefect-aws ecs-worker status {stack_name}",
                )

    except ClientError as e:
        error_msg = e.response.get("Error", {}).get("Message")
        typer.echo(
            f"Error performing {operation} action for stack: {error_msg}", err=True
        )
        raise typer.Exit(1)


def delete_stack(cf_client, stack_name: str, wait: bool = True) -> None:
    """Delete a CloudFormation stack.

    Args:
        cf_client: CloudFormation client
        stack_name: Name of the stack
        wait: Whether to wait for the stack deletion to complete
    """
    try:
        # Validate stack is CLI-managed
        if not validate_stack_is_cli_managed(cf_client, stack_name):
            typer.echo(
                f"Error: Stack '{stack_name}' was not deployed by prefect-aws CLI",
                err=True,
            )
            raise typer.Exit(1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[red]Deleting stack {stack_name}...")

            cf_client.delete_stack(StackName=stack_name)

            if wait:
                # Wait for deletion to complete
                waiter = cf_client.get_waiter("stack_delete_complete")
                progress.update(
                    task, description="[yellow]Waiting for deletion to complete..."
                )
                waiter.wait(
                    StackName=stack_name, WaiterConfig={"Delay": 10, "MaxAttempts": 120}
                )

                progress.update(
                    task, description=f"[green]Stack {stack_name} deleted successfully!"
                )
            else:
                progress.update(
                    task,
                    description=f"[green]Stack {stack_name} deletion initiated. Check status with: prefect-aws ecs-worker status {stack_name}",
                )

    except ClientError as e:
        if (code := e.response.get("Error", {}).get("Code")) == "ValidationError":
            typer.echo(f"Error: Stack '{stack_name}' not found", err=True)
        else:
            typer.echo(f"Error deleting stack: {code}", err=True)
        raise typer.Exit(1)


def get_stack_status(cf_client, stack_name: str) -> dict[str, Any] | None:
    """Get the status of a CloudFormation stack.

    Args:
        cf_client: CloudFormation client
        stack_name: Name of the stack

    Returns:
        Stack information or None if not found
    """
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        return response["Stacks"][0]
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ValidationError":
            return None
        raise


def display_stacks_table(stacks: list[dict[str, Any]]) -> None:
    """Display stacks in a formatted table.

    Args:
        stacks: List of stack information dictionaries
    """
    if not stacks:
        typer.echo("No stacks found deployed by prefect-aws CLI")
        return

    table = Table(title="ECS Worker Stacks")
    table.add_column("Stack Name", style="cyan")
    table.add_column("Work Pool", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Status", style="magenta")
    table.add_column("Created", style="blue")

    for stack in stacks:
        created_time = stack["CreationTime"].strftime("%B %d, %Y at %I:%M %p UTC")
        table.add_row(
            stack["StackName"],
            stack["WorkPoolName"],
            stack["StackType"],
            stack["StackStatus"],
            created_time,
        )

    console.print(table)


def validate_ecs_cluster(ecs_client, cluster_identifier: str) -> bool:
    """Validate that an ECS cluster exists.

    Args:
        ecs_client: ECS client
        cluster_identifier: Cluster name or ARN

    Returns:
        True if cluster exists
    """
    try:
        response = ecs_client.describe_clusters(clusters=[cluster_identifier])
        clusters = response["clusters"]
        return len(clusters) > 0 and clusters[0]["status"] == "ACTIVE"
    except ClientError:
        return False


def validate_vpc_and_subnets(
    ec2_client, vpc_id: str, subnet_ids: list[str]
) -> tuple[bool, str]:
    """Validate VPC and subnets exist and are compatible.

    Args:
        ec2_client: EC2 client
        vpc_id: VPC ID
        subnet_ids: List of subnet IDs

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Validate VPC exists
        vpc_response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
        if not vpc_response["Vpcs"]:
            return False, f"VPC {vpc_id} not found"

        # Validate subnets exist and belong to VPC
        subnet_response = ec2_client.describe_subnets(SubnetIds=subnet_ids)
        for subnet in subnet_response["Subnets"]:
            if subnet["VpcId"] != vpc_id:
                return False, f"Subnet {subnet['SubnetId']} is not in VPC {vpc_id}"

        return True, ""
    except ClientError as e:
        return False, str(e)


def update_work_pool_defaults(
    work_pool_name: str,
    stack_outputs: dict[str, str],
) -> None:
    """Update work pool base job template defaults with stack deployment values.

    Only updates fields that are currently empty/null to preserve user customizations.

    Args:
        work_pool_name: Name of the work pool to update
        stack_outputs: CloudFormation stack outputs containing infrastructure values
    """
    try:
        with get_client(sync_client=True) as client:
            # Get current work pool
            try:
                work_pool = client.read_work_pool(work_pool_name)
            except Exception:
                return

            # Get current base job template
            base_template = work_pool.base_job_template
            if not base_template or "variables" not in base_template:
                return

            variables = base_template["variables"]
            properties = variables.get("properties", {})

            # Update VPC ID default if not set (treat None as empty)
            vpc_id_prop = properties.get("vpc_id", {})
            current_default = vpc_id_prop.get("default")
            if (
                current_default is None or not current_default
            ) and "VpcId" in stack_outputs:
                vpc_id_prop["default"] = stack_outputs["VpcId"]
                properties["vpc_id"] = vpc_id_prop

            # Update cluster default if not set (treat None as empty)
            cluster_prop = properties.get("cluster", {})
            current_default = cluster_prop.get("default")
            if (
                current_default is None or not current_default
            ) and "ClusterArn" in stack_outputs:
                cluster_prop["default"] = stack_outputs["ClusterArn"]
                properties["cluster"] = cluster_prop

            # Update Prefect API key secret ARN default if not set and we created one (treat None as empty)
            api_key_secret_prop = properties.get("prefect_api_key_secret_arn", {})
            current_default = api_key_secret_prop.get("default")
            if (
                current_default is None or not current_default
            ) and "PrefectApiKeySecretArnOutput" in stack_outputs:
                api_key_secret_prop["default"] = stack_outputs[
                    "PrefectApiKeySecretArnOutput"
                ]
                properties["prefect_api_key_secret_arn"] = api_key_secret_prop

            # Update execution role ARN default if not set (treat None as empty)
            execution_role_prop = properties.get("execution_role_arn", {})
            current_default = execution_role_prop.get("default")
            if (
                current_default is None or not current_default
            ) and "TaskExecutionRoleArn" in stack_outputs:
                execution_role_prop["default"] = stack_outputs["TaskExecutionRoleArn"]
                properties["execution_role_arn"] = execution_role_prop

            # Update network configuration subnets default if not set
            network_config_prop = properties.get("network_configuration", {})
            network_config_props = network_config_prop.get("properties", {})
            awsvpc_config_prop = network_config_props.get("awsvpcConfiguration", {})
            awsvpc_config_props = awsvpc_config_prop.get("properties", {})
            subnets_prop = awsvpc_config_props.get("subnets", {})

            current_subnets_default = subnets_prop.get("default")
            if (
                current_subnets_default is None or not current_subnets_default
            ) and "SubnetIds" in stack_outputs:
                subnet_list = stack_outputs["SubnetIds"].split(",")
                subnets_prop["default"] = subnet_list
                awsvpc_config_props["subnets"] = subnets_prop
                awsvpc_config_prop["properties"] = awsvpc_config_props
                network_config_props["awsvpcConfiguration"] = awsvpc_config_prop
                network_config_prop["properties"] = network_config_props
                properties["network_configuration"] = network_config_prop

            variables["properties"] = properties

            # Update the work pool
            update_data = WorkPoolUpdate(base_job_template=base_template)
            client.update_work_pool(work_pool_name, update_data)

    except Exception:
        # Don't fail the deployment if work pool update fails
        pass

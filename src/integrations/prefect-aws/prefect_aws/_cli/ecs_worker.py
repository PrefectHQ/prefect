"""ECS worker deployment commands."""

import json
import pathlib
from typing import Optional

import click
import typer
from rich.table import Table
from typing_extensions import Annotated

from .utils import (
    add_cli_tags,
    console,
    delete_stack,
    deploy_stack,
    display_stacks_table,
    get_aws_client,
    get_stack_status,
    list_cli_deployed_stacks,
    load_template,
    update_work_pool_defaults,
    validate_aws_credentials,
    validate_ecs_cluster,
    validate_stack_is_cli_managed,
    validate_vpc_and_subnets,
)

ecs_worker_app = typer.Typer(
    name="ecs-worker",
    help="Deploy and manage ECS worker infrastructure",
    no_args_is_help=True,
)


@ecs_worker_app.command("deploy-service")
def deploy_service(
    work_pool_name: Annotated[
        str, typer.Option(help="Name of the Prefect work pool", prompt=True)
    ],
    stack_name: Annotated[
        str, typer.Option(help="CloudFormation stack name", prompt=True)
    ],
    # ECS Configuration
    existing_cluster_identifier: Annotated[
        str,
        typer.Option(
            help="ECS cluster name or ARN", prompt="ECS clust identifier (name or ARN)"
        ),
    ],
    existing_vpc_id: Annotated[str, typer.Option(help="VPC ID", prompt="VPC ID")],
    existing_subnet_ids: Annotated[
        str,
        typer.Option(
            help="Comma-separated subnet IDs", prompt="Subnet IDs (comma-separated)"
        ),
    ],
    # Prefect Configuration
    prefect_api_url: Annotated[
        str, typer.Option(help="Prefect API URL", prompt="Prefect API URL")
    ],
    prefect_api_key_secret_arn: Annotated[
        str, typer.Option(help="ARN of existing Prefect API key secret")
    ] = "",
    prefect_api_key: Annotated[
        str,
        typer.Option(
            help="Prefect API key (if not using existing secret)", hide_input=True
        ),
    ] = "",
    prefect_auth_string_secret_arn: Annotated[
        str,
        typer.Option(
            help="ARN of existing Prefect auth string secret for self-hosted servers"
        ),
    ] = "",
    prefect_auth_string: Annotated[
        str,
        typer.Option(
            help="Prefect auth string for self-hosted servers (if not using existing secret)",
            hide_input=True,
        ),
    ] = "",
    # Worker Configuration
    docker_image: Annotated[
        str, typer.Option(help="Docker image for worker")
    ] = "prefecthq/prefect-aws:latest",
    work_queues: Annotated[str, typer.Option(help="Comma-separated work queues")] = "",
    desired_count: Annotated[
        int, typer.Option(help="Desired number of worker tasks")
    ] = 1,
    min_capacity: Annotated[
        int, typer.Option(help="Minimum capacity for auto scaling")
    ] = 1,
    max_capacity: Annotated[
        int, typer.Option(help="Maximum capacity for auto scaling")
    ] = 10,
    # Task Configuration
    task_cpu: Annotated[int, typer.Option(help="CPU units (1024 = 1 vCPU)")] = 1024,
    task_memory: Annotated[int, typer.Option(help="Memory in MB")] = 2048,
    # Logging Configuration
    log_retention_days: Annotated[
        int, typer.Option(help="CloudWatch log retention days")
    ] = 30,
    existing_log_group_name: Annotated[
        str, typer.Option(help="Existing log group name")
    ] = "",
    # AWS Configuration
    region: Annotated[Optional[str], typer.Option(help="AWS region")] = None,
    profile: Annotated[Optional[str], typer.Option(help="AWS profile")] = None,
    # Other options
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be deployed without deploying"),
    ] = False,
    wait: Annotated[
        bool,
        typer.Option("--wait/--no-wait", help="Wait for stack deployment to complete"),
    ] = True,
):
    """Deploy an ECS service stack with worker and event infrastructure."""

    # Validate AWS credentials
    if not validate_aws_credentials(region, profile):
        typer.echo("Error: Invalid AWS credentials", err=True)
        raise typer.Exit(1)

    # Check if this is Prefect Cloud (requires API key)
    is_prefect_cloud = "api.prefect.cloud" in prefect_api_url.lower()

    if is_prefect_cloud:
        # Prefect Cloud requires API key
        if not prefect_api_key_secret_arn and not prefect_api_key:
            prefect_api_key = typer.prompt(
                "Prefect API key (required for Prefect Cloud)", hide_input=True
            )
    else:
        # Self-hosted Prefect server - auth is optional
        if not prefect_auth_string_secret_arn and not prefect_auth_string:
            auth_needed = typer.confirm(
                "Does your Prefect server require authentication?", default=False
            )
            if auth_needed:
                prefect_auth_string = typer.prompt(
                    "Prefect auth string (username:password format)", hide_input=True
                )

    # Parse subnet IDs
    subnet_id_list = [s.strip() for s in existing_subnet_ids.split(",")]

    # Get AWS clients
    cf_client = get_aws_client("cloudformation", region, profile)
    ecs_client = get_aws_client("ecs", region, profile)
    ec2_client = get_aws_client("ec2", region, profile)

    # Validate AWS resources
    console.print("[cyan]Validating AWS resources...")

    if not validate_ecs_cluster(ecs_client, existing_cluster_identifier):
        typer.echo(
            f"Error: ECS cluster '{existing_cluster_identifier}' not found or not active",
            err=True,
        )
        raise typer.Exit(1)

    valid_vpc, vpc_error = validate_vpc_and_subnets(
        ec2_client, existing_vpc_id, subnet_id_list
    )
    if not valid_vpc:
        typer.echo(f"Error: {vpc_error}", err=True)
        raise typer.Exit(1)

    # Load template
    template = load_template("service.json")

    # Prepare parameters
    parameters = [
        {"ParameterKey": "WorkPoolName", "ParameterValue": work_pool_name},
        {"ParameterKey": "PrefectApiUrl", "ParameterValue": prefect_api_url},
        {
            "ParameterKey": "PrefectApiKeySecretArn",
            "ParameterValue": prefect_api_key_secret_arn,
        },
        {"ParameterKey": "PrefectApiKey", "ParameterValue": prefect_api_key},
        {
            "ParameterKey": "PrefectAuthStringSecretArn",
            "ParameterValue": prefect_auth_string_secret_arn,
        },
        {"ParameterKey": "PrefectAuthString", "ParameterValue": prefect_auth_string},
        {
            "ParameterKey": "ExistingClusterIdentifier",
            "ParameterValue": existing_cluster_identifier,
        },
        {"ParameterKey": "ExistingVpcId", "ParameterValue": existing_vpc_id},
        {"ParameterKey": "ExistingSubnetIds", "ParameterValue": existing_subnet_ids},
        {"ParameterKey": "DockerImage", "ParameterValue": docker_image},
        {"ParameterKey": "WorkQueues", "ParameterValue": work_queues},
        {"ParameterKey": "DesiredCount", "ParameterValue": str(desired_count)},
        {"ParameterKey": "MinCapacity", "ParameterValue": str(min_capacity)},
        {"ParameterKey": "MaxCapacity", "ParameterValue": str(max_capacity)},
        {"ParameterKey": "TaskCpu", "ParameterValue": str(task_cpu)},
        {"ParameterKey": "TaskMemory", "ParameterValue": str(task_memory)},
        {"ParameterKey": "LogRetentionDays", "ParameterValue": str(log_retention_days)},
        {
            "ParameterKey": "ExistingLogGroupName",
            "ParameterValue": existing_log_group_name,
        },
    ]

    # Prepare tags
    tags = add_cli_tags(work_pool_name, "service")

    if dry_run:
        console.print("[yellow]DRY RUN - Would deploy the following:")
        console.print(f"Stack Name: {stack_name}")
        console.print(f"Work Pool: {work_pool_name}")
        console.print(f"Cluster: {existing_cluster_identifier}")
        console.print(f"VPC: {existing_vpc_id}")
        console.print(f"Subnets: {existing_subnet_ids}")
        console.print(f"Docker Image: {docker_image}")
        console.print(f"Desired Count: {desired_count}")
        return

    # Deploy stack
    deploy_stack(
        cf_client=cf_client,
        stack_name=stack_name,
        template_body=json.dumps(template),
        parameters=parameters,
        tags=tags,
        wait=wait,
    )

    # Update work pool defaults with deployed infrastructure values if deployment completed
    if wait:
        try:
            stack_info = get_stack_status(cf_client, stack_name)
            if stack_info and "Outputs" in stack_info:
                outputs = {
                    output["OutputKey"]: output["OutputValue"]
                    for output in stack_info["Outputs"]
                }
                update_work_pool_defaults(work_pool_name, outputs)
        except Exception:
            pass

    console.print(f"[green]Successfully deployed ECS service stack: {stack_name}")


@ecs_worker_app.command("deploy-events")
def deploy_events(
    work_pool_name: Annotated[
        str, typer.Option(help="Name of the Prefect work pool", prompt=True)
    ],
    stack_name: Annotated[
        str, typer.Option(help="CloudFormation stack name", prompt=True)
    ],
    existing_cluster_arn: Annotated[
        str, typer.Option(help="ECS cluster ARN", prompt="ECS cluster ARN")
    ],
    # AWS Configuration
    region: Annotated[Optional[str], typer.Option(help="AWS region")] = None,
    profile: Annotated[Optional[str], typer.Option(help="AWS profile")] = None,
    # Other options
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be deployed without deploying"),
    ] = False,
    wait: Annotated[
        bool,
        typer.Option("--wait/--no-wait", help="Wait for stack deployment to complete"),
    ] = True,
):
    """Deploy an events-only stack for monitoring existing ECS infrastructure."""

    # Validate AWS credentials
    if not validate_aws_credentials(region, profile):
        typer.echo("Error: Invalid AWS credentials", err=True)
        raise typer.Exit(1)

    # Get AWS clients
    cf_client = get_aws_client("cloudformation", region, profile)
    ecs_client = get_aws_client("ecs", region, profile)

    # Validate ECS cluster
    console.print("[cyan]Validating AWS resources...")
    if not validate_ecs_cluster(ecs_client, existing_cluster_arn):
        typer.echo(
            f"Error: ECS cluster '{existing_cluster_arn}' not found or not active",
            err=True,
        )
        raise typer.Exit(1)

    # Load template
    template = load_template("events-only.json")

    # Prepare parameters
    parameters = [
        {"ParameterKey": "WorkPoolName", "ParameterValue": work_pool_name},
        {"ParameterKey": "ExistingClusterArn", "ParameterValue": existing_cluster_arn},
    ]

    # Prepare tags
    tags = add_cli_tags(work_pool_name, "events")

    if dry_run:
        console.print("[yellow]DRY RUN - Would deploy the following:")
        console.print(f"Stack Name: {stack_name}")
        console.print(f"Work Pool: {work_pool_name}")
        console.print(f"Cluster ARN: {existing_cluster_arn}")
        return

    # Deploy stack
    deploy_stack(
        cf_client=cf_client,
        stack_name=stack_name,
        template_body=json.dumps(template),
        parameters=parameters,
        tags=tags,
        wait=wait,
    )

    console.print(f"[green]Successfully deployed ECS events stack: {stack_name}")


@ecs_worker_app.command("list")
def list_stacks(
    region: Annotated[Optional[str], typer.Option(help="AWS region")] = None,
    profile: Annotated[Optional[str], typer.Option(help="AWS profile")] = None,
    output_format: Annotated[
        str, typer.Option("--format", help="Output format: table, json")
    ] = "table",
):
    """List all stacks deployed by prefect-aws CLI."""

    # Validate AWS credentials
    if not validate_aws_credentials(region, profile):
        typer.echo("Error: Invalid AWS credentials", err=True)
        raise typer.Exit(1)

    cf_client = get_aws_client("cloudformation", region, profile)
    stacks = list_cli_deployed_stacks(cf_client)

    if output_format == "json":
        # Convert datetime objects to strings for JSON serialization
        import json
        from datetime import datetime

        def serialize_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        print(json.dumps(stacks, default=serialize_datetime, indent=2))
    else:
        display_stacks_table(stacks)


@ecs_worker_app.command("status")
def stack_status(
    stack_name: Annotated[str, typer.Argument(help="Name of the stack")],
    region: Annotated[Optional[str], typer.Option(help="AWS region")] = None,
    profile: Annotated[Optional[str], typer.Option(help="AWS profile")] = None,
):
    """Get the status of a specific stack."""

    # Validate AWS credentials
    if not validate_aws_credentials(region, profile):
        typer.echo("Error: Invalid AWS credentials", err=True)
        raise typer.Exit(1)

    cf_client = get_aws_client("cloudformation", region, profile)

    # Validate stack is CLI-managed
    if not validate_stack_is_cli_managed(cf_client, stack_name):
        typer.echo(
            f"Error: Stack '{stack_name}' was not deployed by prefect-aws CLI", err=True
        )
        raise typer.Exit(1)

    stack_info = get_stack_status(cf_client, stack_name)

    if not stack_info:
        typer.echo(f"Stack '{stack_name}' not found", err=True)
        raise typer.Exit(1)

    # Display stack information
    console.print(f"[bold cyan]Stack: {stack_info['StackName']}[/bold cyan]")
    console.print(f"Status: {stack_info['StackStatus']}")

    # Format creation time in a human-friendly way
    created_time = stack_info["CreationTime"]
    if hasattr(created_time, "strftime"):
        created_formatted = created_time.strftime("%B %d, %Y at %I:%M %p UTC")
    else:
        created_formatted = str(created_time)
    console.print(f"Created: {created_formatted}", highlight=False)

    # Format update time if available
    if "LastUpdatedTime" in stack_info:
        updated_time = stack_info["LastUpdatedTime"]
        if hasattr(updated_time, "strftime"):
            updated_formatted = updated_time.strftime("%B %d, %Y at %I:%M %p UTC")
        else:
            updated_formatted = str(updated_time)
        console.print(f"Updated: {updated_formatted}", highlight=False)

    # Show outputs if available
    if "Outputs" in stack_info:
        console.print("\n[bold]Stack Outputs:[/bold]")

        outputs_table = Table(show_header=True, header_style="bold magenta")
        outputs_table.add_column("Output Key", style="cyan", overflow="ellipsis")
        outputs_table.add_column("Value", style="green", overflow="fold")
        outputs_table.add_column("Description", style="yellow", overflow="fold")

        for output in stack_info["Outputs"]:
            description = output.get("Description", "")
            outputs_table.add_row(
                output["OutputKey"], output["OutputValue"], description
            )

        console.print(outputs_table)


@ecs_worker_app.command("delete")
def delete_stack_cmd(
    stack_name: Annotated[str, typer.Argument(help="Name of the stack to delete")],
    region: Annotated[Optional[str], typer.Option(help="AWS region")] = None,
    profile: Annotated[Optional[str], typer.Option(help="AWS profile")] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Skip confirmation prompt")
    ] = False,
    wait: Annotated[
        bool,
        typer.Option("--wait/--no-wait", help="Wait for stack deletion to complete"),
    ] = True,
):
    """Delete a stack deployed by prefect-aws CLI."""

    # Validate AWS credentials
    if not validate_aws_credentials(region, profile):
        typer.echo("Error: Invalid AWS credentials", err=True)
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(
            f"Are you sure you want to delete stack '{stack_name}'?"
        )
        if not confirm:
            typer.echo("Deletion cancelled")
            return

    cf_client = get_aws_client("cloudformation", region, profile)
    delete_stack(cf_client, stack_name, wait=wait)


@ecs_worker_app.command("export-template")
def export_template(
    template_type: Annotated[
        str,
        typer.Option(
            help="Template type: 'service' or 'events-only'",
            click_type=click.Choice(["service", "events-only"]),
            prompt=True,
        ),
    ],
    output_path: Annotated[
        pathlib.Path,
        typer.Option(help="Output file path for the template", prompt=True),
    ],
    format: Annotated[
        str,
        typer.Option(
            help="Output format: 'json' or 'yaml'",
            click_type=click.Choice(["json", "yaml"]),
        ),
    ] = "json",
):
    """Export CloudFormation templates to files for direct use or customization."""
    try:
        # Load the template
        console.print(f"[cyan]Loading template '{template_type}'...")
        template = load_template(f"{template_type}.json")

        content = ""
        # Prepare content based on format
        if format == "json":
            content = json.dumps(template, indent=2)
        elif format == "yaml":
            try:
                import yaml

                content = yaml.dump(template, default_flow_style=False, sort_keys=False)
            except ImportError:
                console.print(
                    "[yellow]Warning: PyYAML not available, falling back to JSON format"
                )
                content = json.dumps(template, indent=2)
                output_path = (
                    pathlib.Path(str(output_path).rsplit(".", 1)[0] + ".json")
                    if "." in str(output_path)
                    else pathlib.Path(str(output_path) + ".json")
                )

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(content)

        console.print(f"[green]✓ Template exported to: {output_path}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("1. Review and customize the template as needed")
        console.print("2. Deploy using AWS CLI:")
        console.print(
            f"   [cyan]aws cloudformation deploy --template-file {output_path} --stack-name YOUR_STACK_NAME --parameter-overrides ParameterKey=Value[/cyan]"
        )
        console.print("3. Or use the template with other infrastructure tools")

    except Exception as e:
        typer.echo(f"Error exporting template: {e}", err=True)
        raise typer.Exit(1)

"""
Command line interface for SDK generation.
"""

from __future__ import annotations

from pathlib import Path

import typer

from prefect._sdk.generator import (
    APIConnectionError,
    AuthenticationError,
    GenerationResult,
    NoDeploymentsError,
    SDKGeneratorError,
    generate_sdk,
)
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client.orchestration import get_client

sdk_app: PrefectTyper = PrefectTyper(name="sdk", help="Manage Prefect SDKs. (beta)")

app.add_typer(sdk_app)


def _is_valid_identifier(name: str) -> bool:
    """Check if a string is a valid Python identifier."""
    return name.isidentifier()


@sdk_app.command("generate")
async def generate(
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output file path for the generated SDK.",
    ),
    flow: list[str] | None = typer.Option(
        None,
        "--flow",
        "-f",
        help="Filter to specific flow(s). Can be specified multiple times.",
    ),
    deployment: list[str] | None = typer.Option(
        None,
        "--deployment",
        "-d",
        help=(
            "Filter to specific deployment(s). Can be specified multiple times. "
            "Use 'flow-name/deployment-name' format for exact matching."
        ),
    ),
) -> None:
    """
    (beta) Generate a typed Python SDK from workspace deployments.

    The generated SDK provides IDE autocomplete and type checking for your deployments.
    Requires an active Prefect API connection (use `prefect cloud login` or configure
    PREFECT_API_URL).

    \b
    Examples:
        Generate SDK for all deployments:
            $ prefect sdk generate --output ./my_sdk.py

        Generate SDK for specific flows:
            $ prefect sdk generate --output ./my_sdk.py --flow my-etl-flow

        Generate SDK for specific deployments:
            $ prefect sdk generate --output ./my_sdk.py --deployment my-flow/production
    """
    app.console.print(
        "[yellow]Note:[/yellow] This command is in beta. "
        "APIs may change in future releases."
    )
    app.console.print()

    # Pre-validate output path
    if output.exists() and output.is_dir():
        exit_with_error(
            f"Output path '{output}' is a directory. Please provide a file path."
        )

    app.console.print("Fetching deployments...")

    try:
        async with get_client() as client:
            result: GenerationResult = await generate_sdk(
                client=client,
                output_path=output,
                flow_names=flow,
                deployment_names=deployment,
            )
    except AuthenticationError as e:
        exit_with_error(
            f"Not authenticated. Run `prefect cloud login` or configure PREFECT_API_URL.\n"
            f"Details: {e}"
        )
    except APIConnectionError as e:
        exit_with_error(f"Could not connect to Prefect API.\nDetails: {e}")
    except NoDeploymentsError as e:
        exit_with_error(
            f"No deployments found.\n\n"
            f"Details: {e}\n\n"
            f"Make sure you have deployed at least one flow:\n"
            f"  prefect deploy"
        )
    except SDKGeneratorError as e:
        exit_with_error(f"SDK generation failed.\nDetails: {e}")

    # Display warnings
    for warning in result.warnings:
        app.console.print(f"[yellow]Warning:[/yellow] {warning}")

    # Display errors (non-fatal)
    for error in result.errors:
        app.console.print(f"[red]Error:[/red] {error}")

    # Display success message with statistics
    app.console.print()
    app.console.print("[green]SDK generated successfully![/green]")
    app.console.print()
    app.console.print(f"  Flows:       {result.flow_count}")
    app.console.print(f"  Deployments: {result.deployment_count}")
    app.console.print(f"  Work pools:  {result.work_pool_count}")
    app.console.print()
    app.console.print(f"  Output:      {result.output_path.absolute()}")
    app.console.print()

    # Display usage hint
    module_name = result.output_path.stem
    app.console.print("Usage:")
    if _is_valid_identifier(module_name):
        app.console.print(f"  from {module_name} import deployments")
    else:
        # For invalid identifiers (e.g., my-sdk), suggest renaming
        suggested_name = module_name.replace("-", "_")
        app.console.print(
            f"  # Note: '{module_name}' is not a valid Python module name."
        )
        app.console.print(
            f"  # Rename the file to '{suggested_name}.py' to enable imports:"
        )
        app.console.print(f"  #   from {suggested_name} import deployments")

    exit_with_success("")

"""
SDK command — native cyclopts implementation.

Generate typed Python SDK from workspace deployments.
"""

from pathlib import Path
from typing import Annotated, Optional

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)
from prefect.client.orchestration import get_client

sdk_app: cyclopts.App = cyclopts.App(
    name="sdk",
    help="Manage Prefect SDKs. (beta)",
    version_flags=[],
    help_flags=["--help"],
)


def _is_valid_identifier(name: str) -> bool:
    """Check if a string is a valid Python identifier."""
    return name.isidentifier()


@sdk_app.command(name="generate")
@with_cli_exception_handling
async def generate(
    *,
    output: Annotated[
        Path,
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Output file path for the generated SDK.",
        ),
    ],
    flow: Annotated[
        Optional[list[str]],
        cyclopts.Parameter(
            "--flow",
            alias="-f",
            help="Filter to specific flow(s). Can be specified multiple times.",
        ),
    ] = None,
    deployment: Annotated[
        Optional[list[str]],
        cyclopts.Parameter(
            "--deployment",
            alias="-d",
            help=(
                "Filter to specific deployment(s). Can be specified multiple times. "
                "Use 'flow-name/deployment-name' format for exact matching."
            ),
        ),
    ] = None,
) -> None:
    """(beta) Generate a typed Python SDK from workspace deployments."""
    from prefect._sdk.generator import (
        APIConnectionError,
        AuthenticationError,
        GenerationResult,
        NoDeploymentsError,
        SDKGeneratorError,
        generate_sdk,
    )

    _cli.console.print(
        "[yellow]Note:[/yellow] This command is in beta. "
        "APIs may change in future releases."
    )
    _cli.console.print()

    # Pre-validate output path
    if output.exists() and output.is_dir():
        exit_with_error(
            f"Output path '{output}' is a directory. Please provide a file path."
        )

    _cli.console.print("Fetching deployments...")

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
        _cli.console.print(f"[yellow]Warning:[/yellow] {warning}")

    # Display errors (non-fatal)
    for error in result.errors:
        _cli.console.print(f"[red]Error:[/red] {error}")

    # Display success message with statistics
    _cli.console.print()
    _cli.console.print("[green]SDK generated successfully![/green]")
    _cli.console.print()
    _cli.console.print(f"  Flows:       {result.flow_count}")
    _cli.console.print(f"  Deployments: {result.deployment_count}")
    _cli.console.print(f"  Work pools:  {result.work_pool_count}")
    _cli.console.print()
    _cli.console.print(f"  Output:      {result.output_path.absolute()}")
    _cli.console.print()

    # Display usage hint
    module_name = result.output_path.stem
    _cli.console.print("Usage:")
    if _is_valid_identifier(module_name):
        _cli.console.print(f"  from {module_name} import deployments")
    else:
        suggested_name = module_name.replace("-", "_")
        _cli.console.print(
            f"  # Note: '{module_name}' is not a valid Python module name."
        )
        _cli.console.print(
            f"  # Rename the file to '{suggested_name}.py' to enable imports:"
        )
        _cli.console.print(f"  #   from {suggested_name} import deployments")

    exit_with_success("")

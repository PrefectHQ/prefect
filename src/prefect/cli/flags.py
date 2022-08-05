"""
Feature flag CLI commands
"""


import typer
from rich.table import Table

from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.feature_flags import get_feature_flag_client, list_feature_flags

flags_app = typer.Typer(name="flags", help="Commands for working with feature flags.")
app.add_typer(flags_app)

flags_client = get_feature_flag_client()


def feature_flag_table(header: str, rows: list[list[str]]):
    table = Table(title=header, caption_style="red")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Enabled?", style="green", no_wrap=True)
    for row in rows:
        table.add_row(*row)
    return table


@flags_app.command(short_help="List feature flags", name="ls")
@sync_compatible
async def list_features():
    """List feature flags."""
    rows = [[f.name, str(f.is_enabled())] for f in list_feature_flags()]
    table = feature_flag_table("Feature Flags:", rows)
    app.console.print(table)


@flags_app.command(short_help="Enable a feature flag", name="enable")
@sync_compatible
async def enable_feature(name: str):
    """Enable a feature flag."""
    flag = flags_client.get(name)
    if not flag.exists():
        exit_with_error(f"The feature {name} does not exist")
    flag.enable()
    table = feature_flag_table(
        "Enabled feature flag:", [[flag.name, str(flag.is_enabled())]]
    )
    exit_with_success(table)


@flags_app.command(short_help="Disable a feature flag", name="disable")
@sync_compatible
async def disable_feature(name: str):
    """Disable a feature flag."""
    flag = flags_client.get(name)
    if not flag.exists():
        exit_with_error(f"The feature {name} does not exist")
    flag.disable()
    table = feature_flag_table(
        "Disabled feature flag:", [[flag.name, str(flag.is_enabled())]]
    )
    exit_with_success(table)

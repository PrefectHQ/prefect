"""
Feature flag CLI commands
"""
from typing import List

import typer
from rich.table import Table

from prefect.cli.root import app
from prefect.settings import PREFECT_FEATURE_FLAGGING_ENABLED
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.feature_flags import get_feature_flag_client, list_feature_flags

flags_app = typer.Typer(name="flags", help="Commands for working with feature flags.")
app.add_typer(flags_app)

flags_client = get_feature_flag_client()


def feature_flag_table(header: str, rows: List[List[str]]):
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
    if not PREFECT_FEATURE_FLAGGING_ENABLED.value():
        app.console.print(
            "Feature flagging is disabled because the "
            "PREFECT_FEATURE_FLAGGING_ENABLED setting is false."
        )
        return
    rows = [[f.name, str(f.is_enabled())] for f in list_feature_flags()]
    table = feature_flag_table("Feature Flags:", rows)
    app.console.print(table)

"""
Command line interface for managing Prefect Cloud assets
"""

from __future__ import annotations

from typing import Optional

import orjson
import typer
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.cloud import cloud_app, confirm_logged_in
from prefect.cli.root import app
from prefect.client.cloud import get_cloud_client
from prefect.exceptions import ObjectNotFound
from prefect.settings import get_current_settings

asset_app: PrefectTyper = PrefectTyper(name="asset", help="Manage Prefect Cloud assets")
cloud_app.add_typer(asset_app, aliases=["assets"])


@asset_app.command("ls")
async def list_assets(
    prefix: Optional[str] = typer.Option(
        None,
        "--prefix",
        "-p",
        help="Filter assets by key prefix",
    ),
    search: Optional[str] = typer.Option(
        None,
        "--search",
        "-s",
        help="Filter assets by key substring",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output format. Supports: json",
    ),
):
    """
    List assets in the current workspace.
    """
    confirm_logged_in()

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    params: dict[str, str] = {}
    if prefix:
        params["prefix"] = prefix
    if search:
        params["search"] = search

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        assets = await client.request("GET", "/assets/", params=params or None)

    if output and output.lower() == "json":
        json_output = orjson.dumps(assets, option=orjson.OPT_INDENT_2).decode()
        app.console.print(json_output)
    else:
        if not assets:
            app.console.print("No assets found in this workspace.")
            return

        table = Table(
            title="Assets",
            show_header=True,
        )

        table.add_column("Key", style="blue", no_wrap=False)
        table.add_column("Last Seen", style="cyan", no_wrap=True)

        for asset in sorted(assets, key=lambda x: x.get("key", "")):
            table.add_row(
                asset.get("key", ""),
                asset.get("last_seen", ""),
            )

        app.console.print(table)
        app.console.print(f"\nShowing {len(assets)} asset(s)")


@asset_app.command("delete")
async def delete_asset(
    key: str = typer.Argument(..., help="The key of the asset to delete"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """
    Delete an asset by its key.

    The key should be the full asset URI (e.g., 's3://bucket/data.csv').
    """
    confirm_logged_in()

    if not force:
        if not typer.confirm(
            f"Are you sure you want to delete asset {key!r}?",
            default=False,
        ):
            exit_with_error("Deletion aborted.")

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        try:
            await client.request("DELETE", "/assets/key", params={"key": key})
        except ObjectNotFound:
            exit_with_error(f"Asset {key!r} not found.")

    exit_with_success(f"Deleted asset {key!r}.")

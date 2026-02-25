"""Manage Prefect Cloud assets."""

from __future__ import annotations

from typing import Annotated

import cyclopts
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._cloud_utils import confirm_logged_in
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

asset_app: cyclopts.App = cyclopts.App(
    name="asset",
    alias="assets",
    help="Manage Prefect Cloud assets.",
    version_flags=[],
    help_flags=["--help"],
)


@asset_app.command(name="ls")
@with_cli_exception_handling
async def asset_ls(
    *,
    prefix: Annotated[
        str | None,
        cyclopts.Parameter("--prefix", alias="-p", help="Filter assets by key prefix"),
    ] = None,
    search: Annotated[
        str | None,
        cyclopts.Parameter(
            "--search", alias="-s", help="Filter assets by key substring"
        ),
    ] = None,
    limit: Annotated[
        int,
        cyclopts.Parameter(
            "--limit",
            alias="-l",
            help="Maximum number of assets to return (default 50, max 200)",
        ),
    ] = 50,
    output: Annotated[
        str | None,
        cyclopts.Parameter(
            "--output", alias="-o", help="Output format. Supports: json"
        ),
    ] = None,
):
    """List assets in the current workspace."""
    import orjson

    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    if limit < 1 or limit > 200:
        exit_with_error("Limit must be between 1 and 200.")

    key_filter: dict[str, list[str]] = {}
    if prefix:
        key_filter["prefix"] = [prefix]
    if search:
        key_filter["search"] = [search]

    body: dict[str, object] = {"limit": limit}
    if key_filter:
        body["filter"] = {"key": key_filter}

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request("POST", "/assets/filter", json=body)

    assets = response.get("assets", [])
    total = response.get("total", len(assets))

    if output and output.lower() == "json":
        json_output = orjson.dumps(assets, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
        if not assets:
            _cli.console.print("No assets found in this workspace.")
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

        _cli.console.print(table)
        _cli.console.print(f"\nShowing {len(assets)} of {total} asset(s)")


@asset_app.command(name="delete")
@with_cli_exception_handling
async def asset_delete(
    key: Annotated[str, cyclopts.Parameter(help="The key of the asset to delete")],
    *,
    force: Annotated[
        bool,
        cyclopts.Parameter(
            "--force", alias="-f", negative="", help="Skip confirmation prompt"
        ),
    ] = False,
):
    """Delete an asset by its key.

    The key should be the full asset URI (e.g., 's3://bucket/data.csv').
    """
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client
    from prefect.exceptions import ObjectNotFound
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    if _cli.is_interactive() and not force:
        if not confirm(
            f"Are you sure you want to delete asset {key!r}?",
            default=False,
            console=_cli.console,
        ):
            exit_with_error("Deletion aborted.")

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        try:
            await client.request("DELETE", "/assets/key", params={"key": key})
        except ObjectNotFound:
            exit_with_error(f"Asset {key!r} not found.")

    exit_with_success(f"Deleted asset {key!r}.")

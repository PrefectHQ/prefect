"""
Command line interface for working with assets
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import typer
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.cloud import cloud_app, confirm_logged_in
from prefect.cli.root import app, is_interactive
from prefect.client.cloud import get_cloud_client
from prefect.settings import get_current_settings
from prefect.types._datetime import human_friendly_diff

asset_app: PrefectTyper = PrefectTyper(name="asset", help="Manage Prefect Cloud Assets")
cloud_app.add_typer(asset_app, aliases=["assets"])


def _render_assets_into_table(assets: list[dict[str, Any]]) -> Table:
    display_table = Table(show_lines=True)
    display_table.add_column("Key", overflow="fold")
    display_table.add_column("Name", overflow="fold")
    display_table.add_column("Description", overflow="fold")

    for asset in assets:
        display_table.add_row(
            asset.get("key", ""),
            asset.get("name", ""),
            asset.get("description") or "",
        )
    return display_table


async def _list_assets(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """List assets in the workspace."""
    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request(
            "GET", "/assets/", params={"limit": limit, "offset": offset}
        )
        if isinstance(response, list):
            return response
        return response.get("results", [])


async def _get_asset(asset_key: str) -> dict[str, Any]:
    """Get a specific asset by key."""
    async with get_cloud_client(host=get_current_settings().api.url) as client:
        encoded_key = quote(asset_key, safe="")
        return await client.request("GET", f"/assets/key/{encoded_key}")


async def _delete_asset(asset_key: str) -> None:
    """Delete an asset by key."""
    async with get_cloud_client(host=get_current_settings().api.url) as client:
        encoded_key = quote(asset_key, safe="")
        await client.request("DELETE", f"/assets/key/{encoded_key}")


async def _get_latest_dependencies() -> list[dict[str, Any]]:
    """Get latest asset dependencies."""
    async with get_cloud_client(host=get_current_settings().api.url) as client:
        return await client.request("GET", "/assets/latest-dependencies")


@asset_app.command("ls")
async def list_assets(
    limit: int = typer.Option(
        100,
        "--limit",
        "-l",
        help="Maximum number of assets to list.",
    ),
):
    """
    List assets in your workspace.
    """
    confirm_logged_in()

    all_assets: list[dict[str, Any]] = []
    offset = 0

    while True:
        assets = await _list_assets(limit=limit, offset=offset)
        if not assets:
            break
        all_assets.extend(assets)
        if len(assets) < limit:
            break
        offset += limit

    if not all_assets:
        app.console.print("No assets found in workspace.")
        return

    display_table = _render_assets_into_table(all_assets)
    app.console.print(display_table)
    app.console.print(f"\nFound {len(all_assets)} asset(s).")


@asset_app.command("inspect")
async def inspect(
    key: str = typer.Argument(..., help="The key of the asset to inspect."),
):
    """
    Inspect an asset by key.
    """
    confirm_logged_in()

    try:
        asset = await _get_asset(key)
    except Exception as exc:
        exit_with_error(f"Error retrieving asset: {exc}")

    display_table = _render_assets_into_table([asset])
    app.console.print(display_table)


@asset_app.command("delete")
async def delete(
    key: str = typer.Argument(..., help="The key of the asset to delete."),
):
    """
    Delete an asset by key.
    """
    confirm_logged_in()

    if is_interactive() and not typer.confirm(
        f"Are you sure you want to delete asset with key '{key}'?",
        default=False,
    ):
        exit_with_error("Deletion aborted.")

    try:
        await _delete_asset(key)
    except Exception as exc:
        exit_with_error(f"Error deleting asset: {exc}")

    app.console.print(f"Successfully deleted asset '{key}'.")


@asset_app.command("delete-old")
async def delete_old(
    days: int = typer.Option(
        ...,
        "--days",
        "-d",
        help="Delete assets older than this many days.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deleted without actually deleting.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt.",
    ),
):
    """
    Delete assets older than a specified number of days.

    This command determines asset age based on the last materialization event.
    Assets without any materialization events are considered old and will be deleted.
    """
    confirm_logged_in()

    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)

    if dry_run:
        app.console.print(
            f"[bold]DRY RUN:[/bold] Would delete assets older than "
            f"{human_friendly_diff(cutoff_time)}"
        )
    else:
        app.console.print(
            f"Deleting assets older than {human_friendly_diff(cutoff_time)}"
        )

    app.console.print("Fetching all assets...")
    all_assets: list[dict[str, Any]] = []
    offset = 0
    limit = 100

    while True:
        assets = await _list_assets(limit=limit, offset=offset)
        if not assets:
            break
        all_assets.extend(assets)
        if len(assets) < limit:
            break
        offset += limit

    app.console.print(f"Found {len(all_assets)} total asset(s).")

    if not all_assets:
        app.console.print("No assets to delete.")
        return

    app.console.print("Fetching asset dependencies to determine last update times...")
    dependencies = await _get_latest_dependencies()

    asset_last_updated: dict[str, datetime] = {}
    for dep in dependencies:
        for key in [dep.get("upstream"), dep.get("downstream")]:
            if key:
                occurred = dep.get("occurred")
                if occurred:
                    occurred_time = datetime.fromisoformat(
                        occurred.replace("Z", "+00:00")
                    )
                    if (
                        key not in asset_last_updated
                        or occurred_time > asset_last_updated[key]
                    ):
                        asset_last_updated[key] = occurred_time

    assets_to_delete: list[dict[str, Any]] = []
    for asset in all_assets:
        asset_key = asset["key"]
        last_updated = asset_last_updated.get(asset_key)

        if last_updated:
            if last_updated < cutoff_time:
                assets_to_delete.append(
                    {"key": asset_key, "last_updated": last_updated}
                )
        else:
            assets_to_delete.append({"key": asset_key, "last_updated": None})

    app.console.print(f"\nFound {len(assets_to_delete)} asset(s) to delete.")

    if not assets_to_delete:
        app.console.print("No assets to delete.")
        return

    assets_to_delete.sort(
        key=lambda x: x["last_updated"] or datetime.min.replace(tzinfo=timezone.utc)
    )

    app.console.print("\nAssets to delete:")
    for asset in assets_to_delete[:10]:
        if asset["last_updated"]:
            app.console.print(
                f"  - {asset['key']} (last updated: "
                f"{human_friendly_diff(asset['last_updated'])})"
            )
        else:
            app.console.print(f"  - {asset['key']} (no materialization events found)")

    if len(assets_to_delete) > 10:
        app.console.print(f"  ... and {len(assets_to_delete) - 10} more")

    if dry_run:
        app.console.print("\n[bold]DRY RUN:[/bold] No assets were deleted.")
        return

    if not force:
        if is_interactive():
            app.console.print(
                f"\n[bold yellow]WARNING:[/bold yellow] This will delete "
                f"{len(assets_to_delete)} asset(s)!"
            )
            if not typer.confirm("Type 'y' to confirm deletion", default=False):
                exit_with_error("Deletion aborted.")
        else:
            exit_with_error(
                "Confirmation required. Use --force to skip confirmation in "
                "non-interactive mode."
            )

    deleted_count = 0
    failed_count = 0

    app.console.print("\nDeleting assets...")
    for asset in assets_to_delete:
        try:
            await _delete_asset(asset["key"])
            deleted_count += 1
            if deleted_count % 10 == 0:
                app.console.print(
                    f"  Deleted {deleted_count}/{len(assets_to_delete)} asset(s)..."
                )
        except Exception as e:
            app.console.print(f"  [red]Failed to delete {asset['key']}: {e}[/red]")
            failed_count += 1

    app.console.print(
        f"\n[green]Successfully deleted {deleted_count} asset(s).[/green]"
    )
    if failed_count > 0:
        app.console.print(f"[red]Failed to delete {failed_count} asset(s).[/red]")

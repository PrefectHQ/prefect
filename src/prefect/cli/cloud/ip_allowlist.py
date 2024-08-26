import asyncio
import ipaddress
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.cloud import cloud_app, confirm_logged_in
from prefect.cli.root import app
from prefect.client.cloud import get_cloud_client
from prefect.client.schemas.objects import IPAllowlist, IPAllowlistEntry

ip_allowlist_app = PrefectTyper(
    name="ip-allowlist", help="Manage Prefect Cloud IP Allowlists"
)
cloud_app.add_typer(ip_allowlist_app, aliases=["ip-allowlists"])


@ip_allowlist_app.callback()
def require_access_to_ip_allowlisting(ctx: typer.Context):
    """Enforce access to IP allowlisting for all subcommands."""
    asyncio.run(_require_access_to_ip_allowlisting(ctx))


async def _require_access_to_ip_allowlisting(ctx: typer.Context):
    """Check if the account has access to IP allowlisting.

    Exits with an error if the account does not have access to IP allowlisting.

    On success, sets Typer context meta["enforce_ip_allowlist"] to
    True if the account has IP allowlist enforcement enabled, False otherwise.
    """
    confirm_logged_in()

    async with get_cloud_client(infer_cloud_url=True) as client:
        account_settings = await client.read_account_settings()

    if "enforce_ip_allowlist" not in account_settings:
        return exit_with_error("IP allowlisting is not available for this account.")

    enforce_ip_allowlist = account_settings.get("enforce_ip_allowlist", False)
    ctx.meta["enforce_ip_allowlist"] = enforce_ip_allowlist


@ip_allowlist_app.command()
async def enable(ctx: typer.Context):
    """Enable the IP allowlist for your account. When enabled, if the allowlist is non-empty, then access to your Prefect Cloud account will be restricted to only those IP addresses on the allowlist."""
    enforcing_ip_allowlist = ctx.meta["enforce_ip_allowlist"]
    if enforcing_ip_allowlist:
        exit_with_success("IP allowlist is already enabled.")

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()
        if ip_allowlist.entries and not typer.confirm(
            "Enabling the IP allowlist will restrict Prefect Cloud API and UI access to only the IP addresses on the list. "
            "Continue?"
        ):
            exit_with_error("Aborted.")
        await client.update_account_settings({"enforce_ip_allowlist": True})

    exit_with_success("IP allowlist enabled.")


@ip_allowlist_app.command()
async def disable():
    """Disable the IP allowlist for your account. When disabled, all IP addresses will be allowed to access your Prefect Cloud account."""
    async with get_cloud_client(infer_cloud_url=True) as client:
        await client.update_account_settings({"enforce_ip_allowlist": False})

    exit_with_success("IP allowlist disabled.")


@ip_allowlist_app.command()
async def ls(ctx: typer.Context):
    """Fetch and list all IP allowlist entries in your account."""
    enforcing_ip_allowlist = ctx.meta["enforce_ip_allowlist"]

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        _print_ip_allowlist_table(ip_allowlist, enabled=enforcing_ip_allowlist)


@ip_allowlist_app.command()
async def add(
    ctx: typer.Context,
    ip_network: str,
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="A short description to annotate the entry with.",
    ),
):
    """Add a new IP entry to your account IP allowlist."""
    enforcing_ip_allowlist = ctx.meta["enforce_ip_allowlist"]

    new_entry = IPAllowlistEntry(
        ip_network=ip_network, description=description, enabled=True
    )

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        existing_entry_with_same_ip = None
        for entry in ip_allowlist.entries:
            if ipaddress.ip_network(entry.ip_network) == ipaddress.ip_network(
                ip_network
            ):
                existing_entry_with_same_ip = entry
                break

        if existing_entry_with_same_ip:
            if not typer.confirm(
                f"There's already an entry for this IP ({ip_network}). Do you want to overwrite it?"
            ):
                exit_with_error("Aborted.")
            ip_allowlist.entries.remove(existing_entry_with_same_ip)

        ip_allowlist.entries.append(new_entry)
        await client.update_account_ip_allowlist(ip_allowlist)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(updated_ip_allowlist, enabled=enforcing_ip_allowlist)


@ip_allowlist_app.command()
async def remove(ctx: typer.Context, ip_network: str):
    """Remove an IP entry from your account IP allowlist."""
    enforcing_ip_allowlist = ctx.meta["enforce_ip_allowlist"]

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()
        ip_allowlist.entries = [
            entry
            for entry in ip_allowlist.entries
            if ipaddress.ip_network(entry.ip_network)
            != ipaddress.ip_network(ip_network)
        ]
        await client.update_account_ip_allowlist(ip_allowlist)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(updated_ip_allowlist, enabled=enforcing_ip_allowlist)


def _print_ip_allowlist_table(
    ip_allowlist: IPAllowlist, enabled: Optional[bool] = None
):
    if not ip_allowlist.entries:
        app.console.print(
            Panel(
                "IP allowlist is empty. Add an entry to secure access to your Prefect Cloud account.",
                expand=False,
            )
        )
        return

    table = Table(
        title="IP Allowlist",
        caption=None
        if enabled is None
        else f"Enforcement of this list is currently {'ON' if enabled else 'OFF'}.",
    )

    table.add_column("IP Address", style="cyan", no_wrap=True)
    table.add_column("Description", style="blue", no_wrap=False)
    table.add_column("Enabled", style="green", justify="right", no_wrap=True)
    table.add_column("Last Seen", style="magenta", justify="right", no_wrap=True)

    for entry in ip_allowlist.entries:
        table.add_row(
            entry.ip_network,
            entry.description,
            str(entry.enabled),
            entry.last_seen or "Never",
            style="dim" if not entry.enabled else None,
        )

    app.console.print(table)


@ip_allowlist_app.command()
async def toggle(ctx: typer.Context, ip_network: str):
    """Toggle the enabled status of an individual IP entry in your account IP allowlist."""
    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        found_matching_entry = False
        for entry in ip_allowlist.entries:
            if ipaddress.ip_network(entry.ip_network) == ipaddress.ip_network(
                ip_network
            ):
                entry.enabled = not entry.enabled
                found_matching_entry = True
                break

        if not found_matching_entry:
            exit_with_error(f"No entry found with IP address `{ip_network}`.")

        await client.update_account_ip_allowlist(ip_allowlist)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(
            updated_ip_allowlist, enabled=ctx.meta["enforce_ip_allowlist"]
        )

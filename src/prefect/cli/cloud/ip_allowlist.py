import ipaddress
from typing import Optional

import typer
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


@ip_allowlist_app.command()
async def enable():
    """Enable the IP allowlist for your account."""
    confirm_logged_in()

    async with get_cloud_client(infer_cloud_url=True) as client:
        await client.update_account_settings({"enforce_ip_allowlist": True})

    # updated_ip_allowlist = await client.read_account_ip_allowlist()
    # _print_ip_allowlist_table(updated_ip_allowlist)
    exit_with_success("IP allowlist enabled.")


@ip_allowlist_app.command()
async def disable():
    """Disable the IP allowlist for your account."""
    confirm_logged_in()

    async with get_cloud_client(infer_cloud_url=True) as client:
        await client.update_account_settings({"enforce_ip_allowlist": False})

    # updated_ip_allowlist = await client.read_account_ip_allowlist()
    # _print_ip_allowlist_table(updated_ip_allowlist)
    exit_with_success("IP allowlist disabled.")


@ip_allowlist_app.command()
async def ls():
    """Fetch and list all IP allowlist entries in your account."""
    confirm_logged_in()

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        _print_ip_allowlist_table(ip_allowlist)


@ip_allowlist_app.command()
async def add(
    ip_network: str,
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="A short description to annotate the entry with.",
    ),
):
    """Add a new IP entry to your account IP allowlist."""
    confirm_logged_in()

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
        _print_ip_allowlist_table(updated_ip_allowlist)


@ip_allowlist_app.command()
async def remove(ip_network: str):
    """Remove an IP entry from your account IP allowlist."""
    confirm_logged_in()

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
        _print_ip_allowlist_table(updated_ip_allowlist)


def _print_ip_allowlist_table(ip_allowlist: IPAllowlist):
    table = Table(title="IP Allowlist")

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

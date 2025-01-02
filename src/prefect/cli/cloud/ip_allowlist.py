import asyncio
from logging import Logger
from typing import Annotated, Optional

import typer
from pydantic import BaseModel, IPvAnyNetwork
from rich.panel import Panel
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.cloud import cloud_app, confirm_logged_in
from prefect.cli.root import app
from prefect.client.cloud import get_cloud_client
from prefect.client.schemas.objects import IPAllowlist, IPAllowlistEntry
from prefect.exceptions import PrefectHTTPStatusError
from prefect.logging.loggers import get_logger

ip_allowlist_app: PrefectTyper = PrefectTyper(
    name="ip-allowlist", help="Manage Prefect Cloud IP Allowlists"
)
cloud_app.add_typer(ip_allowlist_app, aliases=["ip-allowlists"])

logger: Logger = get_logger(__name__)


@ip_allowlist_app.callback()
def require_access_to_ip_allowlisting(ctx: typer.Context) -> None:
    """Enforce access to IP allowlisting for all subcommands."""
    asyncio.run(_require_access_to_ip_allowlisting(ctx))


async def _require_access_to_ip_allowlisting(ctx: typer.Context) -> None:
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
async def enable(ctx: typer.Context) -> None:
    """Enable the IP allowlist for your account. When enabled, if the allowlist is non-empty, then access to your Prefect Cloud account will be restricted to only those IP addresses on the allowlist."""
    enforcing_ip_allowlist = ctx.meta["enforce_ip_allowlist"]
    if enforcing_ip_allowlist:
        exit_with_success("IP allowlist is already enabled.")

    async with get_cloud_client(infer_cloud_url=True) as client:
        my_access_if_enabled = await client.check_ip_allowlist_access()
        if not my_access_if_enabled.allowed:
            exit_with_error(
                f"Error enabling IP allowlist: {my_access_if_enabled.detail}"
            )

        logger.debug(my_access_if_enabled.detail)

        if not typer.confirm(
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
    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        _print_ip_allowlist_table(
            ip_allowlist, enabled=ctx.meta["enforce_ip_allowlist"]
        )


class IPNetworkArg(BaseModel):
    raw: str
    parsed: IPvAnyNetwork


def parse_ip_network_argument(val: str) -> IPNetworkArg:
    return IPNetworkArg(
        raw=val,
        parsed=val,  # type: ignore
    )


IP_ARGUMENT = Annotated[
    IPNetworkArg,
    typer.Argument(
        parser=parse_ip_network_argument,
        help="An IP address or range in CIDR notation. E.g. 192.168.1.0 or 192.168.1.0/24",
        metavar="IP address or range",
    ),
]


@ip_allowlist_app.command()
async def add(
    ctx: typer.Context,
    ip_address_or_range: IP_ARGUMENT,
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="A short description to annotate the entry with.",
    ),
):
    """Add a new IP entry to your account IP allowlist."""
    new_entry = IPAllowlistEntry(
        ip_network=ip_address_or_range.parsed, description=description, enabled=True
    )

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        existing_entry_with_same_ip = None
        for entry in ip_allowlist.entries:
            if entry.ip_network == ip_address_or_range.parsed:
                existing_entry_with_same_ip = entry
                break

        if existing_entry_with_same_ip:
            if not typer.confirm(
                f"There's already an entry for this IP ({ip_address_or_range.raw}). Do you want to overwrite it?"
            ):
                exit_with_error("Aborted.")
            ip_allowlist.entries.remove(existing_entry_with_same_ip)

        ip_allowlist.entries.append(new_entry)

        try:
            await client.update_account_ip_allowlist(ip_allowlist)
        except PrefectHTTPStatusError as exc:
            _handle_update_error(exc)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(
            updated_ip_allowlist, enabled=ctx.meta["enforce_ip_allowlist"]
        )


@ip_allowlist_app.command()
async def remove(ctx: typer.Context, ip_address_or_range: IP_ARGUMENT):
    """Remove an IP entry from your account IP allowlist."""
    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()
        ip_allowlist.entries = [
            entry
            for entry in ip_allowlist.entries
            if entry.ip_network != ip_address_or_range.parsed
        ]

        try:
            await client.update_account_ip_allowlist(ip_allowlist)
        except PrefectHTTPStatusError as exc:
            _handle_update_error(exc)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(
            updated_ip_allowlist, enabled=ctx.meta["enforce_ip_allowlist"]
        )


@ip_allowlist_app.command()
async def toggle(ctx: typer.Context, ip_address_or_range: IP_ARGUMENT):
    """Toggle the enabled status of an individual IP entry in your account IP allowlist."""
    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        found_matching_entry = False
        for entry in ip_allowlist.entries:
            if entry.ip_network == ip_address_or_range.parsed:
                entry.enabled = not entry.enabled
                found_matching_entry = True
                break

        if not found_matching_entry:
            exit_with_error(
                f"No entry found with IP address `{ip_address_or_range.raw}`."
            )

        try:
            await client.update_account_ip_allowlist(ip_allowlist)
        except PrefectHTTPStatusError as exc:
            _handle_update_error(exc)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(
            updated_ip_allowlist, enabled=ctx.meta["enforce_ip_allowlist"]
        )


def _print_ip_allowlist_table(ip_allowlist: IPAllowlist, enabled: bool):
    if not ip_allowlist.entries:
        app.console.print(
            Panel(
                "IP allowlist is empty. Add an entry to secure access to your Prefect Cloud account.",
                expand=False,
            )
        )
        return

    red_asterisk_if_not_enabled = "[red]*[/red]" if enabled is False else ""

    table = Table(
        title="IP Allowlist " + red_asterisk_if_not_enabled,
        caption=f"{red_asterisk_if_not_enabled} Enforcement is "
        f"[bold]{'ENABLED' if enabled else '[red]DISABLED[/red]'}[/bold].",
        caption_style="not dim",
    )

    table.add_column("IP Address", style="cyan", no_wrap=True)
    table.add_column("Description", style="blue", no_wrap=False)
    table.add_column("Enabled", style="green", justify="right", no_wrap=True)
    table.add_column("Last Seen", style="magenta", justify="right", no_wrap=True)

    for entry in ip_allowlist.entries:
        table.add_row(
            str(entry.ip_network),
            entry.description,
            str(entry.enabled),
            entry.last_seen or "Never",
            style="dim" if not entry.enabled else None,
        )

    app.console.print(table)


def _handle_update_error(error: PrefectHTTPStatusError):
    if error.response.status_code == 422 and (
        details := (
            error.response.json().get("detail")
            or error.response.json().get("exception_detail")
        )
    ):
        exit_with_error(f"Error updating allowlist: {details}")
    else:
        raise error

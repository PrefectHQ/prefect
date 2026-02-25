"""Manage Prefect Cloud IP Allowlists."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

import cyclopts
from rich.panel import Panel
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._cloud_utils import confirm_logged_in
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

ip_allowlist_app: cyclopts.App = cyclopts.App(
    name="ip-allowlist",
    alias="ip-allowlists",
    help="Manage Prefect Cloud IP Allowlists.",
    version_flags=[],
    help_flags=["--help"],
)


async def _check_ip_allowlist_access() -> bool:
    """Check if the account has access to IP allowlisting.

    Returns the enforce_ip_allowlist setting value.
    Exits with an error if the account does not have access.
    """
    from prefect.client.cloud import get_cloud_client

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(infer_cloud_url=True) as client:
        account_settings = await client.read_account_settings()

    if "enforce_ip_allowlist" not in account_settings:
        exit_with_error("IP allowlisting is not available for this account.")

    return account_settings.get("enforce_ip_allowlist", False)


def _print_ip_allowlist_table(ip_allowlist: Any, enabled: bool) -> None:
    from prefect.client.schemas.objects import IPAllowlist

    if TYPE_CHECKING:
        assert isinstance(ip_allowlist, IPAllowlist)

    if not ip_allowlist.entries:
        _cli.console.print(
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

    _cli.console.print(table)


def _handle_update_error(error: Any) -> None:
    from prefect.exceptions import PrefectHTTPStatusError

    if TYPE_CHECKING:
        assert isinstance(error, PrefectHTTPStatusError)
    if error.response.status_code == 422 and (
        details := (
            error.response.json().get("detail")
            or error.response.json().get("exception_detail")
        )
    ):
        exit_with_error(f"Error updating allowlist: {details}")
    else:
        raise error


def _parse_ip_network(val: str) -> Any:
    """Parse and validate an IP network argument."""
    from pydantic import BaseModel, IPvAnyNetwork, ValidationError

    class IPNetworkArg(BaseModel):
        raw: str
        parsed: IPvAnyNetwork

    try:
        return IPNetworkArg(raw=val, parsed=val)
    except ValidationError:
        exit_with_error(
            f"Invalid value for 'IP address or range': {val!r} is not a valid"
            " IP address or CIDR range."
        )


@ip_allowlist_app.command(name="enable")
@with_cli_exception_handling
async def ip_allowlist_enable():
    """Enable the IP allowlist for your account. When enabled, if the allowlist is non-empty, then access to your Prefect Cloud account will be restricted to only those IP addresses on the allowlist."""
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client

    enforcing_ip_allowlist = await _check_ip_allowlist_access()
    if enforcing_ip_allowlist:
        exit_with_success("IP allowlist is already enabled.")

    async with get_cloud_client(infer_cloud_url=True) as client:
        my_access_if_enabled = await client.check_ip_allowlist_access()
        from prefect.logging import get_logger

        get_logger(__name__).debug(my_access_if_enabled.detail)
        if not my_access_if_enabled.allowed:
            exit_with_error(
                f"Error enabling IP allowlist: {my_access_if_enabled.detail}"
            )

        if not confirm(
            "Enabling the IP allowlist will restrict Prefect Cloud API and UI access to only the IP addresses on the list. "
            "Continue?",
            console=_cli.console,
        ):
            exit_with_error("Aborted.")
        await client.update_account_settings({"enforce_ip_allowlist": True})

    exit_with_success("IP allowlist enabled.")


@ip_allowlist_app.command(name="disable")
@with_cli_exception_handling
async def ip_allowlist_disable():
    """Disable the IP allowlist for your account. When disabled, all IP addresses will be allowed to access your Prefect Cloud account."""
    from prefect.client.cloud import get_cloud_client

    await _check_ip_allowlist_access()

    async with get_cloud_client(infer_cloud_url=True) as client:
        await client.update_account_settings({"enforce_ip_allowlist": False})

    exit_with_success("IP allowlist disabled.")


@ip_allowlist_app.command(name="ls")
@with_cli_exception_handling
async def ip_allowlist_ls():
    """Fetch and list all IP allowlist entries in your account."""
    from prefect.client.cloud import get_cloud_client

    enforcing_ip_allowlist = await _check_ip_allowlist_access()

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(ip_allowlist, enabled=enforcing_ip_allowlist)


@ip_allowlist_app.command(name="add")
@with_cli_exception_handling
async def ip_allowlist_add(
    ip_address_or_range: Annotated[
        str,
        cyclopts.Parameter(
            help="An IP address or range in CIDR notation. E.g. 192.168.1.0 or 192.168.1.0/24",
        ),
    ],
    *,
    description: Annotated[
        str | None,
        cyclopts.Parameter(
            "--description",
            alias="-d",
            help="A short description to annotate the entry with.",
        ),
    ] = None,
):
    """Add a new IP entry to your account IP allowlist."""
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client
    from prefect.client.schemas.objects import IPAllowlistEntry
    from prefect.exceptions import PrefectHTTPStatusError

    ip_arg = _parse_ip_network(ip_address_or_range)
    enforcing_ip_allowlist = await _check_ip_allowlist_access()

    new_entry = IPAllowlistEntry(
        ip_network=ip_arg.parsed, description=description, enabled=True
    )

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        existing_entry_with_same_ip = None
        for entry in ip_allowlist.entries:
            if entry.ip_network == ip_arg.parsed:
                existing_entry_with_same_ip = entry
                break

        if existing_entry_with_same_ip:
            if not confirm(
                f"There's already an entry for this IP ({ip_arg.raw}). Do you want to overwrite it?",
                console=_cli.console,
            ):
                exit_with_error("Aborted.")
            ip_allowlist.entries.remove(existing_entry_with_same_ip)

        ip_allowlist.entries.append(new_entry)

        try:
            await client.update_account_ip_allowlist(ip_allowlist)
        except PrefectHTTPStatusError as exc:
            _handle_update_error(exc)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(updated_ip_allowlist, enabled=enforcing_ip_allowlist)


@ip_allowlist_app.command(name="remove")
@with_cli_exception_handling
async def ip_allowlist_remove(
    ip_address_or_range: Annotated[
        str,
        cyclopts.Parameter(
            help="An IP address or range in CIDR notation. E.g. 192.168.1.0 or 192.168.1.0/24",
        ),
    ],
):
    """Remove an IP entry from your account IP allowlist."""
    from prefect.client.cloud import get_cloud_client
    from prefect.exceptions import PrefectHTTPStatusError

    ip_arg = _parse_ip_network(ip_address_or_range)
    enforcing_ip_allowlist = await _check_ip_allowlist_access()

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()
        ip_allowlist.entries = [
            entry for entry in ip_allowlist.entries if entry.ip_network != ip_arg.parsed
        ]

        try:
            await client.update_account_ip_allowlist(ip_allowlist)
        except PrefectHTTPStatusError as exc:
            _handle_update_error(exc)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(updated_ip_allowlist, enabled=enforcing_ip_allowlist)


@ip_allowlist_app.command(name="toggle")
@with_cli_exception_handling
async def ip_allowlist_toggle(
    ip_address_or_range: Annotated[
        str,
        cyclopts.Parameter(
            help="An IP address or range in CIDR notation. E.g. 192.168.1.0 or 192.168.1.0/24",
        ),
    ],
):
    """Toggle the enabled status of an individual IP entry in your account IP allowlist."""
    from prefect.client.cloud import get_cloud_client
    from prefect.exceptions import PrefectHTTPStatusError

    ip_arg = _parse_ip_network(ip_address_or_range)
    enforcing_ip_allowlist = await _check_ip_allowlist_access()

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        found_matching_entry = False
        for entry in ip_allowlist.entries:
            if entry.ip_network == ip_arg.parsed:
                entry.enabled = not entry.enabled
                found_matching_entry = True
                break

        if not found_matching_entry:
            exit_with_error(f"No entry found with IP address `{ip_arg.raw}`.")

        try:
            await client.update_account_ip_allowlist(ip_allowlist)
        except PrefectHTTPStatusError as exc:
            _handle_update_error(exc)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(updated_ip_allowlist, enabled=enforcing_ip_allowlist)

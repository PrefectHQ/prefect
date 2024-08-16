from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli.cloud import cloud_app, confirm_logged_in
from prefect.cli.root import app
from prefect.client.cloud import get_cloud_client

ip_allowlist_app = PrefectTyper(
    name="ip-allowlist", help="Manage Prefect Cloud IP Allowlists"
)
cloud_app.add_typer(ip_allowlist_app, aliases=["ip-allowlists"])


@ip_allowlist_app.command()
async def ls():
    """
    Fetch and list all IP allowlist entries in your workspace
    """
    confirm_logged_in()

    async with get_cloud_client() as client:
        ip_allowlist = await client.read_account_ip_allowlist()

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
            )

        app.console.print(table)

from prefect.cli._types import PrefectTyper
from prefect.cli.cloud import cloud_app

ip_allowlist_app = PrefectTyper(
    name="ip-allowlist", help="Manage Prefect Cloud IP Allowlists"
)
cloud_app.add_typer(ip_allowlist_app, aliases=["ip-allowlists"])


@ip_allowlist_app.command()
async def ls():
    """
    Fetch and list all IP allowlist entries in your workspace
    """
    pass

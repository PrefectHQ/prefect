"""
Command line interface for working with webhooks
"""
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app

webhook_app = PrefectTyper(
    name="webhook", help="Commands for starting and interacting with webhooks"
)
app.add_typer(webhook_app)


@webhook_app.command()
async def start():
    print("YOLO")

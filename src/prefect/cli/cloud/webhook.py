"""
Command line interface for working with webhooks
"""

import typer
from typing_extensions import Annotated
from typing import Optional

from prefect.cli._types import PrefectTyper
from prefect.cli.cloud.cloud import cloud_app, confirm_logged_in
from prefect.client.cloud import get_cloud_client
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.settings import PREFECT_API_URL
from rich.table import Table

webhook_app = PrefectTyper(
    name="webhook", help="Commands for interacting with Prefect Cloud Webhooks"
)
cloud_app.add_typer(webhook_app, aliases=["webhooks"])


@webhook_app.command()
async def get(
    webhook_id: Annotated[Optional[str], typer.Argument()] = None,
    all: bool = typer.Option(
        False, "--all", "-a", help="Retrieve all webhooks in your workspace"
    ),
):
    """
    Retrieve a webhook by ID.
    Optionally, fetch all webhooks with the --all flag
    """

    if not webhook_id and not all:
        exit_with_error("Please provide a webhook ID or use the --all flag")

    if webhook_id and all:
        exit_with_error(
            "Please provide a webhook ID or use the --all flag, but not both"
        )

    confirm_logged_in()

    display_table = Table(show_lines=True)
    for field in ["webhook id", "url slug", "name", "enabled?", "template"]:
        display_table.add_column(field)

    # The /webhooks API lives inside the /accounts/{id}/workspaces/{id} routing tree
    async with get_cloud_client(host=PREFECT_API_URL.value()) as client:
        retrieved_webhooks = []

        if all:
            retrieved_webhooks = await client.request("POST", "/webhooks/filter")
        else:
            retrieved_webhooks = [
                await client.request("GET", f"/webhooks/{webhook_id}")
            ]

        for webhook in retrieved_webhooks:
            display_table.add_row(
                webhook["id"],
                webhook["slug"],
                webhook["name"],
                str(webhook["enabled"]),
                webhook["template"],
            )

        app.console.print(display_table)


@webhook_app.command()
async def create(
    webhook_name: str,
    description: str = typer.Option(
        "", "--description", "-d", help="Description of the webhook"
    ),
    template: str = typer.Option(
        None, "--template", "-t", help="Jinja2 template expression"
    ),
):
    """
    Create a new Cloud webhook
    """
    if not template:
        exit_with_error(
            "Please provide a Jinja2 template expression in the --template flag \nwhich"
            ' should define (at minimum) the following attributes: \n{ "event":'
            ' "your.event.name", "resource": { "prefect.resource.id":'
            ' "your.resource.id" } }'
            " \nhttps://docs.prefect.io/latest/cloud/webhooks/#webhook-templates"
        )

    confirm_logged_in()

    # The /webhooks API lives inside the /accounts/{id}/workspaces/{id} routing tree
    async with get_cloud_client(host=PREFECT_API_URL.value()) as client:
        response = await client.request(
            "POST",
            "/webhooks/",
            json={
                "name": webhook_name,
                "description": description,
                "template": template,
            },
        )
        app.console.print(f'Successfully created {response["name"]}')


@webhook_app.command()
async def rotate(webhook_id: str):
    """
    Rotate url for an existing Cloud webhook, in case it has been compromised
    """
    confirm_logged_in()

    confirm_rotate = typer.confirm(
        "Are you sure you want to rotate? This will invalidate the old URL."
    )

    if not confirm_rotate:
        return

    # The /webhooks API lives inside the /accounts/{id}/workspaces/{id} routing tree
    async with get_cloud_client(host=PREFECT_API_URL.value()) as client:
        response = await client.request("POST", f"/webhooks/{webhook_id}/rotate")
        app.console.print(f'Successfully rotated webhook URL to {response["slug"]}')


@webhook_app.command()
async def toggle(
    webhook_id: str,
):
    """
    Toggle the enabled status of an existing Cloud webhook
    """

    status_lookup = {True: "enabled", False: "disabled"}

    async with get_cloud_client(host=PREFECT_API_URL.value()) as client:
        response = await client.request("GET", f"/webhooks/{webhook_id}")
        current_status = response["enabled"]
        new_status = not current_status

        await client.request(
            "PATCH", f"/webhooks/{webhook_id}", json={"enabled": new_status}
        )
        app.console.print(f"Webhook is now {status_lookup[new_status]}")


@webhook_app.command()
async def update(
    webhook_id: str,
    webhook_name: str = typer.Option(None, "--name", "-n", help="Webhook name"),
    description: str = typer.Option(
        None, "--description", "-d", help="Description of the webhook"
    ),
    template: str = typer.Option(
        None, "--template", "-t", help="Jinja2 template expression"
    ),
):
    """
    Partially update an existing Cloud webhook
    """
    confirm_logged_in()

    # The /webhooks API lives inside the /accounts/{id}/workspaces/{id} routing tree
    async with get_cloud_client(host=PREFECT_API_URL.value()) as client:
        response = await client.request("GET", f"/webhooks/{webhook_id}")
        update_payload = {
            "name": webhook_name or response["name"],
            "description": description or response["description"],
            "template": template or response["template"],
        }

        await client.request("PUT", f"/webhooks/{webhook_id}", json=update_payload)
        app.console.print(f"Successfully updated webhook {webhook_id}")


@webhook_app.command()
async def delete(webhook_id: str):
    """
    Delete an existing Cloud webhook
    """
    confirm_logged_in()

    confirm_delete = typer.confirm(
        "Are you sure you want to delete it? This cannot be undone."
    )

    if not confirm_delete:
        return

    # The /webhooks API lives inside the /accounts/{id}/workspaces/{id} routing tree
    async with get_cloud_client(host=PREFECT_API_URL.value()) as client:
        await client.request("DELETE", f"/webhooks/{webhook_id}")
        app.console.print(f"Successfully deleted webhook {webhook_id}")

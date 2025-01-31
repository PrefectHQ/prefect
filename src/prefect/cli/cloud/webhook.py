"""
Command line interface for working with webhooks
"""

from typing import Dict, List
from uuid import UUID

import typer
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.cloud import cloud_app, confirm_logged_in
from prefect.cli.root import app, is_interactive
from prefect.client.cloud import get_cloud_client
from prefect.exceptions import ObjectNotFound
from prefect.settings import PREFECT_API_URL

webhook_app: PrefectTyper = PrefectTyper(
    name="webhook", help="Manage Prefect Cloud Webhooks"
)
cloud_app.add_typer(webhook_app, aliases=["webhooks"])


def _render_webhooks_into_table(webhooks: List[Dict[str, str]]) -> Table:
    display_table = Table(show_lines=True)
    for field in ["webhook id", "url slug", "name", "enabled?", "template"]:
        # overflow=fold allows the entire table value to display in the terminal
        # even if it is too long for the computed column width
        # https://rich.readthedocs.io/en/stable/reference/table.html#rich.table.Column.overflow
        display_table.add_column(field, overflow="fold")

    for webhook in webhooks:
        display_table.add_row(
            webhook["id"],
            webhook["slug"],
            webhook["name"],
            str(webhook["enabled"]),
            webhook["template"],
        )
    return display_table


@webhook_app.command()
async def ls():
    """
    Fetch and list all webhooks in your workspace
    """
    confirm_logged_in()

    # The /webhooks API lives inside the /accounts/{id}/workspaces/{id} routing tree
    async with get_cloud_client(host=PREFECT_API_URL.value()) as client:
        retrieved_webhooks = await client.request("POST", "/webhooks/filter")
        display_table = _render_webhooks_into_table(retrieved_webhooks)
        app.console.print(display_table)


@webhook_app.command()
async def get(webhook_id: UUID):
    """
    Retrieve a webhook by ID.
    """
    confirm_logged_in()

    # The /webhooks API lives inside the /accounts/{id}/workspaces/{id} routing tree
    async with get_cloud_client(host=PREFECT_API_URL.value()) as client:
        webhook = await client.request("GET", f"/webhooks/{webhook_id}")
        display_table = _render_webhooks_into_table([webhook])
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
            " \nhttps://docs.prefect.io/latest/automate/events/webhook-triggers#webhook-templates"
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
        app.console.print(f"Successfully created webhook {response['name']}")


@webhook_app.command()
async def rotate(webhook_id: UUID):
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
        app.console.print(f"Successfully rotated webhook URL to {response['slug']}")


@webhook_app.command()
async def toggle(
    webhook_id: UUID,
):
    """
    Toggle the enabled status of an existing Cloud webhook
    """
    confirm_logged_in()

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
    webhook_id: UUID,
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
async def delete(webhook_id: UUID):
    """
    Delete an existing Cloud webhook
    """
    confirm_logged_in()

    if is_interactive() and not typer.confirm(
        (f"Are you sure you want to delete webhook with id '{webhook_id!s}'?"),
        default=False,
    ):
        exit_with_error("Deletion aborted.")

    # The /webhooks API lives inside the /accounts/{id}/workspaces/{id} routing tree
    async with get_cloud_client(host=PREFECT_API_URL.value()) as client:
        try:
            await client.request("DELETE", f"/webhooks/{webhook_id}")
            app.console.print(f"Successfully deleted webhook {webhook_id}")
        except ObjectNotFound:
            exit_with_error(f"Webhook with id '{webhook_id!s}' not found.")
        except Exception as exc:
            exit_with_error(f"Error deleting webhook: {exc}")

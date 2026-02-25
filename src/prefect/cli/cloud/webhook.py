"""Manage Prefect Cloud Webhooks."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._cloud_utils import (
    confirm_logged_in,
    render_webhooks_into_table,
)
from prefect.cli._utilities import (
    exit_with_error,
    with_cli_exception_handling,
)

webhook_app: cyclopts.App = cyclopts.App(
    name="webhook",
    alias="webhooks",
    help="Manage Prefect Cloud Webhooks.",
    version_flags=[],
    help_flags=["--help"],
)


@webhook_app.command(name="ls")
@with_cli_exception_handling
async def webhook_ls():
    """Fetch and list all webhooks in your workspace."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        retrieved_webhooks = await client.request("POST", "/webhooks/filter")
        display_table = render_webhooks_into_table(retrieved_webhooks)
        _cli.console.print(display_table)


@webhook_app.command(name="get")
@with_cli_exception_handling
async def webhook_get(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to retrieve.")],
):
    """Retrieve a webhook by ID."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        webhook = await client.request("GET", f"/webhooks/{webhook_id}")
        display_table = render_webhooks_into_table([webhook])
        _cli.console.print(display_table)


@webhook_app.command(name="create")
@with_cli_exception_handling
async def webhook_create(
    webhook_name: Annotated[str, cyclopts.Parameter(help="The name of the webhook.")],
    *,
    description: Annotated[
        str,
        cyclopts.Parameter(
            "--description", alias="-d", help="Description of the webhook"
        ),
    ] = "",
    template: Annotated[
        str | None,
        cyclopts.Parameter("--template", alias="-t", help="Jinja2 template expression"),
    ] = None,
):
    """Create a new Cloud webhook."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    if not template:
        exit_with_error(
            "Please provide a Jinja2 template expression in the --template flag \nwhich"
            ' should define (at minimum) the following attributes: \n{ "event":'
            ' "your.event.name", "resource": { "prefect.resource.id":'
            ' "your.resource.id" } }'
            " \nhttps://docs.prefect.io/latest/automate/events/webhook-triggers#webhook-templates"
        )

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request(
            "POST",
            "/webhooks/",
            json={
                "name": webhook_name,
                "description": description,
                "template": template,
            },
        )
        _cli.console.print(f"Successfully created webhook {response['name']}")


@webhook_app.command(name="rotate")
@with_cli_exception_handling
async def webhook_rotate(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to rotate.")],
):
    """Rotate url for an existing Cloud webhook, in case it has been compromised."""
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    if not confirm(
        "Are you sure you want to rotate? This will invalidate the old URL.",
        console=_cli.console,
    ):
        return

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request("POST", f"/webhooks/{webhook_id}/rotate")
        _cli.console.print(f"Successfully rotated webhook URL to {response['slug']}")


@webhook_app.command(name="toggle")
@with_cli_exception_handling
async def webhook_toggle(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to toggle.")],
):
    """Toggle the enabled status of an existing Cloud webhook."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    status_lookup = {True: "enabled", False: "disabled"}

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request("GET", f"/webhooks/{webhook_id}")
        current_status = response["enabled"]
        new_status = not current_status

        await client.request(
            "PATCH", f"/webhooks/{webhook_id}", json={"enabled": new_status}
        )
        _cli.console.print(f"Webhook is now {status_lookup[new_status]}")


@webhook_app.command(name="update")
@with_cli_exception_handling
async def webhook_update(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to update.")],
    *,
    webhook_name: Annotated[
        str | None,
        cyclopts.Parameter("--name", alias="-n", help="Webhook name"),
    ] = None,
    description: Annotated[
        str | None,
        cyclopts.Parameter(
            "--description", alias="-d", help="Description of the webhook"
        ),
    ] = None,
    template: Annotated[
        str | None,
        cyclopts.Parameter("--template", alias="-t", help="Jinja2 template expression"),
    ] = None,
):
    """Partially update an existing Cloud webhook."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request("GET", f"/webhooks/{webhook_id}")
        update_payload = {
            "name": webhook_name or response["name"],
            "description": description or response["description"],
            "template": template or response["template"],
        }

        await client.request("PUT", f"/webhooks/{webhook_id}", json=update_payload)
        _cli.console.print(f"Successfully updated webhook {webhook_id}")


@webhook_app.command(name="delete")
@with_cli_exception_handling
async def webhook_delete(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to delete.")],
):
    """Delete an existing Cloud webhook."""
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client
    from prefect.exceptions import ObjectNotFound
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    if _cli.is_interactive() and not confirm(
        f"Are you sure you want to delete webhook with id '{webhook_id!s}'?",
        default=False,
        console=_cli.console,
    ):
        exit_with_error("Deletion aborted.")

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        try:
            await client.request("DELETE", f"/webhooks/{webhook_id}")
            _cli.console.print(f"Successfully deleted webhook {webhook_id}")
        except ObjectNotFound:
            exit_with_error(f"Webhook with id '{webhook_id!s}' not found.")
        except Exception as exc:
            exit_with_error(f"Error deleting webhook: {exc}")

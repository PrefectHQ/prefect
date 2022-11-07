import subprocess
import time
from pathlib import Path
from typing import Iterable

import readchar
import typer
from rich.live import Live
from rich.table import Table

from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app

AVAILABLE_PROVIDERS = ["AWS", "GCP", "Azure"]


def build_table(selected_idx: int, providers: Iterable[str]) -> Table:
    """
    Generate a table of providers. The `select_idx` of workspaces will be highlighted.

    Args:
        selected_idx: currently selected index
        workspaces: Iterable of strings

    Returns:
        rich.table.Table
    """

    table = Table()
    table.add_column(
        "[#024dfd]Select a Cloud Provider:",
        justify="right",
        style="#8ea0ae",
        no_wrap=True,
    )

    for i, provider in enumerate(sorted(providers)):
        if i == selected_idx:
            table.add_row("[#024dfd on #FFFFFF]> " + provider)
        else:
            table.add_row("  " + provider)
    return table


@app.command()
async def easy_deploy(path: str):
    provider = select_provider()
    app.console.clear()
    app.console.print(
        f"You have selected [blue]quick-deploy[/blue] on "
        f"[#024dfd]{provider}[/#024dfd]"
        "."
    )
    time.sleep(1)
    app.console.print(
        "It looks like you are missing necessary configuration components.\n"
        f"[blue]Would you like to set them up now?[/blue]"
    )

    setup = typer.prompt(f"Y/N")

    if setup:
        app.console.print(
            f"[blue]Please authenticate your GCP account using the browser tab.[/blue]"
        )
        time.sleep(1)
        authenticate_gcp()
        time.sleep(1.5)
        app.console.clear()
        app.console.print(f"[green]Success![/green]\n")
        time.sleep(1)
        app.console.print(
            "We need to create a GCP Credentials block for quick-deploy. "
            "This will require Prefect to create a new GCP credentials file with the following privileges:\n"
            "- Priv 1\n"
            "- Priv 2\n"
            "- Priv 3\n"
            f"[blue]Can we create a limited scope GCP credentials file for you?[/blue]"
        )
        time.sleep(1)
        creds = typer.prompt(f"Y/N")
        time.sleep(2)
        app.console.clear()
        app.console.print(
            f"[green]Your quick-deploy GCP Credentials block has been created![/green]\n"
        )

        time.sleep(1)
        app.console.print(
            "We cannot find a Prefect quick-deploy storage bucket. We use storage buckets to store you code.\n"
            f"[blue]Can we create one for you?[/blue]"
        )
        time.sleep(1)
        creds = typer.prompt(f"Y/N")
        time.sleep(2)
        app.console.clear()
        app.console.print(
            f"[green]Your quick-deploy GCP storage bucket has been created![/green]\n"
        )

        time.sleep(1)
        app.console.print(
            "It looks like the Google Cloud Run API is not activated on your account. "
            "Cloud Run Jobs are used for Prefect quick deployments.\n"
            f"[blue]Can we activate Google Cloud Run for you?[/blue]"
        )
        time.sleep(1)
        creds = typer.prompt(f"Y/N")

        time.sleep(2)
        app.console.clear()
        app.console.print(f"[green]The Cloud Run API is now active![/green]\n")
        time.sleep(1)
        app.console.print(f"[green]Your configuration is all set![/green]\n")
        time.sleep(1)
        app.console.print(
            f"[blue]Please enter the path of your requirements.txt relative to the current working directory\n[/blue]"
            f"{Path.cwd()}/"
        )
        typer.prompt("relative path")
        time.sleep(0.5)
        name = path.split(":")[1]
        app.console.print(
            f"[green]Your deployment prefect-quick-deployment/{name} is now being created![/green]"
        )


def select_provider() -> str:
    """
    Given a list of workspaces, display them to user in a Table
    and allow them to select one.

    Args:
        workspaces: List of workspaces to choose from

    Returns:
        str: the selected workspace
    """

    current_idx = 0
    providers = sorted(AVAILABLE_PROVIDERS)
    selected_provider = None

    with Live(
        build_table(current_idx, providers), auto_refresh=False, console=app.console
    ) as live:
        while selected_provider is None:
            key = readchar.readkey()

            if key == readchar.key.UP:
                current_idx = current_idx - 1
                # wrap to bottom if at the top
                if current_idx < 0:
                    current_idx = len(providers) - 1
            elif key == readchar.key.DOWN:
                current_idx = current_idx + 1
                # wrap to top if at the bottom
                if current_idx >= len(providers):
                    current_idx = 0
            elif key == readchar.key.CTRL_C:
                # gracefully exit with no message
                exit_with_error("")
            elif key == readchar.key.ENTER:
                selected_provider = providers[current_idx]

            live.update(build_table(current_idx, providers), refresh=True)

        return selected_provider


def authenticate_gcp():

    subprocess.run(["gcloud", "auth", "login"])

import os
import subprocess
import time
from pathlib import Path
from typing import Iterable

import readchar
import typer
from rich.layout import Layout
from rich.live import Live
from rich.table import Table

from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app

AVAILABLE_PROVIDERS = [
    "AWS",
    "GCP",
    "Azure",
    "cobra",
    "stork",
    "penguin",
    "shark",
    "elephant",
    "buffalo",
    "whale",
    "wolf",
    "seal",
    "eagle",
    "wren",
    "horse",
    "rattlesnake",
    "ape",
    "crow",
    "tuna",
]


class CliTable:
    window = []
    window_size = 0
    window_top = 0
    window_bottom = None
    key_press = None
    idx = 0


def build_table(
    rows: Iterable[str],
    search_chars,
    console,
    cli_table: CliTable,
) -> Table:
    """
    Generate a table of providers. The `select_idx` of workspaces will be highlighted.

    Args:
        selected_idx: currently selected index
        workspaces: Iterable of strings

    Returns:
        rich.table.Table
    """
    layout = Layout()
    n_rows = os.get_terminal_size()[1]
    if n_rows != cli_table.window_size:
        cli_table.window_size = n_rows - 5

    if cli_table.window_bottom is None:
        cli_table.window_bottom = cli_table.window_size

    # page down
    if (
        cli_table.key_press == readchar.key.DOWN
        and cli_table.idx >= cli_table.window_bottom
    ):
        cli_table.window_top = cli_table.window_bottom - 1
        cli_table.window_bottom = cli_table.window_top + cli_table.window_size - 1
        cli_table.idx = cli_table.idx - 1

    # page up
    if cli_table.key_press == readchar.key.UP and cli_table.idx < cli_table.window_top:
        cli_table.window_top = cli_table.window_top - (cli_table.window_size - 1)
        cli_table.window_bottom = cli_table.window_top + cli_table.window_size
        cli_table.idx = cli_table.idx + 1

    # while n_rows >= 0:
    table = Table()
    table.add_column(
        "[#024dfd]Select a Cloud Provider:",
        justify="right",
        style="#8ea0ae",
        no_wrap=True,
    )
    table.add_row(f"[green]Search: '{search_chars}'[/green]")
    # table.add_row(f"idx: {cli_table.idx}, t: {cli_table.window_top}, b: {cli_table.window_bottom}, s: {cli_table.window_size}")

    start = max(0, cli_table.window_top)
    end = min(cli_table.window_bottom, len(rows))
    # print(f"start: {start}, end: {end}")
    for i, row in enumerate(rows[start:end]):
        position = i + cli_table.window_top
        # print(f"pos: {position} idx: {cli_table.idx}")
        if position == cli_table.idx:
            # print("HIT")
            table.add_row("[#024dfd on #FFFFFF]> " + row)
        else:
            table.add_row("  " + row)
    layout.update(table)
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
    providers = sorted(AVAILABLE_PROVIDERS)
    selectable_providers = providers
    selected_provider = None
    search_chars = ""

    cli_table = CliTable()

    with Live(
        build_table(providers, search_chars, app.console, cli_table),
        vertical_overflow="visble",
        auto_refresh=False,
        # console=app.console
    ) as live:
        while selected_provider is None:
            key = readchar.readkey()
            typed = False
            if key.isalnum() or key in ["/", "\\", ".", "-"]:
                search_chars += key
                cli_table.idx = 0
                typed = True
            elif key == readchar.key.BACKSPACE:
                search_chars = search_chars[:-1]
                cli_table.idx = 0
            elif key == readchar.key.UP:
                cli_table.idx = max(0, cli_table.idx - 1)
                # wrap to bottom if at the top
                if cli_table.idx < 0:
                    cli_table.idx = len(providers) - 1
            elif key == readchar.key.DOWN:
                cli_table.idx = cli_table.idx + 1
                # wrap to top if at the bottom
                if cli_table.idx >= len(providers):
                    cli_table.idx = 0
            elif key == readchar.key.CTRL_C:
                # gracefully exit with no message
                exit_with_error("")
            elif key == readchar.key.ENTER:
                selected_provider = selectable_providers[cli_table.idx]

            if typed:
                # cli_table.window_bottom = 0
                # cli_table.window_top = cli_table.window_size
                selectable_providers = [
                    p for p in selectable_providers if search_chars.lower() in p.lower()
                ]
                cli_table.window_bottom = None
                cli_table.window_top = 0
            else:
                selectable_providers = [
                    p for p in providers if search_chars.lower() in p.lower()
                ]

            cli_table.key_press = key
            live.update(
                build_table(selectable_providers, search_chars, app.console, cli_table),
                refresh=True,
            )

        return selected_provider


def authenticate_gcp():

    subprocess.run(["gcloud", "auth", "login"])

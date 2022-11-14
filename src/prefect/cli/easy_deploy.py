import os
import subprocess
import time
from pathlib import Path

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


class TableWindow:
    def __init__(self, header_offset=5):
        total_terminal_rows = os.get_terminal_size()[1]

        self.header_offset = header_offset
        self.size = total_terminal_rows - self.header_offset
        self.additional_rows = self.size - 1
        self.top = 0
        self.bottom = self.additional_rows

    def update_size(self):
        total_terminal_rows = os.get_terminal_size()[1]
        self.size = total_terminal_rows - self.header_offset

    def reset(self):
        self.bottom = None
        self.top = 0

    def page_up(self):
        self.bottom = self.top + 1
        self.top = max(0, self.top - self.additional_rows)

    def page_down(self):
        self.top = self.bottom - 1
        self.bottom = self.top + self.additional_rows

    def render(self, elements):
        pass


class CliTable:
    def __init__(self, elements, title):
        self.elements: dict = {el: i for i, el in enumerate(elements)}
        self.title = title
        self.active_elements: list = elements
        self.window = TableWindow()
        self.key_press = None
        self.idx = 0
        self.selected_element = None
        self.search_chars = ""

    def _refine_search(self):
        self.active_elements = [
            el for el in self.active_elements if self.search_chars in el.lower()
        ]

    def _search_all_elements(self):
        all_elements = list(self.elements.keys())
        self.active_elements = [
            el for el in all_elements if self.search_chars in el.lower()
        ]

    def _reset(self):
        self.idx = 0
        self.window.reset()

    def _process_up_key(self):
        # start of the list
        if self.idx <= 0:
            return

        # page up if at beginning of page
        elif self.idx < self.window.top + 1:
            self.window.page_up()

        else:
            self.idx -= 1

    def _process_down_key(self):
        # end of the list
        if self.idx >= len(self.active_elements) - 1:
            return

        # page down if at the end of the window
        elif self.idx >= self.window.bottom - 1:
            self.window.page_down()

        else:
            self.idx += 1

    def _process_ctrl_c(self):
        # gracefully exit with no message
        exit_with_error("")

    def _process_enter_key(self):
        self.selected_element = self.active_elements[self.idx]

    def _process_backspace_key(self):
        self.search_chars = self.search_chars[:-1]
        self._reset()
        self._search_all_elements()

    def _process_allowed_character_key(self, key):
        self.search_chars += key.lower()
        self._reset()
        self._refine_search()

    def process_keypress(self, key):
        self.key_press = key

        if key.isalnum() or key in ["/", "\\", ".", "-"]:
            self._process_allowed_character_key(key)

        elif key == readchar.key.BACKSPACE:
            self._process_backspace_key()

        elif key == readchar.key.UP:
            self._process_up_key()

        elif key == readchar.key.DOWN:
            self._process_down_key()

        elif key == readchar.key.CTRL_C:
            self._process_ctrl_c()

        elif key == readchar.key.ENTER:
            self._process_enter_key()

    def get_table_position_and_rows(self):
        start = max(0, self.window.top)
        end = min(self.window.bottom, len(self.elements))

        items = [
            (i + self.window.top, row)
            for i, row in enumerate(self.active_elements[start:end])
        ]
        # print(f"start: {start}, end: {end}, idx: {self.idx}, wdwsz: {self.window.size}, btm: {self.window.bottom} top: {self.window.top} ae: {len(self.active_elements)}")
        # print(items)
        return items

    def render_table(self):
        """
        Generate a table of providers. The `select_idx` of workspaces will be highlighted.

        Args:
            selected_idx: currently selected index
            workspaces: Iterable of strings

        Returns:
            rich.table.Table
        """
        self.window.update_size()

        layout = Layout()
        table = Table()
        table.add_column(
            header=f"[#024dfd]{self.title}",
            justify="right",
            style="#8ea0ae",
            no_wrap=True,
        )

        table.add_row(f"[green]Search: '{self.search_chars}'[/green]")

        for position, row in self.get_table_position_and_rows():
            if position == self.idx:
                table.add_row("[#024dfd on #FFFFFF]> " + row)
            else:
                table.add_row("  " + row)
        layout.update(table)
        return table


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

    cli_table = CliTable(title="Select a Cloud Provider:", elements=providers)

    with Live(
        cli_table.render_table(),
        vertical_overflow="visble",
        auto_refresh=False,
    ) as live:
        while cli_table.selected_element is None:
            key = readchar.readkey()
            cli_table.process_keypress(key=key)

            live.update(
                cli_table.render_table(),
                refresh=True,
            )
        return cli_table.selected_element


def authenticate_gcp():

    subprocess.run(["gcloud", "auth", "login"])


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

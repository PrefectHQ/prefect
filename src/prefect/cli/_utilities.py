"""
Utilities for Prefect CLI commands
"""
import functools
import traceback
from typing import Dict, List, Optional
import readchar

import typer
import typer.core
from click.exceptions import ClickException
from rich.table import Table
from rich.live import Live
from rich.prompt import Prompt

from prefect.exceptions import MissingProfileError
from prefect.settings import PREFECT_TEST_MODE


def exit_with_error(message, code=1, **kwargs):
    """
    Utility to print a stylized error message and exit with a non-zero code
    """
    from prefect.cli.root import app

    kwargs.setdefault("style", "red")
    app.console.print(message, **kwargs)
    raise typer.Exit(code)


def exit_with_success(message, **kwargs):
    """
    Utility to print a stylized success message and exit with a zero code
    """
    from prefect.cli.root import app

    kwargs.setdefault("style", "green")
    app.console.print(message, **kwargs)
    raise typer.Exit(0)


def with_cli_exception_handling(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (typer.Exit, typer.Abort, ClickException):
            raise  # Do not capture click or typer exceptions
        except MissingProfileError as exc:
            exit_with_error(exc)
        except Exception:
            if PREFECT_TEST_MODE.value():
                raise  # Reraise exceptions during test mode
            traceback.print_exc()
            exit_with_error("An exception occurred.")

    return wrapper


def prompt(message, **kwargs):
    """Utility to prompt the user for input with consistent styling"""
    return Prompt.ask(f"[bold][green]?[/] {message}[/]", **kwargs)


def prompt_select_from_table(
    console,
    prompt: str,
    columns: List[Dict],
    data: List[Dict],
    table_kwargs: Optional[Dict] = None,
) -> Dict:
    """
    Given a list of columns and some data, display options to user in a table
    and prompt them to select one.

    Args:
        prompt: A prompt to display to the user before the table.
        columns: A list of dicts with keys `header` and `key` to display in
            the table. The `header` value will be displayed in the table header
            and the `key` value will be used to lookup the value for each row
            in the provided data.
        data: A list of dicts with keys corresponding to the `key` values in
            the `columns` argument.
        table_kwargs: Additional kwargs to pass to the `rich.Table` constructor.
    Returns:
        dict: Data representation of the selected row
    """
    current_idx = 0
    selected_row = None
    first_run = True
    table_kwargs = table_kwargs or {}

    def build_table() -> Table:
        """
        Generate a table of options. The `current_idx` will be highlighted.
        """

        nonlocal first_run
        if first_run:
            console.print(
                f"[bold][green]?[/] {prompt} [bright_blue][Use arrows to move; enter to"
                " select][/]"
            )
        table = Table(**table_kwargs)
        table.add_column()
        for column in columns:
            table.add_column(column.get("header", ""))

        rows = []
        for item in data:
            rows.append(tuple(item.get(column.get("key")) for column in columns))

        for i, row in enumerate(rows):
            if i == current_idx:
                # Use blue for selected options
                table.add_row("[bold][blue]>", f"[bold][blue]{row[0]}[/]", *row[1:])
            else:
                table.add_row("  ", *row)
        first_run = False
        return table

    with Live(build_table(), auto_refresh=False, console=console) as live:
        while selected_row is None:
            key = readchar.readkey()

            if key == readchar.key.UP:
                current_idx = current_idx - 1
                # wrap to bottom if at the top
                if current_idx < 0:
                    current_idx = len(data) - 1
            elif key == readchar.key.DOWN:
                current_idx = current_idx + 1
                # wrap to top if at the bottom
                if current_idx >= len(data):
                    current_idx = 0
            elif key == readchar.key.CTRL_C:
                # gracefully exit with no message
                exit_with_error("")
            elif key == readchar.key.ENTER or key == readchar.key.CR:
                selected_row = data[current_idx]

            live.update(build_table(), refresh=True)

        return selected_row

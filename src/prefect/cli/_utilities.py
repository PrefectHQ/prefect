"""
Utilities for Prefect CLI commands
"""
import functools
import os
import traceback
from typing import Any, Tuple

import readchar
import typer
import typer.core
from click.exceptions import ClickException
from readchar.key import BACKSPACE, CTRL_C, DOWN, ENTER, UP
from rich.live import Live
from rich.table import Table

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


class TableWindow:
    def __init__(self, header_offset=5):
        total_terminal_rows = os.get_terminal_size()[1]

        self.header_offset = header_offset
        self.size = max(3, total_terminal_rows - self.header_offset)
        self.top = 0
        self.bottom = self.size - 1

    @property
    def additional_rows(self):
        return self.size - 1

    def update_size(self):
        total_terminal_rows = os.get_terminal_size()[1]
        self.size = max(3, total_terminal_rows - self.header_offset)

    def reset(self):
        self.top = 0
        self.bottom = self.additional_rows

    def page_up(self, top_min=0):
        self.bottom = self.top + 1
        self.top = max(top_min, self.top - self.additional_rows)

    def page_down(self, bottom_max):
        self.top = self.bottom - 1
        self.bottom = min(self.top + self.additional_rows, bottom_max)

    def get_rows(self, elements) -> Tuple[int, str]:
        rows = []
        for i, element in enumerate(elements[self.top : self.bottom]):
            position = i + self.top
            rows.append((position, element))

        return rows


class CliTable:
    def __init__(self, elements, title):
        self.elements: dict = {el: i for i, el in enumerate(elements)}
        self.title = title
        self.active_elements: list = elements
        self.window = TableWindow()
        self.idx = 0
        self.selected_element = None
        self.search_chars = ""
        self.key_function_map = {
            BACKSPACE: self._process_backspace_key,
            ENTER: self._process_enter_key,
            UP: self._process_up_key,
            DOWN: self._process_down_key,
            CTRL_C: self._process_ctrl_c,
        }

    def _refine_search(self):
        self.active_elements = [
            el for el in self.active_elements if self.search_chars in el.lower()
        ]

    def _search_all_elements(self):
        all_elements = list(self.elements.keys())
        self.active_elements = [
            el for el in all_elements if self.search_chars in el.lower()
        ]

    def _reset_window(self):
        """Set the window to include the first n items of the active elements,
        with the index pointing to the first element of the list.
        """
        self.idx = 0
        self.window.reset()

    def _process_up_key(self):
        # don't do anything at start of the list
        if self.idx <= 0:
            return

        # page up if at beginning of page
        elif self.idx < self.window.top + 1:
            self.window.page_up()

        else:
            self.idx -= 1

    def _process_down_key(self):
        # don't do anything at end of the list
        if self.idx >= len(self.active_elements) - 1:
            return

        # page down if at the end of the window
        elif self.idx >= self.window.bottom - 1:
            self.window.page_down(bottom_max=len(self.active_elements))

        else:
            self.idx += 1

    def _process_ctrl_c(self):
        # gracefully exit with no message
        exit_with_error("")

    def _process_enter_key(self):
        self.selected_element = self.active_elements[self.idx]

    def _process_backspace_key(self):
        self.search_chars = self.search_chars[:-1]
        self._reset_window()
        self._search_all_elements()

    def _process_search_key(self, key):
        self.search_chars += key.lower()
        self._reset_window()
        self._refine_search()

    def _process_interaction_key(self, key):
        function = self.key_function_map.get(key)

        if function is not None:
            function()

    def _process_keypress(self, key):
        if key.isalnum() or key in ["/", "\\", ".", "-"]:
            self._process_search_key(key)
        else:
            self._process_interaction_key(key)

    def _initialize_rich_table(self, searchable: bool = True) -> Table:
        table = Table()
        table.add_column(
            header=f"[#024dfd]{self.title}",
            justify="right",
            style="#8ea0ae",
            no_wrap=True,
        )

        if searchable:
            table.add_row(f"[green]Search: '{self.search_chars}'[/green]")

        return table

    def _add_highlighted_row(self, table: Table, row: Any) -> Table:
        table.add_row("[#024dfd on #FFFFFF]> " + row)
        return table

    def _add_basic_row(self, table: Table, row: Any) -> Table:
        table.add_row("  " + row)
        return table

    def _add_rows_to_rich_table(self, table) -> Table:
        for position, row in self.window.get_rows(self.active_elements):
            if position == self.idx:
                table = self._add_highlighted_row(table=table, row=row)
            else:
                table = self._add_basic_row(table=table, row=row)

        return table

    def _render_table(self):
        """
        Generate a table of providers. The `select_idx` of workspaces will be highlighted.

        Args:
            selected_idx: currently selected index
            workspaces: Iterable of strings

        Returns:
            rich.table.Table
        """
        self.window.update_size()
        table = self._initialize_rich_table()
        table = self._add_rows_to_rich_table(table)

        return table

    def start(self):
        with Live(
            self._render_table(),
            vertical_overflow="visble",
            auto_refresh=False,
        ) as live:
            while self.selected_element is None:
                key = readchar.readkey()
                self._process_keypress(key=key)

                live.update(
                    self._render_table(),
                    refresh=True,
                )
            return self.selected_element

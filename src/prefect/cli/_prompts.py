"""
Utilities for prompting the user for input
"""
from datetime import timedelta
from rich.prompt import PromptBase, InvalidResponse
from rich.text import Text

from prefect.client.schemas.schedules import (
    SCHEDULE_TYPES,
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)

from typing import Any, Dict, List, Optional
import readchar

from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.prompt import Prompt, Confirm
from prefect.cli._utilities import exit_with_error

from prefect.client.utilities import inject_client

from prefect.client.orchestration import PrefectClient

from prefect.client.collections import get_collections_metadata_client

from prefect.client.schemas.actions import WorkPoolCreate


def prompt(message, **kwargs):
    """Utility to prompt the user for input with consistent styling"""
    return Prompt.ask(f"[bold][green]?[/] {message}[/]", **kwargs)


def confirm(message, **kwargs):
    """Utility to prompt the user for confirmation with consistent styling"""
    return Confirm.ask(f"[bold][green]?[/] {message}[/]", **kwargs)


def prompt_select_from_table(
    console,
    prompt: str,
    columns: List[Dict],
    data: List[Dict],
    table_kwargs: Optional[Dict] = None,
    opt_out_message: Optional[str] = None,
    opt_out_response: Any = None,
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
    table_kwargs = table_kwargs or {}

    def build_table() -> Table:
        """
        Generate a table of options. The `current_idx` will be highlighted.
        """

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

        if opt_out_message:
            prefix = "  > " if current_idx == len(data) else " " * 4
            bottom_text = Text(prefix + opt_out_message)
            if current_idx == len(data):
                bottom_text.stylize("bold blue")
            return Group(table, bottom_text)

        return table

    with Live(build_table(), auto_refresh=False, console=console) as live:
        live.console.print(
            f"[bold][green]?[/] {prompt} [bright_blue][Use arrows to move; enter to"
            " select][/]"
        )
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
                if opt_out_message and current_idx >= len(data) + 1:
                    current_idx = 0
                elif not opt_out_message and current_idx >= len(data):
                    current_idx = 0
            elif key == readchar.key.CTRL_C:
                # gracefully exit with no message
                exit_with_error("")
            elif key == readchar.key.ENTER or key == readchar.key.CR:
                if current_idx >= len(data):
                    selected_row = opt_out_response
                else:
                    selected_row = data[current_idx]

            live.update(build_table(), refresh=True)

        return selected_row


# Interval schedule prompting utilities


class IntervalValuePrompt(PromptBase[timedelta]):
    response_type = timedelta
    validate_error_message = (
        "[prompt.invalid]Please enter a valid interval denoted in seconds"
    )

    def process_response(self, value: str) -> timedelta:
        try:
            int_value = int(value)
            if int_value <= 0:
                raise InvalidResponse("[prompt.invalid]Interval must be greater than 0")
            return timedelta(seconds=int_value)
        except ValueError:
            raise InvalidResponse(self.validate_error_message)


def prompt_interval_schedule(console):
    """
    Prompt the user for an interval in seconds.
    """
    interval = IntervalValuePrompt.ask(
        "[bold][green]?[/] Seconds between scheduled runs",
        console=console,
        default="3600",
    )
    return IntervalSchedule(interval=interval)


# Cron schedule prompting utilities


class CronStringPrompt(PromptBase[str]):
    response_type = str
    validate_error_message = "[prompt.invalid]Please enter a valid cron string"

    def process_response(self, value: str) -> str:
        try:
            CronSchedule.valid_cron_string(value)
            return value
        except ValueError:
            raise InvalidResponse(self.validate_error_message)


class CronTimezonePrompt(PromptBase[str]):
    response_type = str
    validate_error_message = "[prompt.invalid]Please enter a valid timezone."

    def process_response(self, value: str) -> str:
        try:
            CronSchedule.valid_timezone(value)
            return value
        except ValueError:
            raise InvalidResponse(self.validate_error_message)


def prompt_cron_schedule(console):
    """
    Prompt the user for a cron string and timezone.
    """
    cron = CronStringPrompt.ask(
        "[bold][green]?[/] Cron string",
        console=console,
        default="0 0 * * *",
    )
    timezone = CronTimezonePrompt.ask(
        "[bold][green]?[/] Timezone", console=console, default="UTC"
    )
    return CronSchedule(cron=cron, timezone=timezone)


# RRule schedule prompting utilities


class RRuleStringPrompt(PromptBase[str]):
    response_type = str
    validate_error_message = "[prompt.invalid]Please enter a valid RRule string"

    def process_response(self, value: str) -> str:
        try:
            RRuleSchedule.validate_rrule_str(value)
            return value
        except ValueError:
            raise InvalidResponse(self.validate_error_message)


class RRuleTimezonePrompt(PromptBase[str]):
    response_type = str
    validate_error_message = "[prompt.invalid]Please enter a valid timezone."

    def process_response(self, value: str) -> str:
        try:
            RRuleSchedule.valid_timezone(value)
            return value
        except ValueError:
            raise InvalidResponse(self.validate_error_message)


def prompt_rrule_schedule(console):
    """
    Prompts the user to enter an RRule string and timezone.
    """
    rrule = RRuleStringPrompt.ask(
        "[bold][green]?[/] RRule string",
        console=console,
        default="RRULE:FREQ=DAILY;INTERVAL=1",
    )
    timezone = CronTimezonePrompt.ask(
        "[bold][green]?[/] Timezone", console=console, default="UTC"
    )
    return RRuleSchedule(rrule=rrule, timezone=timezone)


# Schedule type prompting utilities


def prompt_schedule_type(console):
    """
    Prompts the user to select a schedule type from a list of options.
    """
    selection = prompt_select_from_table(
        console,
        "What type of schedule would you like to use?",
        [
            {"header": "Schedule Type", "key": "type"},
            {"header": "Description", "key": "description"},
        ],
        [
            {
                "type": "Interval",
                "description": (
                    "Allows you to set flow runs to be executed at fixed time"
                    " intervals."
                ),
            },
            {
                "type": "Cron",
                "description": (
                    "Allows you to define recurring flow runs based on a specified"
                    " pattern using cron syntax."
                ),
            },
            {
                "type": "RRule",
                "description": (
                    "Allows you to define recurring flow runs using RFC 2445 recurrence"
                    " rules."
                ),
            },
        ],
    )
    return selection["type"]


def prompt_schedule(console) -> SCHEDULE_TYPES:
    """
    Prompt the user for a schedule type. Once a schedule type is selected, prompt
    the user for the schedule details and return the schedule.
    """
    schedule_type = prompt_schedule_type(console)
    if schedule_type == "Cron":
        return prompt_cron_schedule(console)
    elif schedule_type == "Interval":
        return prompt_interval_schedule(console)
    elif schedule_type == "RRule":
        return prompt_rrule_schedule(console)
    else:
        raise Exception("Invalid schedule type")


@inject_client
async def prompt_select_work_pool(
    console: Console,
    prompt: str = "Which work pool would you like to deploy this flow to?",
    client: PrefectClient = None,
) -> str:
    work_pools = await client.read_work_pools()
    work_pool_options = [
        work_pool.dict()
        for work_pool in work_pools
        if work_pool.type != "prefect-agent"
    ]
    if not work_pool_options:
        work_pool = await prompt_create_work_pool(console, client=client)
        return work_pool.name
    else:
        selected_work_pool_row = prompt_select_from_table(
            console,
            prompt,
            [
                {"header": "Work Pool Name", "key": "name"},
                {"header": "Infrastructure Type", "key": "type"},
                {"header": "Description", "key": "description"},
            ],
            work_pool_options,
        )
        return selected_work_pool_row["name"]


@inject_client
async def prompt_create_work_pool(
    console: Console,
    client: PrefectClient = None,
):
    if not confirm(
        (
            "Looks like you don't have any work pools this flow can be deployed to."
            " Would you like to create one?"
        ),
        default=True,
        console=console,
    ):
        raise ValueError(
            "A work pool is required to deploy this flow. Please specify a work pool"
            " name via the '--pool' flag or in your prefect.yaml file."
        )
    async with get_collections_metadata_client() as collections_client:
        worker_metadata = await collections_client.read_worker_metadata()
    selected_worker_row = prompt_select_from_table(
        console,
        prompt="What infrastructure type would you like to use for your new work pool?",
        columns=[
            {"header": "Type", "key": "type"},
            {"header": "Description", "key": "description"},
        ],
        data=[
            worker
            for collection in worker_metadata.values()
            for worker in collection.values()
            if worker["type"] != "prefect-agent"
        ],
        table_kwargs={"show_lines": True},
    )
    work_pool_name = prompt("Work pool name")
    work_pool = await client.create_work_pool(
        WorkPoolCreate(name=work_pool_name, type=selected_worker_row["type"])
    )
    console.print(f"Your work pool {work_pool.name!r} has been created!", style="green")
    return work_pool

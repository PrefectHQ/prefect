"""
Utilities for prompting the user for input
"""
from datetime import timedelta
from getpass import GetPassWarning
import os
import shutil
import sys
from prefect.deployments.base import _search_for_flow_functions
from prefect.flows import load_flow_from_entrypoint
from prefect.infrastructure.container import DockerRegistry
from prefect.utilities.processutils import run_process
from rich.prompt import PromptBase, InvalidResponse
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

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

from prefect.utilities.slugify import slugify


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
        max_length = 250
        for item in data:
            rows.append(
                tuple(
                    (
                        value[:max_length] + "...\n"
                        if isinstance(value := item.get(column.get("key")), str)
                        and len(value) > max_length
                        else value
                    )
                    for column in columns
                )
            )

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
        instructions_message = (
            f"[bold][green]?[/] {prompt} [bright_blue][Use arrows to move; enter to"
            " select"
        )
        if opt_out_message:
            instructions_message += "; n to select none"
        instructions_message += "]"
        live.console.print(instructions_message)
        while selected_row is None:
            key = readchar.readkey()

            if key == readchar.key.UP:
                current_idx = current_idx - 1
                # wrap to bottom if at the top
                if opt_out_message and current_idx < 0:
                    current_idx = len(data)
                elif not opt_out_message and current_idx < 0:
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
                    return opt_out_response
                else:
                    selected_row = data[current_idx]
            elif key == "n" and opt_out_message:
                return opt_out_response

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


async def prompt_build_custom_docker_image(
    console: Console,
    deployment_config: dict,
):
    if not confirm(
        "Would you like to build a custom Docker image for this deployment?",
        console=console,
        default=False,
    ):
        return

    build_step = {
        "requires": "prefect-docker>=0.3.1",
        "id": "build-image",
    }

    if os.path.exists("Dockerfile"):
        if confirm(
            "Would you like to use the Dockerfile in the current directory?",
            console=console,
            default=True,
        ):
            build_step["dockerfile"] = "Dockerfile"
        else:
            if confirm(
                "A Dockerfile exists. You chose not to use it. A temporary Dockerfile"
                " will be automatically built during the deployment build step. If"
                " another file named 'Dockerfile' already exists at that time, the"
                " build step will fail. Would you like to rename your existing"
                " Dockerfile?"
            ):
                new_dockerfile_name = prompt(
                    "New Dockerfile name", default="Dockerfile.backup"
                )
                shutil.move("Dockerfile", new_dockerfile_name)
                build_step["dockerfile"] = "auto"
            else:
                # this will otherwise raise when build steps are run as the auto-build feature
                # executed in the build_docker_image step will create a temporary Dockerfile
                raise ValueError(
                    "A Dockerfile already exists. Please remove or rename the existing"
                    " one."
                )
    else:
        build_step["dockerfile"] = "auto"

    repo_name = prompt("Repository name (e.g. your Docker Hub username)").rstrip("/")
    image_name = prompt("Image name", default=deployment_config["name"])
    build_step["image_name"] = f"{repo_name}/{image_name}"
    build_step["tag"] = prompt("Image tag", default="latest")

    console.print(
        "Image"
        f" [bold][yellow]{build_step['image_name']}:{build_step['tag']}[/yellow][/bold]"
        " will be built."
    )

    return {"prefect_docker.deployments.steps.build_docker_image": build_step}


async def prompt_push_custom_docker_image(
    console: Console,
    deployment_config: dict,
    build_docker_image_step: dict,
):
    if not confirm(
        "Would you like to push this image to a remote registry?",
        console=console,
        default=False,
    ):
        return None, build_docker_image_step

    push_step = {
        "requires": "prefect-docker>=0.3.1",
        "image_name": "{{ build-image.image_name }}",
        "tag": "{{ build-image.tag }}",
    }

    registry_url = prompt("Registry URL", default="docker.io").rstrip("/")

    repo_and_image_name = build_docker_image_step[
        "prefect_docker.deployments.steps.build_docker_image"
    ]["image_name"]
    full_image_name = f"{registry_url}/{repo_and_image_name}"
    build_docker_image_step["prefect_docker.deployments.steps.build_docker_image"][
        "image_name"
    ] = full_image_name

    if confirm("Is this a private registry?", console=console):
        docker_credentials = {}
        docker_credentials["registry_url"] = registry_url

        if confirm(
            "Would you like use prefect-docker to manage Docker registry credentials?",
            console=console,
            default=False,
        ):
            try:
                import prefect_docker
            except ImportError:
                console.print("Installing prefect-docker...")
                await run_process(
                    [sys.executable, "-m", "pip", "install", "prefect-docker"],
                    stream_output=True,
                )
                import prefect_docker

            credentials_block = prefect_docker.DockerRegistryCredentials
            push_step["credentials"] = (
                "{{ prefect_docker.docker-registry-credentials.docker_registry_creds_name }}"
            )
        else:
            credentials_block = DockerRegistry
            push_step["credentials"] = (
                "{{ prefect.docker-registry.docker_registry_creds_name }}"
            )
        docker_registry_creds_name = f"deployment-{slugify(deployment_config['name'])}-{slugify(deployment_config['work_pool']['name'])}-registry-creds"
        create_new_block = False
        try:
            await credentials_block.load(docker_registry_creds_name)
            if not confirm(
                (
                    "Would you like to use the existing Docker registry credentials"
                    f" block {docker_registry_creds_name}?"
                ),
                console=console,
                default=True,
            ):
                create_new_block = True
        except ValueError:
            create_new_block = True

        if create_new_block:
            docker_credentials["username"] = prompt(
                "Docker registry username", console=console
            )
            try:
                docker_credentials["password"] = prompt(
                    "Docker registry password",
                    console=console,
                    password=True,
                )
            except GetPassWarning:
                docker_credentials["password"] = prompt(
                    "Docker registry password",
                    console=console,
                )

            new_creds_block = credentials_block(
                username=docker_credentials["username"],
                password=docker_credentials["password"],
                registry_url=docker_credentials["registry_url"],
            )
            await new_creds_block.save(name=docker_registry_creds_name, overwrite=True)

    return {
        "prefect_docker.deployments.steps.push_docker_image": push_step
    }, build_docker_image_step


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


class EntrypointPrompt(PromptBase[str]):
    response_type = str
    validate_error_message = "[prompt.invalid]Please enter a valid flow entrypoint."

    def process_response(self, value: str) -> str:
        try:
            value.rsplit(":", 1)
        except ValueError:
            raise InvalidResponse(self.validate_error_message)

        try:
            load_flow_from_entrypoint(value)
        except Exception:
            raise InvalidResponse(
                f"[prompt.invalid]Failed to load flow from entrypoint {value!r}."
                f" {self.validate_error_message}"
            )
        return value


async def prompt_entrypoint(console: Console) -> str:
    """
    Prompt the user for a flow entrypoint. Will search for flow functions in the
    current working directory and nested subdirectories to prompt the user to select
    from a list of discovered flows. If no flows are found, the user will be prompted
    to enter a flow entrypoint manually.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task_id = progress.add_task(
            description="Scanning for flows...",
            total=1,
        )
        discovered_flows = await _search_for_flow_functions()
        progress.update(task_id, completed=1)
    if not discovered_flows:
        return EntrypointPrompt.ask(
            (
                "[bold][green]?[/] Flow entrypoint (expected format"
                " path/to/file.py:function_name)"
            ),
            console=console,
        )
    selected_flow = prompt_select_from_table(
        console,
        prompt="Select a flow to deploy",
        columns=[
            {"header": "Flow Name", "key": "flow_name"},
            {"header": "Location", "key": "filepath"},
        ],
        data=discovered_flows,
        opt_out_message="Enter a flow entrypoint manually",
    )
    if selected_flow is None:
        return EntrypointPrompt.ask(
            (
                "[bold][green]?[/] Flow entrypoint (expected format"
                " path/to/file.py:function_name)"
            ),
            console=console,
        )
    return f"{selected_flow['filepath']}:{selected_flow['function_name']}"

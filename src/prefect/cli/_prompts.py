"""
Utilities for prompting the user for input
"""

from __future__ import annotations

import asyncio
import os
import shutil
from datetime import timedelta
from getpass import GetPassWarning
from typing import (
    TYPE_CHECKING,
    Any,
    Coroutine,
    Optional,
    TypeVar,
    Union,
    overload,
)

import anyio
import readchar
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, InvalidResponse, Prompt, PromptBase
from rich.table import Table

from prefect.cli._utilities import exit_with_error
from prefect.client.collections import get_collections_metadata_client
from prefect.client.schemas.actions import (
    BlockDocumentCreate,
    DeploymentScheduleCreate,
    WorkPoolCreate,
)
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
    is_valid_timezone,
)
from prefect.client.utilities import client_injector
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound
from prefect.flows import load_flow_from_entrypoint
from prefect.logging.loggers import get_logger
from prefect.utilities import urls
from prefect.utilities._ast import find_flow_functions_in_file
from prefect.utilities._git import get_git_remote_origin_url
from prefect.utilities.filesystem import filter_files
from prefect.utilities.processutils import get_sys_executable, run_process
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient

T = TypeVar("T", bound=RenderableType)

STORAGE_PROVIDER_TO_CREDS_BLOCK = {
    "s3": "aws-credentials",
    "gcs": "gcp-credentials",
    "azure_blob_storage": "azure-blob-storage-credentials",
}

REQUIRED_FIELDS_FOR_CREDS_BLOCK = {
    "aws-credentials": ["aws_access_key_id", "aws_secret_access_key"],
    "gcp-credentials": ["project", "service_account_file"],
    "azure-blob-storage-credentials": ["account_url", "connection_string"],
}


logger = get_logger(__name__)


async def search_for_flow_functions(
    directory: str = ".", exclude_patterns: list[str] | None = None
) -> list[dict[str, str]]:
    """
    Search for flow functions in the provided directory. If no directory is provided,
    the current working directory is used.

    Args:
        directory: The directory to search in
        exclude_patterns: List of patterns to exclude from the search, defaults to
            ["**/site-packages/**"]

    Returns:
        List[Dict]: the flow name, function name, and filepath of all flow functions found
    """
    path = anyio.Path(directory)
    exclude_patterns = exclude_patterns or ["**/site-packages/**"]
    coros: list[Coroutine[list[dict[str, str]], Any, Any]] = []

    try:
        for file in filter_files(
            root=str(path),
            ignore_patterns=["*", "!**/*.py", *exclude_patterns],
            include_dirs=False,
        ):
            coros.append(find_flow_functions_in_file(anyio.Path(str(path / file))))

    except (PermissionError, OSError) as e:
        logger.error(f"Error searching for flow functions: {e}")
        return []

    return [fn for file_fns in await asyncio.gather(*coros) for fn in file_fns]


def prompt(message: str, **kwargs: Any) -> str:
    """Utility to prompt the user for input with consistent styling"""
    return Prompt.ask(f"[bold][green]?[/] {message}[/]", **kwargs)


def confirm(message: str, **kwargs: Any) -> bool:
    """Utility to prompt the user for confirmation with consistent styling"""
    return Confirm.ask(f"[bold][green]?[/] {message}[/]", **kwargs)


@overload
def prompt_select_from_table(
    console: Console,
    prompt: str,
    columns: list[dict[str, str]],
    data: list[dict[str, T]],
    table_kwargs: dict[str, Any] | None = None,
    opt_out_message: None = None,
    opt_out_response: Any = None,
) -> dict[str, T]: ...


@overload
def prompt_select_from_table(
    console: Console,
    prompt: str,
    columns: list[dict[str, str]],
    data: list[dict[str, T]],
    table_kwargs: dict[str, Any] | None = None,
    opt_out_message: str = "",
    opt_out_response: Any = None,
) -> dict[str, T] | None: ...


def prompt_select_from_table(
    console: Console,
    prompt: str,
    columns: list[dict[str, str]],
    data: list[dict[str, T]],
    table_kwargs: dict[str, Any] | None = None,
    opt_out_message: str | None = None,
    opt_out_response: Any = None,
) -> dict[str, T] | None:
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
    visible_rows = min(10, console.height - 4)  # Adjust number of visible rows
    scroll_offset = 0
    total_options = len(data) + (1 if opt_out_message else 0)

    def build_table() -> Union[Table, Group]:
        nonlocal scroll_offset
        table = Table(**table_kwargs)
        table.add_column()
        for column in columns:
            table.add_column(column.get("header", ""))

        # Adjust scroll_offset if necessary
        if current_idx < scroll_offset:
            scroll_offset = current_idx
        elif current_idx >= scroll_offset + visible_rows:
            scroll_offset = current_idx - visible_rows + 1

        for i, item in enumerate(data[scroll_offset : scroll_offset + visible_rows]):
            row = [item.get(column.get("key", "")) for column in columns]
            if i + scroll_offset == current_idx:
                table.add_row(
                    "[bold][blue]>", *[f"[bold][blue]{cell}[/]" for cell in row]
                )
            else:
                table.add_row("  ", *row)

        if opt_out_message:
            opt_out_row = [""] * (len(columns) - 1) + [opt_out_message]
            if current_idx == len(data):
                table.add_row(
                    "[bold][blue]>", *[f"[bold][blue]{cell}[/]" for cell in opt_out_row]
                )
            else:
                table.add_row("  ", *opt_out_row)

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
                current_idx = (current_idx - 1) % total_options
            elif key == readchar.key.DOWN:
                current_idx = (current_idx + 1) % total_options
            elif key == readchar.key.CTRL_C:
                # gracefully exit with no message
                exit_with_error("")
            elif key == readchar.key.ENTER or key == readchar.key.CR:
                if current_idx == len(data):
                    return opt_out_response
                else:
                    selected_row = data[current_idx]
            elif key == "n" and opt_out_message:
                return opt_out_response

            live.update(build_table(), refresh=True)

        return selected_row


# Interval schedule prompting utilities
class IntervalValuePrompt(PromptBase[timedelta]):
    response_type: type[timedelta] = timedelta
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


def prompt_interval_schedule(console: Console) -> IntervalSchedule:
    """
    Prompt the user for an interval in seconds.
    """
    default_seconds = 3600
    default_duration = timedelta(seconds=default_seconds)

    # We show the default in the prompt message rather than enabling `show_default=True` here because `rich` displays timedeltas in hours
    # rather than seconds, which would confuse users since we ask them to enter the interval in seconds.
    interval = IntervalValuePrompt.ask(
        f"[bold][green]?[/] Seconds between scheduled runs ({default_seconds})",
        console=console,
        default=default_duration,
        show_default=False,
    )

    return IntervalSchedule(interval=interval)


# Cron schedule prompting utilities


class CronStringPrompt(PromptBase[str]):
    response_type: type[str] = str
    validate_error_message = "[prompt.invalid]Please enter a valid cron string"

    def process_response(self, value: str) -> str:
        try:
            CronSchedule.valid_cron_string(value)
            return value
        except ValueError:
            raise InvalidResponse(self.validate_error_message)


class CronTimezonePrompt(PromptBase[str]):
    response_type: type[str] = str
    validate_error_message = "[prompt.invalid]Please enter a valid timezone."

    def process_response(self, value: str) -> str:
        try:
            CronSchedule.valid_timezone(value)
            return value
        except ValueError:
            raise InvalidResponse(self.validate_error_message)


def prompt_cron_schedule(console: Console) -> CronSchedule:
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
    response_type: type[str] = str
    validate_error_message = "[prompt.invalid]Please enter a valid RRule string"

    def process_response(self, value: str) -> str:
        try:
            RRuleSchedule.validate_rrule_str(value)
            return value
        except ValueError:
            raise InvalidResponse(self.validate_error_message)


class RRuleTimezonePrompt(PromptBase[str]):
    response_type: type[str] = str
    validate_error_message = "[prompt.invalid]Please enter a valid timezone."

    def process_response(self, value: str) -> str:
        try:
            is_valid_timezone(value)
            return value
        except ValueError:
            raise InvalidResponse(self.validate_error_message)


def prompt_rrule_schedule(console: Console) -> RRuleSchedule:
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


def prompt_schedule_type(console: Console) -> str:
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


def prompt_schedules(console: Console) -> list[DeploymentScheduleCreate]:
    """
    Prompt the user to configure schedules for a deployment.
    """
    schedules: list[DeploymentScheduleCreate] = []

    if confirm(
        "Would you like to configure schedules for this deployment?", default=True
    ):
        add_schedule = True
        while add_schedule:
            schedule_type = prompt_schedule_type(console)
            if schedule_type == "Cron":
                schedule = prompt_cron_schedule(console)
            elif schedule_type == "Interval":
                schedule = prompt_interval_schedule(console)
            elif schedule_type == "RRule":
                schedule = prompt_rrule_schedule(console)
            else:
                raise Exception("Invalid schedule type")

            is_schedule_active = confirm(
                "Would you like to activate this schedule?", default=True
            )

            schedules.append(
                DeploymentScheduleCreate(schedule=schedule, active=is_schedule_active)
            )

            add_schedule = confirm(
                "Would you like to add another schedule?", default=False
            )

    return schedules


@client_injector
async def prompt_select_work_pool(
    client: "PrefectClient",
    console: Console,
    prompt: str = "Which work pool would you like to deploy this flow to?",
) -> str:
    work_pools = await client.read_work_pools()
    work_pool_options = [
        work_pool.model_dump()
        for work_pool in work_pools
        if work_pool.type != "prefect-agent"
    ]
    if not work_pool_options:
        work_pool = await prompt_create_work_pool(console)
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
    deployment_config: dict[str, Any],
) -> dict[str, Any] | None:
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
    deployment_config: dict[str, Any],
    build_docker_image_step: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
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
                    [get_sys_executable(), "-m", "pip", "install", "prefect[docker]"],
                    stream_output=True,
                )
                import prefect_docker

            credentials_block = prefect_docker.DockerRegistryCredentials
            push_step["credentials"] = (
                "{{ prefect_docker.docker-registry-credentials.docker_registry_creds_name }}"
            )
            docker_registry_creds_name = f"deployment-{slugify(deployment_config['name'])}-{slugify(deployment_config['work_pool']['name'])}-registry-creds"
            create_new_block = False
            try:
                await credentials_block.aload(docker_registry_creds_name)
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
                coro = new_creds_block.save(
                    name=docker_registry_creds_name, overwrite=True
                )
                if TYPE_CHECKING:
                    assert asyncio.iscoroutine(coro)
                await coro
    return {
        "prefect_docker.deployments.steps.push_docker_image": push_step
    }, build_docker_image_step


@client_injector
async def prompt_create_work_pool(
    client: "PrefectClient",
    console: Console,
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
    response_type: type[str] = str
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
        discovered_flows = await search_for_flow_functions()
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


@client_injector
async def prompt_select_remote_flow_storage(
    client: "PrefectClient", console: Console
) -> Optional[str]:
    valid_slugs_for_context: set[str] = set()

    for (
        storage_provider,
        creds_block_type_slug,
    ) in STORAGE_PROVIDER_TO_CREDS_BLOCK.items():
        try:
            # only return storage options for which the user has a credentials
            # block type
            await client.read_block_type_by_slug(creds_block_type_slug)
            valid_slugs_for_context.add(storage_provider)
        except ObjectNotFound:
            pass

    if get_git_remote_origin_url():
        valid_slugs_for_context.add("git")

    flow_storage_options = [
        {
            "type": "Git Repo",
            "slug": "git",
            "description": "Use a Git repository [bold](recommended).",
        },
        {
            "type": "S3",
            "slug": "s3",
            "description": "Use an AWS S3 bucket.",
        },
        {
            "type": "GCS",
            "slug": "gcs",
            "description": "Use a Google Cloud Storage bucket.",
        },
        {
            "type": "Azure Blob Storage",
            "slug": "azure_blob_storage",
            "description": "Use an Azure Blob Storage bucket.",
        },
    ]

    valid_storage_options_for_context = [
        row for row in flow_storage_options if row["slug"] in valid_slugs_for_context
    ]

    selected_flow_storage_row = prompt_select_from_table(
        console,
        prompt="Please select a remote code storage option.",
        columns=[
            {"header": "Storage Type", "key": "type"},
            {"header": "Description", "key": "description"},
        ],
        data=valid_storage_options_for_context,
    )

    return selected_flow_storage_row["slug"]


@client_injector
async def prompt_select_blob_storage_credentials(
    client: "PrefectClient",
    console: Console,
    storage_provider: str,
) -> str:
    """
    Prompt the user for blob storage credentials.

    Returns a jinja template string that references a credentials block.
    """

    storage_provider_slug = storage_provider.replace("_", "-")
    pretty_storage_provider = storage_provider.replace("_", " ").upper()

    creds_block_type_slug = STORAGE_PROVIDER_TO_CREDS_BLOCK[storage_provider]
    pretty_creds_block_type = creds_block_type_slug.replace("-", " ").title()

    existing_credentials_blocks = await client.read_block_documents_by_type(
        block_type_slug=creds_block_type_slug
    )

    if existing_credentials_blocks:
        selected_credentials_block = prompt_select_from_table(
            console,
            prompt=(
                f"Select from your existing {pretty_creds_block_type} credential blocks"
            ),
            columns=[
                {
                    "header": f"{pretty_storage_provider} Credentials Blocks",
                    "key": "name",
                }
            ],
            data=[
                {"name": block.name}
                for block in existing_credentials_blocks
                if block.name is not None
            ],
            opt_out_message="Create a new credentials block",
        )

        if selected_credentials_block and (
            selected_block := selected_credentials_block.get("name")
        ):
            return f"{{{{ prefect.blocks.{creds_block_type_slug}.{selected_block} }}}}"

    credentials_block_type = await client.read_block_type_by_slug(creds_block_type_slug)

    credentials_block_schema = await client.get_most_recent_block_schema_for_block_type(
        block_type_id=credentials_block_type.id
    )
    if credentials_block_schema is None:
        raise ValueError(f"No schema found for {pretty_creds_block_type} block")

    console.print(
        f"\nProvide details on your new {pretty_storage_provider} credentials:"
    )

    hydrated_fields = {
        field_name: prompt(f"{field_name} [yellow]({props.get('type')})[/]")
        for field_name, props in credentials_block_schema.fields.get(
            "properties", {}
        ).items()
        if field_name in REQUIRED_FIELDS_FOR_CREDS_BLOCK[creds_block_type_slug]
    }

    console.print(f"[blue]\n{pretty_storage_provider} credentials specified![/]\n")

    while True:
        credentials_block_name = prompt(
            "Give a name to your new credentials block",
            default=f"{storage_provider_slug}-storage-credentials",
        )

        try:
            new_block_document = await client.create_block_document(
                block_document=BlockDocumentCreate(
                    name=credentials_block_name,
                    data=hydrated_fields,
                    block_schema_id=credentials_block_schema.id,
                    block_type_id=credentials_block_type.id,
                )
            )
            break
        except ObjectAlreadyExists:
            console.print(
                f"A {pretty_creds_block_type!r} block named"
                f" {credentials_block_name!r} already exists. Please choose another"
                " name"
            )

    url = urls.url_for(new_block_document)
    if url:
        console.print(
            f"\nView/Edit your new credentials block in the UI:\n[blue]{url}[/]\n",
            soft_wrap=True,
        )
    return f"{{{{ prefect.blocks.{creds_block_type_slug}.{new_block_document.name} }}}}"

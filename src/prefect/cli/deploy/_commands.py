"""
Deploy command — native cyclopts implementation.

Reuses all business logic from prefect.cli.deploy.* modules, threading
`console` and `is_interactive` as parameters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import cyclopts
from rich.prompt import Prompt
from rich.table import Table

import prefect
import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    with_cli_exception_handling,
)
from prefect.client.schemas.objects import ConcurrencyLimitConfig

deploy_app: cyclopts.App = cyclopts.App(
    name="deploy",
    help="Create and manage deployments.",
    version_flags=[],
    help_flags=["--help"],
)


@deploy_app.command(name="init")
@with_cli_exception_handling
async def init(
    *,
    name: Annotated[
        str | None,
        cyclopts.Parameter("--name", help="The name to give the project."),
    ] = None,
    recipe: Annotated[
        str | None,
        cyclopts.Parameter("--recipe", help="The recipe to use for the project."),
    ] = None,
    fields: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--field",
            alias="-f",
            help=(
                "One or more fields to pass to the recipe (e.g., image_name) in the"
                " format of key=value."
            ),
        ),
    ] = None,
):
    """Initialize a Prefect project."""
    import yaml

    from prefect.deployments import initialize_project

    inputs: dict[str, Any] = {}
    fields = fields or []
    recipe_paths = prefect.__module_path__ / "deployments" / "recipes"

    for field in fields:
        key, value = field.split("=")
        inputs[key] = value

    from prefect.cli._prompts import prompt_select_from_table

    if not recipe and _cli.is_interactive():
        recipes: list[dict[str, Any]] = []
        for r in recipe_paths.iterdir():
            if r.is_dir() and (r / "prefect.yaml").exists():
                with open(r / "prefect.yaml") as f:
                    recipe_data = yaml.safe_load(f)
                    recipe_name = r.name
                    recipe_description = recipe_data.get(
                        "description", "(no description available)"
                    )
                    recipes.append(
                        {"name": recipe_name, "description": recipe_description}
                    )

        selected_recipe = prompt_select_from_table(
            _cli.console,
            "Would you like to initialize your deployment configuration with a recipe?",
            columns=[
                {"header": "Name", "key": "name"},
                {"header": "Description", "key": "description"},
            ],
            data=recipes,
            opt_out_message="No, I'll use the default deployment configuration.",
            opt_out_response={},
        )
        if selected_recipe != {}:
            recipe = selected_recipe["name"]

    if recipe and (recipe_paths / recipe / "prefect.yaml").exists():
        with open(recipe_paths / recipe / "prefect.yaml") as f:
            recipe_inputs = yaml.safe_load(f).get("required_inputs") or {}
        if recipe_inputs:
            if set(recipe_inputs.keys()) < set(inputs.keys()):
                _cli.console.print(
                    (
                        f"Warning: extra fields provided for {recipe!r} recipe:"
                        f" '{', '.join(set(inputs.keys()) - set(recipe_inputs.keys()))}'"
                    ),
                    style="red",
                )
            elif set(recipe_inputs.keys()) > set(inputs.keys()):
                table = Table(
                    title=f"[red]Required inputs for {recipe!r} recipe[/red]",
                )
                table.add_column("Field Name", style="green", no_wrap=True)
                table.add_column(
                    "Description", justify="left", style="white", no_wrap=False
                )
                for field_name, description in recipe_inputs.items():
                    if field_name not in inputs:
                        table.add_row(field_name, description)
                _cli.console.print(table)
                for key, description in recipe_inputs.items():
                    if key not in inputs:
                        inputs[key] = Prompt.ask(key, console=_cli.console)
            _cli.console.print("-" * 15)

    try:
        files = [
            f"[green]{fname}[/green]"
            for fname in initialize_project(name=name, recipe=recipe, inputs=inputs)
        ]
    except ValueError as exc:
        if "Unknown recipe" in str(exc):
            exit_with_error(
                f"Unknown recipe {recipe!r} provided - run"
                " [yellow]`prefect init`[/yellow] to see all available recipes."
            )
        else:
            raise

    files_str = "\n".join(files)
    empty_msg = (
        f"Created project in [green]{Path('.').resolve()}[/green];"
        " no new files created."
    )
    file_msg = (
        f"Created project in [green]{Path('.').resolve()}[/green]"
        f" with the following new files:\n{files_str}"
    )
    _cli.console.print(file_msg if files_str else empty_msg)


@deploy_app.default
@with_cli_exception_handling
async def deploy(
    entrypoint: Annotated[
        str | None,
        cyclopts.Parameter(
            show=False,
            help=(
                "The path to a flow entrypoint within a project, in the form of"
                " `./path/to/file.py:flow_func_name`"
            ),
        ),
    ] = None,
    *,
    names: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--name",
            alias="-n",
            help=(
                "The name to give the deployment. Can be a pattern. Examples:"
                " 'my-deployment', 'my-flow/my-deployment', 'my-deployment-*',"
                " '*-flow-name/deployment*'"
            ),
        ),
    ] = None,
    description: Annotated[
        str | None,
        cyclopts.Parameter(
            "--description",
            alias="-d",
            help=(
                "The description to give the deployment. If not provided, the"
                " description will be populated from the flow's description."
            ),
        ),
    ] = None,
    version_type: Annotated[
        str | None,
        cyclopts.Parameter(
            "--version-type",
            help="The type of version to use for this deployment.",
        ),
    ] = None,
    version: Annotated[
        str | None,
        cyclopts.Parameter("--version", help="A version to give the deployment."),
    ] = None,
    tags: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--tag",
            alias="-t",
            help=(
                "One or more optional tags to apply to the deployment. Note: tags are"
                " used only for organizational purposes. For delegating work to"
                " workers, use the --work-queue flag."
            ),
        ),
    ] = None,
    concurrency_limit: Annotated[
        int | None,
        cyclopts.Parameter(
            "--concurrency-limit",
            help="The maximum number of concurrent runs for this deployment.",
        ),
    ] = None,
    concurrency_limit_collision_strategy: Annotated[
        str | None,
        cyclopts.Parameter(
            "--collision-strategy",
            help=(
                "Configure the behavior for runs once the concurrency limit is"
                " reached. Falls back to `ENQUEUE` if unset."
            ),
        ),
    ] = None,
    work_pool_name: Annotated[
        str | None,
        cyclopts.Parameter(
            "--pool",
            alias="-p",
            help="The work pool that will handle this deployment's runs.",
        ),
    ] = None,
    work_queue_name: Annotated[
        str | None,
        cyclopts.Parameter(
            "--work-queue",
            alias="-q",
            help=(
                "The work queue that will handle this deployment's runs. It will be"
                " created if it doesn't already exist. Defaults to `None`."
            ),
        ),
    ] = None,
    job_variables: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--job-variable",
            json_list=False,
            help=(
                "One or more job variable overrides for the work pool provided in the"
                " format of key=value string or a JSON object"
            ),
        ),
    ] = None,
    cron: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--cron",
            help=(
                "A cron string that will be used to set a CronSchedule on the"
                " deployment."
            ),
        ),
    ] = None,
    interval: Annotated[
        list[int] | None,
        cyclopts.Parameter(
            "--interval",
            help=(
                "An integer specifying an interval (in seconds) that will be used to"
                " set an IntervalSchedule on the deployment."
            ),
        ),
    ] = None,
    interval_anchor: Annotated[
        str | None,
        cyclopts.Parameter(
            "--anchor-date",
            help="The anchor date for all interval schedules",
        ),
    ] = None,
    rrule: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--rrule",
            help=(
                "An RRule that will be used to set an RRuleSchedule on the deployment."
            ),
        ),
    ] = None,
    timezone: Annotated[
        str | None,
        cyclopts.Parameter(
            "--timezone",
            help="Deployment schedule timezone string e.g. 'America/New_York'",
        ),
    ] = None,
    trigger: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--trigger",
            json_list=False,
            help=(
                "Specifies a trigger for the deployment. The value can be a json"
                " string or path to `.yaml`/`.json` file. This flag can be used"
                " multiple times."
            ),
        ),
    ] = None,
    param: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--param",
            help=(
                "An optional parameter override, values are parsed as JSON strings"
                " e.g. --param question=ultimate --param answer=42"
            ),
        ),
    ] = None,
    params: Annotated[
        str | None,
        cyclopts.Parameter(
            "--params",
            help=(
                "An optional parameter override in a JSON string format e.g."
                ' --params=\'{"question": "ultimate", "answer": 42}\''
            ),
        ),
    ] = None,
    enforce_parameter_schema: Annotated[
        bool,
        cyclopts.Parameter(
            "--enforce-parameter-schema",
            help=(
                "Whether to enforce the parameter schema on this deployment. If set to"
                " True, any parameters passed to this deployment must match the"
                " signature of the flow."
            ),
        ),
    ] = True,
    deploy_all: Annotated[
        bool,
        cyclopts.Parameter(
            "--all",
            help=(
                "Deploy all flows in the project. If a flow name or entrypoint is also"
                " provided, this flag will be ignored."
            ),
        ),
    ] = False,
    prefect_file: Annotated[
        Path,
        cyclopts.Parameter(
            "--prefect-file",
            help="Specify a custom path to a prefect.yaml file",
        ),
    ] = Path("prefect.yaml"),
    sla: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--sla",
            json_list=False,
            help=(
                "Experimental: One or more SLA configurations for the deployment. May"
                " be removed or modified at any time. Currently only supported on"
                " Prefect Cloud."
            ),
        ),
    ] = None,
):
    """Create and update deployments."""
    from prefect.cli.deploy._config import (
        _load_deploy_configs_and_actions,
        _parse_name_from_pattern,
        _pick_deploy_configs,
    )
    from prefect.cli.deploy._core import _run_multi_deploy, _run_single_deploy
    from prefect.settings import get_current_settings

    # Resolve default work pool from settings (typer uses a lambda callback).
    if work_pool_name is None:
        work_pool_name = get_current_settings().deployments.default_work_pool_name

    if job_variables is None:
        job_variables = list()

    concurrency_limit_config = (
        None
        if concurrency_limit is None
        else (
            concurrency_limit
            if concurrency_limit_collision_strategy is None
            else ConcurrencyLimitConfig(
                limit=concurrency_limit,
                collision_strategy=concurrency_limit_collision_strategy,
            ).model_dump()
        )
    )

    options: dict[str, Any] = {
        "entrypoint": entrypoint,
        "description": description,
        "version_type": version_type,
        "version": version,
        "tags": tags,
        "concurrency_limit": concurrency_limit_config,
        "work_pool_name": work_pool_name,
        "work_queue_name": work_queue_name,
        "variables": job_variables,
        "cron": cron,
        "interval": interval,
        "anchor_date": interval_anchor,
        "rrule": rrule,
        "timezone": timezone,
        "triggers": trigger,
        "param": param,
        "params": params,
        "sla": sla,
    }

    try:
        all_deploy_configs, actions = _load_deploy_configs_and_actions(
            prefect_file=prefect_file, console=_cli.console
        )
        parsed_names: list[str] = []
        for name in names or []:
            if "*" in name:
                parsed_names.extend(_parse_name_from_pattern(all_deploy_configs, name))
            else:
                parsed_names.append(name)
        deploy_configs = _pick_deploy_configs(
            all_deploy_configs,
            parsed_names,
            deploy_all,
            console=_cli.console,
            is_interactive=_cli.is_interactive,
        )

        if len(deploy_configs) > 1:
            if any(options.values()):
                _cli.console.print(
                    (
                        "You have passed options to the deploy command, but you are"
                        " creating or updating multiple deployments. These options"
                        " will be ignored."
                    ),
                    style="yellow",
                )
            await _run_multi_deploy(
                deploy_configs=deploy_configs,
                actions=actions,
                deploy_all=deploy_all,
                prefect_file=prefect_file,
                console=_cli.console,
                is_interactive=_cli.is_interactive,
            )
        else:
            deploy_config = deploy_configs[0] if deploy_configs else {}
            options["names"] = [
                name.split("/", 1)[-1] if "/" in name else name for name in parsed_names
            ]
            if not enforce_parameter_schema:
                options["enforce_parameter_schema"] = False
            await _run_single_deploy(
                deploy_config=deploy_config,
                actions=actions,
                options=options,
                prefect_file=prefect_file,
                console=_cli.console,
                is_interactive=_cli.is_interactive,
            )
    except ValueError as exc:
        exit_with_error(str(exc))

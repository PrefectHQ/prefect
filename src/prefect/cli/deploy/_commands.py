from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

import typer
import yaml
from rich.table import Table

import prefect
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app, is_interactive
from prefect.client.schemas.objects import ConcurrencyLimitConfig
from prefect.deployments import initialize_project
from prefect.settings import get_current_settings

from ._config import (
    _load_deploy_configs_and_actions,
    _parse_name_from_pattern,
    _pick_deploy_configs,
)
from ._core import _run_multi_deploy, _run_single_deploy


@app.command()
async def init(
    name: Optional[str] = None,
    recipe: Optional[str] = None,
    fields: Optional[list[str]] = typer.Option(
        None,
        "-f",
        "--field",
        help=(
            "One or more fields to pass to the recipe (e.g., image_name) in the format"
            " of key=value."
        ),
    ),
):
    inputs: dict[str, Any] = {}
    fields = fields or []
    recipe_paths = prefect.__module_path__ / "deployments" / "recipes"

    for field in fields:
        key, value = field.split("=")
        inputs[key] = value

    from prefect.cli._prompts import prompt_select_from_table

    if not recipe and is_interactive():
        recipe_paths = prefect.__module_path__ / "deployments" / "recipes"
        recipes: list[dict[str, Any]] = []
        for r in recipe_paths.iterdir():
            if r.is_dir() and (r / "prefect.yaml").exists():
                with open(r / "prefect.yaml") as f:
                    recipe_data = yaml.safe_load(f)
                    recipe_name = r.name
                    recipe_description = recipe_data.get(
                        "description", "(no description available)"
                    )
                    recipe_dict = {
                        "name": recipe_name,
                        "description": recipe_description,
                    }
                    recipes.append(recipe_dict)

        selected_recipe = prompt_select_from_table(
            app.console,
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
                app.console.print(
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
                for field, description in recipe_inputs.items():
                    if field not in inputs:
                        table.add_row(field, description)
                app.console.print(table)
                for key, description in recipe_inputs.items():
                    if key not in inputs:
                        inputs[key] = typer.prompt(key)
            app.console.print("-" * 15)

    try:
        files = [
            f"[green]{fname}[/green]"
            for fname in initialize_project(name=name, recipe=recipe, inputs=inputs)
        ]
    except ValueError as exc:
        if "Unknown recipe" in str(exc):
            exit_with_error(
                f"Unknown recipe {recipe!r} provided - run [yellow]`prefect init`[/yellow] to see all available recipes."
            )
        else:
            raise

    files = "\n".join(files)
    empty_msg = f"Created project in [green]{Path('.').resolve()}[/green]; no new files created."
    file_msg = f"Created project in [green]{Path('.').resolve()}[/green] with the following new files:\n{files}"
    app.console.print(file_msg if files else empty_msg)


@app.command()
async def deploy(
    entrypoint: str = typer.Argument(
        None,
        help=(
            "The path to a flow entrypoint within a project, in the form of"
            " `./path/to/file.py:flow_func_name`"
        ),
    ),
    names: List[str] = typer.Option(
        None,
        "--name",
        "-n",
        help=(
            "The name to give the deployment. Can be a pattern. Examples:"
            " 'my-deployment', 'my-flow/my-deployment', 'my-deployment-*',"
            " '*-flow-name/deployment*'"
        ),
    ),
    description: str = typer.Option(
        None,
        "--description",
        "-d",
        help=(
            "The description to give the deployment. If not provided, the description will be populated from the flow's description."
        ),
    ),
    version_type: str = typer.Option(
        None, "--version-type", help="The type of version to use for this deployment."
    ),
    version: str = typer.Option(
        None, "--version", help="A version to give the deployment."
    ),
    tags: List[str] = typer.Option(
        None,
        "-t",
        "--tag",
        help=(
            "One or more optional tags to apply to the deployment. Note: tags are used only for organizational purposes. For delegating work to workers, use the --work-queue flag."
        ),
    ),
    concurrency_limit: int = typer.Option(
        None,
        "-cl",
        "--concurrency-limit",
        help=("The maximum number of concurrent runs for this deployment."),
    ),
    concurrency_limit_collision_strategy: str = typer.Option(
        None,
        "--collision-strategy",
        help="Configure the behavior for runs once the concurrency limit is reached. Falls back to `ENQUEUE` if unset.",
    ),
    work_pool_name: str = typer.Option(
        lambda: get_current_settings().deployments.default_work_pool_name,
        "-p",
        "--pool",
        help="The work pool that will handle this deployment's runs.",
        show_default="from PREFECT_DEFAULT_WORK_POOL_NAME",
    ),
    work_queue_name: str = typer.Option(
        None,
        "-q",
        "--work-queue",
        help=(
            "The work queue that will handle this deployment's runs. It will be created if it doesn't already exist. Defaults to `None`."
        ),
    ),
    job_variables: List[str] = typer.Option(
        None,
        "-jv",
        "--job-variable",
        help=(
            "One or more job variable overrides for the work pool provided in the format of key=value string or a JSON object"
        ),
    ),
    cron: List[str] = typer.Option(
        None,
        "--cron",
        help="A cron string that will be used to set a CronSchedule on the deployment.",
    ),
    interval: List[int] = typer.Option(
        None,
        "--interval",
        help=(
            "An integer specifying an interval (in seconds) that will be used to set an IntervalSchedule on the deployment."
        ),
    ),
    interval_anchor: Optional[str] = typer.Option(
        None, "--anchor-date", help="The anchor date for all interval schedules"
    ),
    rrule: List[str] = typer.Option(
        None,
        "--rrule",
        help="An RRule that will be used to set an RRuleSchedule on the deployment.",
    ),
    timezone: str = typer.Option(
        None,
        "--timezone",
        help="Deployment schedule timezone string e.g. 'America/New_York'",
    ),
    trigger: List[str] = typer.Option(
        None,
        "--trigger",
        help=(
            "Specifies a trigger for the deployment. The value can be a json string or path to `.yaml`/`.json` file. This flag can be used multiple times."
        ),
    ),
    param: List[str] = typer.Option(
        None,
        "--param",
        help=(
            "An optional parameter override, values are parsed as JSON strings e.g. --param question=ultimate --param answer=42"
        ),
    ),
    params: str = typer.Option(
        None,
        "--params",
        help=(
            "An optional parameter override in a JSON string format e.g. --params='{"
            "question"
            ": "
            "ultimate"
            ", "
            "answer"
            ": 42}'"
        ),
    ),
    enforce_parameter_schema: bool = typer.Option(
        True,
        help=(
            "Whether to enforce the parameter schema on this deployment. If set to True, any parameters passed to this deployment must match the signature of the flow."
        ),
    ),
    deploy_all: bool = typer.Option(
        False,
        "--all",
        help=(
            "Deploy all flows in the project. If a flow name or entrypoint is also provided, this flag will be ignored."
        ),
    ),
    prefect_file: Path = typer.Option(
        Path("prefect.yaml"),
        "--prefect-file",
        help="Specify a custom path to a prefect.yaml file",
    ),
    sla: List[str] = typer.Option(
        None,
        "--sla",
        help="Experimental: One or more SLA configurations for the deployment. May be removed or modified at any time. Currently only supported on Prefect Cloud.",
    ),
):
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
            prefect_file=prefect_file
        )
        parsed_names: list[str] = []
        for name in names or []:
            if "*" in name:
                parsed_names.extend(_parse_name_from_pattern(all_deploy_configs, name))
            else:
                parsed_names.append(name)
        deploy_configs = _pick_deploy_configs(
            all_deploy_configs, parsed_names, deploy_all
        )

        if len(deploy_configs) > 1:
            if any(options.values()):
                app.console.print(
                    (
                        "You have passed options to the deploy command, but you are creating or updating multiple deployments. These options will be ignored."
                    ),
                    style="yellow",
                )
            await _run_multi_deploy(
                deploy_configs=deploy_configs,
                actions=actions,
                deploy_all=deploy_all,
                prefect_file=prefect_file,
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
            )
    except ValueError as exc:
        exit_with_error(str(exc))

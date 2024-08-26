"""Module containing implementation for deploying flows."""

import json
import os
import re
from copy import deepcopy
from datetime import timedelta
from getpass import GetPassWarning
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import pydantic
import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from yaml.error import YAMLError

import prefect
from prefect._internal.compatibility.deprecated import (
    generate_deprecation_message,
)
from prefect.blocks.system import Secret
from prefect.cli._prompts import (
    confirm,
    prompt,
    prompt_build_custom_docker_image,
    prompt_entrypoint,
    prompt_push_custom_docker_image,
    prompt_schedules,
    prompt_select_blob_storage_credentials,
    prompt_select_from_table,
    prompt_select_remote_flow_storage,
    prompt_select_work_pool,
)
from prefect.cli._types import SettingsOption
from prefect.cli._utilities import (
    exit_with_error,
)
from prefect.cli.root import app, is_interactive
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.client.utilities import inject_client
from prefect.deployments import initialize_project
from prefect.deployments.base import (
    _format_deployment_for_saving_to_prefect_file,
    _get_git_branch,
    _get_git_remote_origin_url,
    _save_deployment_to_prefect_file,
)
from prefect.deployments.steps.core import run_steps
from prefect.events import DeploymentTriggerTypes, TriggerTypes
from prefect.exceptions import ObjectNotFound, PrefectHTTPStatusError
from prefect.flows import load_flow_from_entrypoint
from prefect.settings import (
    PREFECT_DEFAULT_WORK_POOL_NAME,
    PREFECT_UI_URL,
)
from prefect.utilities.annotations import NotSet
from prefect.utilities.callables import (
    parameter_schema,
)
from prefect.utilities.collections import get_from_dict
from prefect.utilities.slugify import slugify
from prefect.utilities.templating import (
    apply_values,
    resolve_block_document_references,
    resolve_variables,
)

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


@app.command()
async def init(
    name: Optional[str] = None,
    recipe: Optional[str] = None,
    fields: Optional[List[str]] = typer.Option(
        None,
        "-f",
        "--field",
        help=(
            "One or more fields to pass to the recipe (e.g., image_name) in the format"
            " of key=value."
        ),
    ),
):
    """
    Initialize a new deployment configuration recipe.
    """
    inputs = {}
    fields = fields or []
    recipe_paths = prefect.__module_path__ / "deployments" / "recipes"

    for field in fields:
        key, value = field.split("=")
        inputs[key] = value

    if not recipe and is_interactive():
        recipe_paths = prefect.__module_path__ / "deployments" / "recipes"
        recipes = []

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
                # message to user about extra fields
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
                f"Unknown recipe {recipe!r} provided - run [yellow]`prefect init"
                "`[/yellow] to see all available recipes."
            )
        else:
            raise

    files = "\n".join(files)
    empty_msg = (
        f"Created project in [green]{Path('.').resolve()}[/green]; no new files"
        " created."
    )
    file_msg = (
        f"Created project in [green]{Path('.').resolve()}[/green] with the following"
        f" new files:\n{files}"
    )
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
            "The description to give the deployment. If not provided, the description"
            " will be populated from the flow's description."
        ),
    ),
    version: str = typer.Option(
        None, "--version", help="A version to give the deployment."
    ),
    tags: List[str] = typer.Option(
        None,
        "-t",
        "--tag",
        help=(
            "One or more optional tags to apply to the deployment. Note: tags are used"
            " only for organizational purposes. For delegating work to agents, use the"
            " --work-queue flag."
        ),
    ),
    concurrency_limit: int = typer.Option(
        None,
        "-cl",
        "--concurrency-limit",
        help=("The maximum number of concurrent runs for this deployment."),
    ),
    work_pool_name: str = SettingsOption(
        PREFECT_DEFAULT_WORK_POOL_NAME,
        "-p",
        "--pool",
        help="The work pool that will handle this deployment's runs.",
    ),
    work_queue_name: str = typer.Option(
        None,
        "-q",
        "--work-queue",
        help=(
            "The work queue that will handle this deployment's runs. "
            "It will be created if it doesn't already exist. Defaults to `None`."
        ),
    ),
    variables: List[str] = typer.Option(
        None,
        "-v",
        "--variable",
        help=("DEPRECATED: Please use --jv/--job-variable for similar functionality "),
    ),
    job_variables: List[str] = typer.Option(
        None,
        "-jv",
        "--job-variable",
        help=(
            "One or more job variable overrides for the work pool provided in the"
            " format of key=value string or a JSON object"
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
            "An integer specifying an interval (in seconds) that will be used to set an"
            " IntervalSchedule on the deployment."
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
            "Specifies a trigger for the deployment. The value can be a"
            " json string or path to `.yaml`/`.json` file. This flag can be used"
            " multiple times."
        ),
    ),
    param: List[str] = typer.Option(
        None,
        "--param",
        help=(
            "An optional parameter override, values are parsed as JSON strings e.g."
            " --param question=ultimate --param answer=42"
        ),
    ),
    params: str = typer.Option(
        None,
        "--params",
        help=(
            "An optional parameter override in a JSON string format e.g."
            ' --params=\'{"question": "ultimate", "answer": 42}\''
        ),
    ),
    enforce_parameter_schema: bool = typer.Option(
        True,
        "--enforce-parameter-schema",
        help=(
            "Whether to enforce the parameter schema on this deployment. If set to"
            " True, any parameters passed to this deployment must match the signature"
            " of the flow."
        ),
    ),
    deploy_all: bool = typer.Option(
        False,
        "--all",
        help=(
            "Deploy all flows in the project. If a flow name or entrypoint is also"
            " provided, this flag will be ignored."
        ),
    ),
    prefect_file: Path = typer.Option(
        Path("prefect.yaml"),
        "--prefect-file",
        help="Specify a custom path to a prefect.yaml file",
    ),
):
    """
    Create a deployment to deploy a flow from this project.

    Should be run from a project root directory.
    """

    if variables is not None:
        app.console.print(
            generate_deprecation_message(
                name="The `--variable` flag",
                start_date="Mar 2024",
                help=(
                    "Please use the `--job-variable foo=bar` argument instead: `prefect"
                    " deploy --job-variable`."
                ),
            ),
            style="yellow",
        )

    if variables is None:
        variables = list()
    if job_variables is None:
        job_variables = list()
    job_variables.extend(variables)

    options = {
        "entrypoint": entrypoint,
        "description": description,
        "version": version,
        "tags": tags,
        "concurrency_limit": concurrency_limit,
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
    }
    try:
        deploy_configs, actions = _load_deploy_configs_and_actions(
            prefect_file=prefect_file,
        )
        parsed_names = []
        for name in names or []:
            if "*" in name:
                parsed_names.extend(_parse_name_from_pattern(deploy_configs, name))
            else:
                parsed_names.append(name)
        deploy_configs = _pick_deploy_configs(
            deploy_configs,
            parsed_names,
            deploy_all,
        )

        if len(deploy_configs) > 1:
            if any(options.values()):
                app.console.print(
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
            )
        else:
            # Accommodate passing in -n flow-name/deployment-name as well as -n deployment-name
            options["names"] = [
                name.split("/", 1)[-1] if "/" in name else name for name in parsed_names
            ]
            options["enforce_parameter_schema"] = enforce_parameter_schema

            await _run_single_deploy(
                deploy_config=deploy_configs[0] if deploy_configs else {},
                actions=actions,
                options=options,
                prefect_file=prefect_file,
            )
    except ValueError as exc:
        exit_with_error(str(exc))


@inject_client
async def _run_single_deploy(
    deploy_config: Dict,
    actions: Dict,
    options: Optional[Dict] = None,
    client: Optional["PrefectClient"] = None,
    prefect_file: Path = Path("prefect.yaml"),
):
    deploy_config = deepcopy(deploy_config) if deploy_config else {}
    actions = deepcopy(actions) if actions else {}
    options = deepcopy(options) if options else {}

    should_prompt_for_save = is_interactive()

    deploy_config = _merge_with_default_deploy_config(deploy_config)
    deploy_config = _handle_deprecated_schedule_fields(deploy_config)
    (
        deploy_config,
        variable_overrides,
    ) = _apply_cli_options_to_deploy_config(deploy_config, options)

    build_steps = deploy_config.get("build", actions.get("build")) or []
    push_steps = deploy_config.get("push", actions.get("push")) or []
    pull_steps = deploy_config.get("pull", actions.get("pull")) or []

    deploy_config = await resolve_block_document_references(deploy_config)
    deploy_config = await resolve_variables(deploy_config)

    # check for env var placeholders early so users can pass work pool names, etc.
    deploy_config = apply_values(deploy_config, os.environ, remove_notset=False)

    if not deploy_config.get("entrypoint"):
        if not is_interactive():
            raise ValueError(
                "An entrypoint must be provided:\n\n"
                " \t[yellow]prefect deploy path/to/file.py:flow_function\n\n"
                "You can also provide an entrypoint in a prefect.yaml file."
            )
        deploy_config["entrypoint"] = await prompt_entrypoint(app.console)

    flow = load_flow_from_entrypoint(deploy_config["entrypoint"])

    deploy_config["flow_name"] = flow.name

    deployment_name = deploy_config.get("name")
    if not deployment_name:
        if not is_interactive():
            raise ValueError("A deployment name must be provided.")
        deploy_config["name"] = prompt("Deployment name", default="default")

    deploy_config["parameter_openapi_schema"] = parameter_schema(flow)

    deploy_config["schedules"] = _construct_schedules(
        deploy_config,
    )

    # determine work pool
    work_pool_name = get_from_dict(deploy_config, "work_pool.name")
    if work_pool_name:
        try:
            work_pool = await client.read_work_pool(deploy_config["work_pool"]["name"])

            # dont allow submitting to prefect-agent typed work pools
            if work_pool.type == "prefect-agent":
                if not is_interactive():
                    raise ValueError(
                        "Cannot create a project-style deployment with work pool of"
                        " type 'prefect-agent'. If you wish to use an agent with"
                        " your deployment, please use the `prefect deployment"
                        " build` command."
                    )
                app.console.print(
                    "You've chosen a work pool with type 'prefect-agent' which"
                    " cannot be used for project-style deployments. Let's pick"
                    " another work pool to deploy to."
                )
                deploy_config["work_pool"]["name"] = await prompt_select_work_pool(
                    app.console
                )
        except ObjectNotFound:
            raise ValueError(
                "This deployment configuration references work pool"
                f" {deploy_config['work_pool']['name']!r} which does not exist. This"
                " means no worker will be able to pick up its runs. You can create a"
                " work pool in the Prefect UI."
            )
    else:
        if not is_interactive():
            raise ValueError(
                "A work pool is required to deploy this flow. Please specify a work"
                " pool name via the '--pool' flag or in your prefect.yaml file."
            )
        if not isinstance(deploy_config.get("work_pool"), dict):
            deploy_config["work_pool"] = {}
        deploy_config["work_pool"]["name"] = await prompt_select_work_pool(
            console=app.console
        )

    docker_build_steps = [
        "prefect_docker.deployments.steps.build_docker_image",
    ]

    docker_push_steps = [
        "prefect_docker.deployments.steps.push_docker_image",
    ]

    docker_build_step_exists = any(
        any(step in action for step in docker_build_steps)
        for action in deploy_config.get("build", actions.get("build")) or []
    )

    update_work_pool_image = False

    build_step_set_to_null = "build" in deploy_config and deploy_config["build"] is None

    work_pool = await client.read_work_pool(deploy_config["work_pool"]["name"])

    if is_interactive() and not docker_build_step_exists and not build_step_set_to_null:
        docker_based_infrastructure = "image" in work_pool.base_job_template.get(
            "variables", {}
        ).get("properties", {})
        if docker_based_infrastructure:
            build_docker_image_step = await prompt_build_custom_docker_image(
                app.console, deploy_config
            )
            if build_docker_image_step is not None:
                work_pool_job_variables_image_not_found = not get_from_dict(
                    deploy_config, "work_pool.job_variables.image"
                )
                if work_pool_job_variables_image_not_found:
                    update_work_pool_image = True

                (
                    push_docker_image_step,
                    updated_build_docker_image_step,
                ) = await prompt_push_custom_docker_image(
                    app.console, deploy_config, build_docker_image_step
                )

                if actions.get("build"):
                    actions["build"].append(updated_build_docker_image_step)
                else:
                    actions["build"] = [updated_build_docker_image_step]

                if push_docker_image_step is not None:
                    if actions.get("push"):
                        actions["push"].append(push_docker_image_step)
                    else:
                        actions["push"] = [push_docker_image_step]

            build_steps = deploy_config.get("build", actions.get("build")) or []
            push_steps = deploy_config.get("push", actions.get("push")) or []

    docker_push_step_exists = any(
        any(step in action for step in docker_push_steps)
        for action in deploy_config.get("push", actions.get("push")) or []
    )

    ## CONFIGURE PUSH and/or PULL STEPS FOR REMOTE FLOW STORAGE
    if (
        is_interactive()
        and not (deploy_config.get("pull") or actions.get("pull"))
        and not docker_push_step_exists
        and confirm(
            (
                "Your Prefect workers will need access to this flow's code in order to"
                " run it. Would you like your workers to pull your flow code from a"
                " remote storage location when running this flow?"
            ),
            default=True,
            console=app.console,
        )
    ):
        actions = await _generate_actions_for_remote_flow_storage(
            console=app.console, deploy_config=deploy_config, actions=actions
        )

    if trigger_specs := _gather_deployment_trigger_definitions(
        options.get("triggers"), deploy_config.get("triggers")
    ):
        triggers = _initialize_deployment_triggers(deployment_name, trigger_specs)
    else:
        triggers = []

    pull_steps = (
        pull_steps
        or actions.get("pull")
        or await _generate_default_pull_action(
            app.console,
            deploy_config=deploy_config,
            actions=actions,
        )
    )

    ## RUN BUILD AND PUSH STEPS
    step_outputs = {}
    if build_steps:
        app.console.print("Running deployment build steps...")
        step_outputs.update(
            await run_steps(build_steps, step_outputs, print_function=app.console.print)
        )

    if push_steps := push_steps or actions.get("push"):
        app.console.print("Running deployment push steps...")
        step_outputs.update(
            await run_steps(push_steps, step_outputs, print_function=app.console.print)
        )

    step_outputs.update(variable_overrides)

    if update_work_pool_image:
        if "build-image" not in step_outputs:
            app.console.print(
                "Warning: no build-image step found in the deployment build steps."
                " The work pool image will not be updated."
            )
        deploy_config["work_pool"]["job_variables"]["image"] = "{{ build-image.image }}"

    if not deploy_config.get("description"):
        deploy_config["description"] = flow.description

    # save deploy_config before templating
    deploy_config_before_templating = deepcopy(deploy_config)
    ## apply templating from build and push steps to the final deployment spec
    _parameter_schema = deploy_config.pop("parameter_openapi_schema")

    _schedules = deploy_config.pop("schedules")

    deploy_config = apply_values(deploy_config, step_outputs)
    deploy_config["parameter_openapi_schema"] = _parameter_schema
    deploy_config["schedules"] = _schedules

    pull_steps = apply_values(pull_steps, step_outputs, remove_notset=False)

    flow_id = await client.create_flow_from_name(deploy_config["flow_name"])

    deployment_id = await client.create_deployment(
        flow_id=flow_id,
        name=deploy_config.get("name"),
        work_queue_name=get_from_dict(deploy_config, "work_pool.work_queue_name"),
        work_pool_name=get_from_dict(deploy_config, "work_pool.name"),
        version=deploy_config.get("version"),
        schedules=deploy_config.get("schedules"),
        paused=deploy_config.get("paused"),
        enforce_parameter_schema=deploy_config.get("enforce_parameter_schema", True),
        parameter_openapi_schema=deploy_config.get(
            "parameter_openapi_schema"
        ).model_dump_for_openapi(),
        parameters=deploy_config.get("parameters"),
        description=deploy_config.get("description"),
        tags=deploy_config.get("tags", []),
        concurrency_limit=deploy_config.get("concurrency_limit"),
        entrypoint=deploy_config.get("entrypoint"),
        pull_steps=pull_steps,
        job_variables=get_from_dict(deploy_config, "work_pool.job_variables"),
    )

    await _create_deployment_triggers(client, deployment_id, triggers)

    app.console.print(
        Panel(
            f"Deployment '{deploy_config['flow_name']}/{deploy_config['name']}'"
            f" successfully created with id '{deployment_id}'."
        ),
        style="green",
    )

    if PREFECT_UI_URL:
        app.console.print(
            "\nView Deployment in UI:"
            f" {PREFECT_UI_URL.value()}/deployments/deployment/{deployment_id}\n"
        )

    identical_deployment_exists_in_prefect_file = (
        _check_if_identical_deployment_in_prefect_file(
            deploy_config_before_templating, prefect_file
        )
    )
    if should_prompt_for_save and not identical_deployment_exists_in_prefect_file:
        if confirm(
            (
                "Would you like to save configuration for this deployment for faster"
                " deployments in the future?"
            ),
            console=app.console,
        ):
            matching_deployment_exists = (
                _check_for_matching_deployment_name_and_entrypoint_in_prefect_file(
                    deploy_config=deploy_config_before_templating,
                    prefect_file=prefect_file,
                )
            )
            if matching_deployment_exists and not confirm(
                (
                    "Found existing deployment configuration with name:"
                    f" [yellow]{deploy_config_before_templating.get('name')}[/yellow]"
                    " and entrypoint:"
                    f" [yellow]{deploy_config_before_templating.get('entrypoint')}[/yellow]"
                    f" in the [yellow]prefect.yaml[/yellow] file at {prefect_file}."
                    " Would you like to overwrite that entry?"
                ),
            ):
                app.console.print(
                    "[red]Cancelled saving deployment configuration"
                    f" '{deploy_config_before_templating.get('name')}' to the"
                    f" deployment configuration file[/red] at {prefect_file}"
                )
            else:
                deploy_config_before_templating.update({"schedules": _schedules})
                _save_deployment_to_prefect_file(
                    deploy_config_before_templating,
                    build_steps=build_steps or None,
                    push_steps=push_steps or None,
                    pull_steps=pull_steps or None,
                    triggers=trigger_specs or None,
                    prefect_file=prefect_file,
                )
                app.console.print(
                    (
                        f"\n[green]Deployment configuration saved to {prefect_file}![/]"
                        " You can now deploy using this deployment configuration"
                        " with:\n\n\t[blue]$ prefect deploy -n"
                        f" {deploy_config['name']}[/]\n\nYou can also make changes to"
                        " this deployment configuration by making changes to the"
                        " YAML file."
                    ),
                )
    if not work_pool.is_push_pool and not work_pool.is_managed_pool:
        app.console.print(
            "\nTo execute flow runs from this deployment, start a worker in a"
            " separate terminal that pulls work from the"
            f" {deploy_config['work_pool']['name']!r} work pool:"
        )
        app.console.print(
            f"\n\t$ prefect worker start --pool {deploy_config['work_pool']['name']!r}",
            style="blue",
        )
    app.console.print(
        "\nTo schedule a run for this deployment, use the following command:"
    )
    app.console.print(
        (
            "\n\t$ prefect deployment run"
            f" '{deploy_config['flow_name']}/{deploy_config['name']}'\n"
        ),
        style="blue",
    )


async def _run_multi_deploy(
    deploy_configs: List[Dict],
    actions: Dict,
    names: Optional[List[str]] = None,
    deploy_all: bool = False,
    prefect_file: Path = Path("prefect.yaml"),
):
    deploy_configs = deepcopy(deploy_configs) if deploy_configs else []
    actions = deepcopy(actions) if actions else {}
    names = names or []

    if deploy_all:
        app.console.print(
            "Deploying all flows with an existing deployment configuration..."
        )
    else:
        app.console.print("Deploying flows with selected deployment configurations...")
    for deploy_config in deploy_configs:
        if deploy_config.get("name") is None:
            if not is_interactive():
                app.console.print(
                    "Discovered unnamed deployment. Skipping...", style="yellow"
                )
                continue
            app.console.print("Discovered unnamed deployment.", style="yellow")
            app.console.print_json(data=deploy_config)
            if confirm(
                "Would you like to give this deployment a name and deploy it?",
                default=True,
                console=app.console,
            ):
                deploy_config["name"] = prompt("Deployment name", default="default")
            else:
                app.console.print("Skipping unnamed deployment.", style="yellow")
                continue
        app.console.print(Panel(f"Deploying {deploy_config['name']}", style="blue"))
        await _run_single_deploy(deploy_config, actions, prefect_file=prefect_file)


def _construct_schedules(
    deploy_config: Dict,
) -> List[DeploymentScheduleCreate]:
    """
    Constructs a schedule from a deployment configuration.

    Args:
        deploy_config: A deployment configuration

    Returns:
        A list of schedule objects
    """
    schedule_configs = deploy_config.get("schedules", NotSet) or []

    if schedule_configs is not NotSet:
        schedules = [
            _schedule_config_to_deployment_schedule(schedule_config)
            for schedule_config in schedule_configs
        ]
    elif schedule_configs is NotSet:
        if is_interactive():
            schedules = prompt_schedules(app.console)
        else:
            schedules = []

    return schedules


def _schedule_config_to_deployment_schedule(
    schedule_config: Dict,
) -> DeploymentScheduleCreate:
    cron = schedule_config.get("cron")
    interval = schedule_config.get("interval")
    anchor_date = schedule_config.get("anchor_date")
    rrule = schedule_config.get("rrule")
    timezone = schedule_config.get("timezone")
    schedule_active = schedule_config.get("active", True)
    max_active_runs = schedule_config.get("max_active_runs")
    catchup = schedule_config.get("catchup", False)

    if cron:
        cron_kwargs = {"cron": cron, "timezone": timezone}
        schedule = CronSchedule(
            **{k: v for k, v in cron_kwargs.items() if v is not None}
        )
    elif interval:
        interval_kwargs = {
            "interval": timedelta(seconds=interval),
            "anchor_date": anchor_date,
            "timezone": timezone,
        }
        schedule = IntervalSchedule(
            **{k: v for k, v in interval_kwargs.items() if v is not None}
        )
    elif rrule:
        try:
            schedule = RRuleSchedule(**json.loads(rrule))
            if timezone:
                # override timezone if specified via CLI argument
                schedule.timezone = timezone
        except json.JSONDecodeError:
            schedule = RRuleSchedule(rrule=rrule, timezone=timezone)
    else:
        raise ValueError(
            f"Unknown schedule type. Please provide a valid schedule. schedule={schedule_config}"
        )

    return DeploymentScheduleCreate(
        schedule=schedule,
        active=schedule_active,
        max_active_runs=max_active_runs,
        catchup=catchup,
    )


def _merge_with_default_deploy_config(deploy_config: Dict):
    """
    Merge a base deploy config with the default deploy config.
    If a key is missing in the base deploy config, it will be filled with the
    corresponding value from the default deploy config.

    Parameters:
        deploy_config: The base deploy config to be merged with
        the default deploy config.

    Returns:
        The merged deploy config.
    """
    deploy_config = deepcopy(deploy_config)
    DEFAULT_DEPLOY_CONFIG = {
        "name": None,
        "version": None,
        "tags": [],
        "concurrency_limit": None,
        "description": None,
        "flow_name": None,
        "entrypoint": None,
        "parameters": {},
        "work_pool": {
            "name": None,
            "work_queue_name": None,
            "job_variables": {},
        },
    }

    # merge default and base deploy configs
    # this allows for missing keys in a user's deploy config
    for key, value in DEFAULT_DEPLOY_CONFIG.items():
        if key not in deploy_config:
            deploy_config[key] = value
        if isinstance(value, dict):
            for k, v in value.items():
                if k not in deploy_config[key]:
                    deploy_config[key][k] = v

    return deploy_config


async def _generate_git_clone_pull_step(
    console: Console,
    deploy_config: Dict,
    remote_url: str,
):
    branch = _get_git_branch() or "main"

    if not remote_url:
        remote_url = prompt(
            "Please enter the URL to pull your flow code from", console=console
        )

    elif not confirm(
        f"Is [green]{remote_url}[/] the correct URL to pull your flow code from?",
        default=True,
        console=console,
    ):
        remote_url = prompt(
            "Please enter the URL to pull your flow code from", console=console
        )
    if not confirm(
        f"Is [green]{branch}[/] the correct branch to pull your flow code from?",
        default=True,
        console=console,
    ):
        branch = prompt(
            "Please enter the branch to pull your flow code from",
            default="main",
            console=console,
        )
    token_secret_block_name = None
    if confirm("Is this a private repository?", console=console):
        token_secret_block_name = f"deployment-{slugify(deploy_config['name'])}-{slugify(deploy_config['flow_name'])}-repo-token"
        create_new_block = False
        prompt_message = (
            "Please enter a token that can be used to access your private"
            " repository. This token will be saved as a secret via the Prefect API"
        )

        try:
            await Secret.load(token_secret_block_name)
            if not confirm(
                (
                    "We found an existing token saved for this deployment. Would"
                    " you like use the existing token?"
                ),
                default=True,
                console=console,
            ):
                prompt_message = (
                    "Please enter a token that can be used to access your private"
                    " repository (this will overwrite the existing token saved via"
                    " the Prefect API)."
                )

                create_new_block = True
        except ValueError:
            create_new_block = True

        if create_new_block:
            try:
                repo_token = prompt(
                    prompt_message,
                    console=console,
                    password=True,
                )
            except GetPassWarning:
                # Handling for when password masking is not supported
                repo_token = prompt(
                    prompt_message,
                    console=console,
                )
            await Secret(
                value=repo_token,
            ).save(name=token_secret_block_name, overwrite=True)

    git_clone_step = {
        "prefect.deployments.steps.git_clone": {
            "repository": remote_url,
            "branch": branch,
        }
    }

    if token_secret_block_name:
        git_clone_step["prefect.deployments.steps.git_clone"]["access_token"] = (
            "{{ prefect.blocks.secret." + token_secret_block_name + " }}"
        )

    return [git_clone_step]


async def _generate_pull_step_for_build_docker_image(
    console: Console, deploy_config: Dict, auto: bool = True
):
    pull_step = {}
    dir_name = os.path.basename(os.getcwd())
    if auto:
        pull_step["directory"] = f"/opt/prefect/{dir_name}"
    else:
        pull_step["directory"] = prompt(
            "What is the path to your flow code in your Dockerfile?",
            default=f"/opt/prefect/{dir_name}",
            console=console,
        )

    return [{"prefect.deployments.steps.set_working_directory": pull_step}]


async def _check_for_build_docker_image_step(
    build_action: List[Dict],
) -> Optional[Dict[str, Any]]:
    if not build_action:
        return None

    build_docker_image_steps = [
        "prefect_docker.deployments.steps.build_docker_image",
    ]
    for build_docker_image_step in build_docker_image_steps:
        for action in build_action:
            if action.get(build_docker_image_step):
                return action.get(build_docker_image_step)

    return None


async def _generate_actions_for_remote_flow_storage(
    console: Console, deploy_config: dict, actions: List[Dict]
) -> Dict[str, List[Dict[str, Any]]]:
    storage_provider_to_collection = {
        "s3": "prefect_aws",
        "gcs": "prefect_gcp",
        "azure_blob_storage": "prefect_azure",
    }
    selected_storage_provider = await prompt_select_remote_flow_storage(console=console)

    if selected_storage_provider == "git":
        actions["pull"] = await _generate_git_clone_pull_step(
            console=console,
            deploy_config=deploy_config,
            remote_url=_get_git_remote_origin_url(),
        )

    elif selected_storage_provider in storage_provider_to_collection.keys():
        collection = storage_provider_to_collection[selected_storage_provider]

        bucket, folder = prompt("Bucket name"), prompt("Folder name")

        credentials = await prompt_select_blob_storage_credentials(
            console=console,
            storage_provider=selected_storage_provider,
        )

        step_fields = {
            (
                "container"
                if selected_storage_provider == "azure_blob_storage"
                else "bucket"
            ): bucket,
            "folder": folder,
            "credentials": credentials,
        }

        actions["push"] = [
            {
                f"{collection}.deployments.steps.push_to_{selected_storage_provider}": (
                    step_fields
                )
            }
        ]

        actions["pull"] = [
            {
                f"{collection}.deployments.steps.pull_from_{selected_storage_provider}": (
                    step_fields
                )
            }
        ]

    return actions


async def _generate_default_pull_action(
    console: Console,
    deploy_config: Dict,
    actions: List[Dict],
):
    build_docker_image_step = await _check_for_build_docker_image_step(
        deploy_config.get("build") or actions["build"]
    )
    if build_docker_image_step:
        dockerfile = build_docker_image_step.get("dockerfile")
        if dockerfile == "auto":
            return await _generate_pull_step_for_build_docker_image(
                console, deploy_config
            )
        if is_interactive():
            if not confirm(
                "Does your Dockerfile have a line that copies the current working"
                " directory into your image?"
            ):
                exit_with_error(
                    "Your flow code must be copied into your Docker image to run"
                    " your deployment.\nTo do so, you can copy this line into your"
                    " Dockerfile: [yellow]COPY . /opt/prefect/[/yellow]"
                )
            return await _generate_pull_step_for_build_docker_image(
                console, deploy_config, auto=False
            )
    else:
        entrypoint_path, _ = deploy_config["entrypoint"].split(":")
        console.print(
            "Your Prefect workers will attempt to load your flow from:"
            f" [green]{(Path.cwd()/Path(entrypoint_path)).absolute().resolve()}[/]. To"
            " see more options for managing your flow's code, run:\n\n\t[blue]$"
            " prefect init[/]\n"
        )
        return [
            {
                "prefect.deployments.steps.set_working_directory": {
                    "directory": str(Path.cwd().absolute().resolve())
                }
            }
        ]


def _load_deploy_configs_and_actions(
    prefect_file: Path,
) -> Tuple[List[Dict], Dict]:
    """
    Load deploy configs and actions from a deployment configuration YAML file.

    Returns:
        Tuple[List[Dict], Dict]: a tuple of deployment configurations and actions
    """
    try:
        with prefect_file.open("r") as f:
            prefect_yaml_contents = yaml.safe_load(f)
    except (FileNotFoundError, IsADirectoryError, YAMLError) as exc:
        app.console.print(
            f"Unable to read the specified config file. Reason: {exc}. Skipping.",
            style="yellow",
        )
        prefect_yaml_contents = {}
    if not isinstance(prefect_yaml_contents, dict):
        app.console.print(
            "Unable to parse the specified config file. Skipping.",
            style="yellow",
        )
        prefect_yaml_contents = {}

    actions = {
        "build": prefect_yaml_contents.get("build", []),
        "push": prefect_yaml_contents.get("push", []),
        "pull": prefect_yaml_contents.get("pull", []),
    }

    deploy_configs = prefect_yaml_contents.get("deployments", [])

    return deploy_configs, actions


def _handle_pick_deploy_without_name(deploy_configs):
    # Prompt the user to select one or more deployment configurations
    selectable_deploy_configs = [
        deploy_config for deploy_config in deploy_configs if deploy_config.get("name")
    ]
    if not selectable_deploy_configs:
        return []
    selected_deploy_config = prompt_select_from_table(
        app.console,
        "Would you like to use an existing deployment configuration?",
        [
            {"header": "Name", "key": "name"},
            {"header": "Entrypoint", "key": "entrypoint"},
            {"header": "Description", "key": "description"},
        ],
        selectable_deploy_configs,
        opt_out_message="No, configure a new deployment",
        opt_out_response=None,
    )
    return [selected_deploy_config] if selected_deploy_config else []


def _log_missing_deployment_names(missing_names, matched_deploy_configs, names):
    # Log unfound names
    if missing_names:
        app.console.print(
            (
                "The following deployment(s) could not be found and will not be"
                f" deployed: {', '.join(list(sorted(missing_names)))}"
            ),
            style="yellow",
        )
    if not matched_deploy_configs:
        app.console.print(
            (
                "Could not find any deployment configurations with the given"
                f" name(s): {', '.join(names)}. Your flow will be deployed with a"
                " new deployment configuration."
            ),
            style="yellow",
        )


def _filter_matching_deploy_config(name, deploy_configs):
    # Logic to find the deploy_config matching the given name
    # This function handles both "flow-name/deployment-name" and just "deployment-name"
    matching_deployments = []
    if "/" in name:
        flow_name, deployment_name = name.split("/")
        flow_name = flow_name.replace("-", "_")
        matching_deployments = [
            deploy_config
            for deploy_config in deploy_configs
            if deploy_config.get("name") == deployment_name
            and deploy_config.get("entrypoint", "").split(":")[-1] == flow_name
        ]
    else:
        matching_deployments = [
            deploy_config
            for deploy_config in deploy_configs
            if deploy_config.get("name") == name
        ]
    return matching_deployments


def _parse_name_from_pattern(deploy_configs, name_pattern):
    """
    Parse the deployment names from a user-provided pattern such as "flow-name/*" or "my-deployment-*"

    Example:

    >>> deploy_configs = [
    ...     {"name": "my-deployment-1", "entrypoint": "flow-name-1"},
    ...     {"name": "my-deployment-2", "entrypoint": "flow-name-2"},
    ...     {"name": "my-deployment-3", "entrypoint": "flow-name-3"},
    ... ]

    >>> _parse_name_from_pattern(deploy_configs, "flow-name-1/*")
    ["my-deployment-1"]

    Args:
        deploy_configs: A list of deploy configs
        name: A pattern to match against the deploy configs

    Returns:
        List[str]: a list of deployment names that match the given pattern
    """
    parsed_names = []

    name_pattern = re.escape(name_pattern).replace(r"\*", ".*")

    # eg. "flow-name/deployment-name"
    if "/" in name_pattern:
        flow_name, deploy_name = name_pattern.split("/", 1)
        flow_name = (
            re.compile(flow_name.replace("*", ".*"))
            if "*" in flow_name
            else re.compile(flow_name)
        )
        deploy_name = (
            re.compile(deploy_name.replace("*", ".*"))
            if "*" in deploy_name
            else re.compile(deploy_name)
        )
    # e.g. "deployment-name"
    else:
        flow_name = None
        deploy_name = re.compile(name_pattern.replace("*", ".*"))

    for deploy_config in deploy_configs:
        # skip the default deploy config where this may be None
        if not deploy_config.get("entrypoint"):
            continue
        entrypoint = deploy_config.get("entrypoint").split(":")[-1].replace("_", "-")
        deployment_name = deploy_config.get("name")
        flow_match = flow_name.fullmatch(entrypoint) if flow_name else True
        deploy_match = deploy_name.fullmatch(deployment_name)
        if flow_match and deploy_match:
            parsed_names.append(deployment_name)

    return parsed_names


def _handle_pick_deploy_with_name(
    deploy_configs,
    names,
):
    matched_deploy_configs = []
    deployment_names = []
    for name in names:
        matching_deployments = _filter_matching_deploy_config(name, deploy_configs)

        if len(matching_deployments) > 1 and is_interactive():
            user_selected_matching_deployment = prompt_select_from_table(
                app.console,
                (
                    "Found multiple deployment configurations with the name"
                    f" [yellow]{name}[/yellow]. Please select the one you would"
                    " like to deploy:"
                ),
                [
                    {"header": "Name", "key": "name"},
                    {"header": "Entrypoint", "key": "entrypoint"},
                    {"header": "Description", "key": "description"},
                ],
                matching_deployments,
            )
            matched_deploy_configs.append(user_selected_matching_deployment)
        elif matching_deployments:
            matched_deploy_configs.extend(matching_deployments)

        deployment_names.append(
            name.split("/")[-1]
        )  # Keep only the deployment_name part if any

    unfound_names = set(deployment_names) - {
        deploy_config.get("name") for deploy_config in matched_deploy_configs
    }
    _log_missing_deployment_names(unfound_names, matched_deploy_configs, names)

    return matched_deploy_configs


def _pick_deploy_configs(
    deploy_configs,
    names,
    deploy_all,
):
    """
    Return a list of deploy configs to deploy based on the given
    deploy configs, names, and deploy_all flag.

    Args:
        deploy_configs: A list of deploy configs
        names: A list of names of deploy configs to deploy
        deploy_all: Whether to use all deploy configs

    Returns:
        List[Dict]: a list of deploy configs to deploy
    """
    if not deploy_configs:
        return []

    elif deploy_all:
        return deploy_configs

    # e.g. `prefect --no-prompt deploy`
    elif not is_interactive() and len(deploy_configs) == 1 and len(names) <= 1:
        # No name is needed if there is only one deployment configuration
        # and we are not in interactive mode
        return deploy_configs

    # e.g. `prefect deploy -n flow-name/deployment-name -n deployment-name`
    elif len(names) >= 1:
        return _handle_pick_deploy_with_name(
            deploy_configs,
            names,
        )

    # e.g. `prefect deploy`
    elif is_interactive():
        return _handle_pick_deploy_without_name(deploy_configs)

    # e.g `prefect --no-prompt deploy` where we have multiple deployment configurations
    elif len(deploy_configs) > 1:
        raise ValueError(
            "Discovered one or more deployment configurations, but"
            " no name was given. Please specify the name of at least one"
            " deployment to create or update."
        )
    else:
        return []


def _extract_variable(variable: str) -> Dict[str, Any]:
    """
    Extracts a variable from a string. Variables can be in the format
    key=value or a JSON object.
    """
    try:
        key, value = variable.split("=", 1)
    except ValueError:
        pass
    else:
        return {key: value}

    try:
        # Only key=value strings and JSON objexcts are valid inputs for
        # variables, not arrays or strings, so we attempt to convert the parsed
        # object to a dict.
        return dict(json.loads(variable))
    except (ValueError, TypeError) as e:
        raise ValueError(
            f'Could not parse variable: "{variable}". Please ensure variables are'
            " either in the format `key=value` or are strings containing a valid JSON"
            " object."
        ) from e


def _apply_cli_options_to_deploy_config(deploy_config, cli_options):
    """
    Applies CLI options to a deploy config. CLI options take
    precedence over values in the deploy config.

    Args:
        deploy_config: A deploy config
        cli_options: A dictionary of CLI options

    Returns:
        Dict: a deploy config with CLI options applied
    """
    deploy_config = deepcopy(deploy_config)

    # verification
    if cli_options.get("param") and (cli_options.get("params") is not None):
        raise ValueError("Can only pass one of `param` or `params` options")

    # If there's more than one name, we can't set the name of the deploy config.
    # The user will be prompted if running in interactive mode.
    if len(cli_options.get("names", [])) == 1:
        deploy_config["name"] = cli_options["names"][0]

    variable_overrides = {}
    for cli_option, cli_value in cli_options.items():
        if (
            cli_option
            in [
                "description",
                "entrypoint",
                "version",
                "tags",
                "concurrency_limit",
                "flow_name",
                "enforce_parameter_schema",
            ]
            and cli_value
        ):
            deploy_config[cli_option] = cli_value

        elif (
            cli_option in ["work_pool_name", "work_queue_name", "variables"]
            and cli_value
        ):
            if not isinstance(deploy_config.get("work_pool"), dict):
                deploy_config["work_pool"] = {}
            if cli_option == "work_pool_name":
                deploy_config["work_pool"]["name"] = cli_value
            elif cli_option == "variables":
                for variable in cli_value or []:
                    variable_overrides.update(**_extract_variable(variable))
                if not isinstance(deploy_config["work_pool"].get("variables"), dict):
                    deploy_config["work_pool"]["job_variables"] = {}
                deploy_config["work_pool"]["job_variables"].update(variable_overrides)
            else:
                deploy_config["work_pool"][cli_option] = cli_value

        elif cli_option in ["cron", "interval", "rrule"] and cli_value:
            if not isinstance(deploy_config.get("schedules"), list):
                deploy_config["schedules"] = []

            for value in cli_value:
                deploy_config["schedules"].append({cli_option: value})

        elif cli_option in ["param", "params"] and cli_value:
            parameters = dict()
            if cli_option == "param":
                for p in cli_value or []:
                    k, unparsed_value = p.split("=", 1)
                    try:
                        v = json.loads(unparsed_value)
                        app.console.print(
                            f"The parameter value {unparsed_value} is parsed as a JSON"
                            " string"
                        )
                    except json.JSONDecodeError:
                        v = unparsed_value
                    parameters[k] = v

            if cli_option == "params" and cli_value is not None:
                parameters = json.loads(cli_value)

            if not isinstance(deploy_config.get("parameters"), dict):
                deploy_config["parameters"] = {}
            deploy_config["parameters"].update(parameters)

    anchor_date = cli_options.get("anchor_date")
    timezone = cli_options.get("timezone")

    # Apply anchor_date and timezone to new and existing schedules
    for schedule_config in deploy_config.get("schedules") or []:
        if anchor_date and schedule_config.get("interval"):
            schedule_config["anchor_date"] = anchor_date
        if timezone:
            schedule_config["timezone"] = timezone

    return deploy_config, variable_overrides


def _check_for_matching_deployment_name_and_entrypoint_in_prefect_file(
    deploy_config, prefect_file: Path = Path("prefect.yaml")
) -> bool:
    if prefect_file.exists():
        with prefect_file.open(mode="r") as f:
            parsed_prefect_file_contents = yaml.safe_load(f)
            existing_deployments = parsed_prefect_file_contents.get("deployments")
            if existing_deployments is not None:
                for existing_deployment in existing_deployments:
                    if existing_deployment.get("name") == deploy_config.get(
                        "name"
                    ) and (
                        existing_deployment.get("entrypoint")
                        == deploy_config.get("entrypoint")
                    ):
                        return True
    return False


def _check_if_identical_deployment_in_prefect_file(
    untemplated_deploy_config: Dict, prefect_file: Path = Path("prefect.yaml")
) -> bool:
    """
    Check if the given deploy config is identical to an existing deploy config in the
    prefect.yaml file, meaning that there have been no updates and prompting to save is unnecessary.

    Args:
        untemplated_deploy_config: A deploy config that has not been templated.
    """

    user_specified_deploy_config = _format_deployment_for_saving_to_prefect_file(
        untemplated_deploy_config
    )
    if prefect_file.exists():
        with prefect_file.open(mode="r") as f:
            parsed_prefect_file_contents = yaml.safe_load(f)
            existing_deployments = parsed_prefect_file_contents.get("deployments")
            if existing_deployments is not None:
                for deploy_config in existing_deployments:
                    if deploy_config == user_specified_deploy_config:
                        return True
    return False


def _initialize_deployment_triggers(
    deployment_name: str, triggers_spec: List[Dict[str, Any]]
) -> List[DeploymentTriggerTypes]:
    triggers = []
    for i, spec in enumerate(triggers_spec, start=1):
        spec.setdefault("name", f"{deployment_name}__automation_{i}")
        triggers.append(
            pydantic.TypeAdapter(DeploymentTriggerTypes).validate_python(spec)
        )

    return triggers


async def _create_deployment_triggers(
    client: "PrefectClient",
    deployment_id: UUID,
    triggers: List[Union[DeploymentTriggerTypes, TriggerTypes]],
):
    try:
        # The triggers defined in the deployment spec are, essentially,
        # anonymous and attempting truly sync them with cloud is not
        # feasible. Instead, we remove all automations that are owned
        # by the deployment, meaning that they were created via this
        # mechanism below, and then recreate them.
        await client.delete_resource_owned_automations(
            f"prefect.deployment.{deployment_id}"
        )
    except PrefectHTTPStatusError as e:
        if e.response.status_code == 404:
            # This Prefect server does not support automations, so we can safely
            # ignore this 404 and move on.
            return
        raise e

    for trigger in triggers:
        trigger.set_deployment_id(deployment_id)
        await client.create_automation(trigger.as_automation())


def _gather_deployment_trigger_definitions(
    trigger_flags: List[str], existing_triggers: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Parses trigger flags from CLI and existing deployment config in `prefect.yaml`.

    Args:
        trigger_flags: Triggers passed via CLI, either as JSON strings or file paths.
        existing_triggers: Triggers from existing deployment configuration.

    Returns:
        List of trigger specifications.

    Raises:
        ValueError: If trigger flag is not a valid JSON string or file path.
    """

    if trigger_flags:
        trigger_specs = []
        for t in trigger_flags:
            try:
                if t.endswith(".yaml"):
                    with open(t, "r") as f:
                        trigger_specs.extend(yaml.safe_load(f).get("triggers", []))
                elif t.endswith(".json"):
                    with open(t, "r") as f:
                        trigger_specs.extend(json.load(f).get("triggers", []))
                else:
                    trigger_specs.append(json.loads(t))
            except Exception as e:
                raise ValueError(f"Failed to parse trigger: {t}. Error: {str(e)}")
        return trigger_specs

    return existing_triggers


def _handle_deprecated_schedule_fields(deploy_config: Dict):
    deploy_config = deepcopy(deploy_config)

    legacy_schedule = deploy_config.get("schedule", NotSet)
    schedule_configs = deploy_config.get("schedules", NotSet)

    if (
        legacy_schedule
        and legacy_schedule is not NotSet
        and schedule_configs is not NotSet
    ):
        raise ValueError(
            "Both 'schedule' and 'schedules' keys are present in the deployment"
            " configuration. Please use only use `schedules`."
        )

    if legacy_schedule and isinstance(legacy_schedule, dict):
        # The yaml has a legacy schedule key, we should honor whatever
        # is there while still appending these new schedules.
        deploy_config["schedules"] = [deploy_config["schedule"]]

        app.console.print(
            generate_deprecation_message(
                "Defining a schedule via the `schedule` key in the deployment",
                start_date="Mar 2024",
                help=(
                    "Please use `schedules` instead by renaming the "
                    "`schedule` key to `schedules` and providing a list of "
                    "schedule objects."
                ),
            ),
            style="yellow",
        )

    return deploy_config

"""Module containing implementation for deploying projects."""
from getpass import GetPassWarning
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import typer
import typer.core
import yaml
from rich.panel import Panel
from rich.console import Console

from prefect.cli._utilities import (
    exit_with_error,
)
from prefect.cli._prompts import (
    prompt,
    confirm,
    prompt_select_from_table,
    prompt_schedule,
    prompt_select_work_pool,
    prompt_entrypoint,
)
from prefect.cli.root import app, is_interactive
from prefect.client.schemas.schedules import (
    SCHEDULE_TYPES,
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.client.utilities import inject_client
from prefect.exceptions import ObjectNotFound
from prefect.flows import load_flow_from_entrypoint
from prefect.deployments import find_prefect_directory, register_flow
from prefect.settings import PREFECT_UI_URL, PREFECT_DEBUG_MODE
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.callables import parameter_schema
from prefect.utilities.templating import apply_values

from prefect.deployments.steps.core import run_steps

from prefect.deployments.base import (
    _copy_deployments_into_prefect_file,
    _get_git_branch,
    _get_git_remote_origin_url,
    _save_deployment_to_prefect_file,
)

from prefect.blocks.system import Secret

from prefect.utilities.slugify import slugify

from prefect.client.orchestration import PrefectClient

from prefect._internal.compatibility.deprecated import (
    generate_deprecation_message,
)

from prefect.utilities.collections import get_from_dict


@app.command()
async def deploy(
    entrypoint: str = typer.Argument(
        None,
        help=(
            "The path to a flow entrypoint within a project, in the form of"
            " `./path/to/file.py:flow_func_name`"
        ),
    ),
    flow_name: str = typer.Option(
        None,
        "--flow",
        "-f",
        help="The name of a registered flow to create a deployment for.",
    ),
    names: List[str] = typer.Option(
        None, "--name", "-n", help="The name to give the deployment."
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
    work_pool_name: str = typer.Option(
        None,
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
        help=(
            "One or more job variable overrides for the work pool provided in the"
            " format of key=value"
        ),
    ),
    cron: str = typer.Option(
        None,
        "--cron",
        help="A cron string that will be used to set a CronSchedule on the deployment.",
    ),
    interval: int = typer.Option(
        None,
        "--interval",
        help=(
            "An integer specifying an interval (in seconds) that will be used to set an"
            " IntervalSchedule on the deployment."
        ),
    ),
    interval_anchor: Optional[str] = typer.Option(
        None, "--anchor-date", help="The anchor date for an interval schedule"
    ),
    rrule: str = typer.Option(
        None,
        "--rrule",
        help="An RRule that will be used to set an RRuleSchedule on the deployment.",
    ),
    timezone: str = typer.Option(
        None,
        "--timezone",
        help="Deployment schedule timezone string e.g. 'America/New_York'",
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
    deploy_all: bool = typer.Option(
        False,
        "--all",
        help=(
            "Deploy all flows in the project. If a flow name or entrypoint is also"
            " provided, this flag will be ignored."
        ),
    ),
    ci: bool = typer.Option(
        False,
        "--ci",
        help=(
            "Run this command in CI mode. This will disable interactive prompts and"
            " will error if any required arguments are not provided."
        ),
    ),
):
    """
    Deploy a flow from this project by creating a deployment.

    Should be run from a project root directory.
    """
    if ci:
        app.console.print(
            generate_deprecation_message(
                name="The `--ci` flag",
                start_date="Jun 2023",
                help=(
                    "Please use the global `--no-prompt` flag instead: `prefect"
                    " --no-prompt deploy`."
                ),
            ),
            style="yellow",
        )

    options = {
        "entrypoint": entrypoint,
        "flow_name": flow_name,
        "description": description,
        "version": version,
        "tags": tags,
        "work_pool_name": work_pool_name,
        "work_queue_name": work_queue_name,
        "variables": variables,
        "cron": cron,
        "interval": interval,
        "anchor_date": interval_anchor,
        "rrule": rrule,
        "timezone": timezone,
        "param": param,
        "params": params,
    }
    try:
        deploy_configs, actions = _load_deploy_configs_and_actions(ci=ci)
        deploy_configs = _pick_deploy_configs(deploy_configs, names, deploy_all, ci)

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
                ci=ci,
            )
        else:
            options["names"] = names
            await _run_single_deploy(
                deploy_config=deploy_configs[0] if deploy_configs else {},
                actions=actions,
                options=options,
                ci=ci,
            )
    except ValueError as exc:
        exit_with_error(str(exc))


@inject_client
async def _run_single_deploy(
    deploy_config: Dict,
    actions: Dict,
    options: Optional[Dict] = None,
    ci: bool = False,
    client: PrefectClient = None,
):
    deploy_config = deepcopy(deploy_config) if deploy_config else {}
    actions = deepcopy(actions) if actions else {}
    options = deepcopy(options) if options else {}

    should_prompt_for_save = is_interactive() and not ci and not bool(deploy_config)

    deploy_config = _merge_with_default_deploy_config(deploy_config)
    (
        deploy_config,
        variable_overrides,
    ) = _apply_cli_options_to_deploy_config(deploy_config, options)

    build_steps = deploy_config.get("build", actions.get("build")) or []
    push_steps = deploy_config.get("push", actions.get("push")) or []

    if get_from_dict(deploy_config, "schedule.anchor_date") and not get_from_dict(
        deploy_config, "schedule.interval"
    ):
        raise ValueError(
            "An anchor date can only be provided with an interval schedule"
        )

    number_of_schedules_provided = len(
        [
            value
            for value in (
                get_from_dict(deploy_config, "schedule.cron"),
                get_from_dict(deploy_config, "schedule.rrule"),
                get_from_dict(deploy_config, "schedule.interval"),
            )
            if value is not None
        ]
    )

    if number_of_schedules_provided > 1:
        raise ValueError("Only one schedule type can be provided.")

    if not deploy_config.get("flow_name") and not deploy_config.get("entrypoint"):
        if not is_interactive() and not ci:
            raise ValueError(
                "An entrypoint or flow name must be provided.\n\nDeploy a flow by"
                " entrypoint:\n\n\t[yellow]prefect deploy"
                " path/to/file.py:flow_function[/]\n\nDeploy a flow by"
                " name:\n\n\t[yellow]prefect project register-flow"
                " path/to/file.py:flow_function\n\tprefect deploy --flow"
                " registered-flow-name[/]\n\nYou can also provide an entrypoint or flow"
                " name in this project's prefect.yaml file."
            )
        deploy_config["entrypoint"] = await prompt_entrypoint(app.console)
    if deploy_config.get("flow_name") and deploy_config.get("entrypoint"):
        raise ValueError(
            "Received an entrypoint and a flow name for this deployment. Please provide"
            " either an entrypoint or a flow name."
        )

    # flow-name and entrypoint logic
    flow = None
    if deploy_config.get("entrypoint"):
        try:
            flow = await register_flow(deploy_config["entrypoint"])
        except ModuleNotFoundError:
            raise ValueError(
                f"Could not find a flow at {deploy_config['entrypoint']}.\n\nPlease"
                " ensure your entrypoint is in the format path/to/file.py:flow_fn_name"
                " and the file name and flow function name are correct."
            )
        except FileNotFoundError:
            if PREFECT_DEBUG_MODE:
                app.console.print(
                    "Could not find .prefect directory. Flow entrypoint will not be"
                    " registered."
                )
            flow = await run_sync_in_worker_thread(
                load_flow_from_entrypoint, deploy_config["entrypoint"]
            )
        deploy_config["flow_name"] = flow.name
    elif deploy_config.get("flow_name"):
        app.console.print(
            generate_deprecation_message(
                "The ability to deploy by flow name",
                start_date="Jun 2023",
                help=(
                    "\nUse `prefect deploy ./path/to/file.py:flow_fn_name` to specify"
                    " an entrypoint instead."
                ),
            )
        )
        prefect_dir = find_prefect_directory()
        if not prefect_dir:
            raise ValueError(
                "No .prefect directory could be found - run [yellow]`prefect"
                " init`[/yellow] to create one."
            )
        if not (prefect_dir / "flows.json").exists():
            raise ValueError(
                f"Flow {deploy_config['flow_name']!r} cannot be found;"
                " run\n\t[yellow]prefect project register-flow"
                " ./path/to/file.py:flow_fn_name[/yellow]\nto register its location."
            )
        with open(prefect_dir / "flows.json", "r") as f:
            flows = json.load(f)

        if deploy_config["flow_name"] not in flows:
            raise ValueError(
                f"Flow {deploy_config['flow_name']!r} cannot be found;"
                " run\n\t[yellow]prefect project register-flow"
                " ./path/to/file.py:flow_fn_name[/yellow]\nto register its location."
            )

        # set entrypoint from prior registration
        deploy_config["entrypoint"] = flows[deploy_config["flow_name"]]

    if not deploy_config.get("name"):
        if not is_interactive() or ci:
            raise ValueError("A deployment name must be provided.")
        deploy_config["name"] = prompt("Deployment name", default="default")

    # minor optimization in case we already loaded the flow
    if not flow:
        flow = await run_sync_in_worker_thread(
            load_flow_from_entrypoint, deploy_config["entrypoint"]
        )

    deploy_config["parameter_openapi_schema"] = parameter_schema(flow)

    deploy_config["schedule"] = _construct_schedule(deploy_config, ci=ci)

    # determine work pool
    if get_from_dict(deploy_config, "work_pool.name"):
        try:
            work_pool = await client.read_work_pool(deploy_config["work_pool"]["name"])

            # dont allow submitting to prefect-agent typed work pools
            if work_pool.type == "prefect-agent":
                if not is_interactive() or ci:
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
                    app.console,
                    client=client,
                )
        except ObjectNotFound:
            raise ValueError(
                "This deployment configuration references work pool"
                f" {deploy_config['work_pool']['name']!r} which does not exist. This"
                " means no worker will be able to pick up its runs. You can create a"
                " work pool in the Prefect UI."
            )
    else:
        if not is_interactive() or ci:
            raise ValueError(
                "A work pool is required to deploy this flow. Please specify a work"
                " pool name via the '--pool' flag or in your prefect.yaml file."
            )
        if not isinstance(deploy_config.get("work_pool"), dict):
            deploy_config["work_pool"] = {}
        deploy_config["work_pool"]["name"] = await prompt_select_work_pool(
            console=app.console, client=client
        )

    ## RUN BUILD AND PUSH STEPS
    step_outputs = {}
    if build_steps:
        app.console.print("Running deployment build steps...")
        step_outputs.update(
            await run_steps(build_steps, step_outputs, print_function=app.console.print)
        )

    if push_steps:
        app.console.print("Running deployment push steps...")
        step_outputs.update(
            await run_steps(push_steps, step_outputs, print_function=app.console.print)
        )

    step_outputs.update(variable_overrides)

    if not deploy_config.get("description"):
        deploy_config["description"] = flow.description

    ## apply templating from build and push steps to the final deployment spec
    _parameter_schema = deploy_config.pop("parameter_openapi_schema")
    _schedule = deploy_config.pop("schedule")
    deploy_config = apply_values(deploy_config, step_outputs)
    deploy_config["parameter_openapi_schema"] = _parameter_schema
    deploy_config["schedule"] = _schedule

    # prepare the pull step
    pull_steps = deploy_config.get(
        "pull", actions.get("pull")
    ) or await _generate_default_pull_action(
        app.console,
        deploy_config=deploy_config,
        ci=ci,
    )
    pull_steps = apply_values(pull_steps, step_outputs)

    flow_id = await client.create_flow_from_name(deploy_config["flow_name"])

    deployment_id = await client.create_deployment(
        flow_id=flow_id,
        name=deploy_config.get("name"),
        work_queue_name=get_from_dict(deploy_config, "work_pool.work_queue_name"),
        work_pool_name=get_from_dict(deploy_config, "work_pool.name"),
        version=deploy_config.get("version"),
        schedule=deploy_config.get("schedule"),
        parameters=deploy_config.get("parameters"),
        description=deploy_config.get("description"),
        tags=deploy_config.get("tags", []),
        entrypoint=deploy_config.get("entrypoint"),
        parameter_openapi_schema=deploy_config.get("parameter_openapi_schema").dict(),
        pull_steps=pull_steps,
        infra_overrides=get_from_dict(deploy_config, "work_pool.job_variables"),
    )

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

    if should_prompt_for_save and confirm(
        (
            "Would you like to save configuration for this deployment for faster"
            " deployments in the future?"
        ),
        console=app.console,
    ):
        _save_deployment_to_prefect_file(
            deploy_config,
            build_steps=build_steps or None,
            push_steps=push_steps or None,
            pull_steps=pull_steps or None,
        )
        app.console.print(
            (
                "\n[green]Deployment configuration saved to prefect.yaml![/] You can"
                " now deploy using this deployment configuration with:\n\n\t[blue]$"
                f" prefect deploy -n {deploy_config['name']}[/]\n\nYou can also make"
                " changes to this deployment configuration by making changes to the"
                " prefect.yaml file."
            ),
        )

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
    ci: bool = False,
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
            if not is_interactive() or ci:
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
        await _run_single_deploy(deploy_config, actions, ci=ci)


def _construct_schedule(
    deploy_config: Dict,
    ci: bool = False,
) -> Optional[SCHEDULE_TYPES]:
    """
    Constructs a schedule from a deployment configuration.

    Args:
        deploy_config: A deployment configuration
        ci: Disable interactive prompts if True

    Returns:
        A schedule object
    """
    schedule = None
    cron = get_from_dict(deploy_config, "schedule.cron")
    interval = get_from_dict(deploy_config, "schedule.interval")
    anchor_date = get_from_dict(deploy_config, "schedule.anchor_date")
    rrule = get_from_dict(deploy_config, "schedule.rrule")
    timezone = get_from_dict(deploy_config, "schedule.timezone")

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
        if (
            not ci
            and is_interactive()
            and confirm(
                "Would you like to schedule when this flow runs?",
                default=True,
                console=app.console,
            )
        ):
            schedule = prompt_schedule(app.console)

    return schedule


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
        "description": None,
        "schedule": {},
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


async def _generate_default_pull_action(
    console: Console, deploy_config: Dict, ci: bool = False
):
    remote_url = _get_git_remote_origin_url()
    if (
        is_interactive()
        and not ci
        and remote_url
        and confirm(
            (
                "Your Prefect workers will need access to this flow's code in order to"
                " run it. Would you like your workers to pull your flow code from its"
                " remote repository when running this flow?"
            ),
            default=True,
            console=console,
        )
    ):
        branch = _get_git_branch() or "main"

        if not confirm(
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
    else:
        entrypoint_path, _ = deploy_config["entrypoint"].split(":")
        console.print(
            "Your Prefect workers will attempt to load your flow from:"
            f" [green]{(Path.cwd()/Path(entrypoint_path)).absolute().resolve()}[/]. To"
            " see more options for managing your flow's code, run:\n\n\t[blue]$"
            " prefect project recipes ls[/]\n"
        )
        return [
            {
                "prefect.deployments.steps.set_working_directory": {
                    "directory": str(Path.cwd().absolute().resolve())
                }
            }
        ]


def _handle_deployment_yaml_copy(prefect_yaml_contents, ci):
    """
    Handle the deprecation of the deployment.yaml file by copying the
    deployment configurations into the prefect.yaml file.

    Remove this after December 2023.

    Args:
        prefect_yaml_contents: The contents of the prefect.yaml file
        ci: Disables interactive mode if True
    """
    if is_interactive() and not ci and prefect_yaml_contents:
        if confirm(
            generate_deprecation_message(
                "Using a `deployment.yaml` file with `prefect deploy`",
                start_date="Jun 2023",
                help=(
                    "Would you like to copy the contents of your `deployment.yaml`"
                    " file into your `prefect.yaml` file now?"
                ),
            )
        ):
            try:
                _copy_deployments_into_prefect_file()
                app.console.print(
                    "Successfully copied your deployment configurations into your"
                    " prefect.yaml file! Once you've verified that all your"
                    " deployment configurations in your prefect.yaml file are"
                    " correct, you can delete your deployment.yaml file."
                )
            except Exception:
                app.console.print(
                    "Encountered an error while copying deployments into"
                    " prefect.yaml: {exc}"
                )
    else:
        app.console.print(
            generate_deprecation_message(
                "Using a `deployment.yaml` file with `prefect deploy`",
                start_date="Jun 2023",
                help=(
                    "Please use the `prefect.yaml` file instead by copying the"
                    " contents of your `deployment.yaml` file into your"
                    " `prefect.yaml` file."
                ),
            ),
            style="yellow",
        )


def _load_deploy_configs_and_actions(ci=False) -> Tuple[List[Dict], Dict]:
    """
    Load deploy configs and actions from the prefect.yaml file.

    Handles the deprecation of the deployment.yaml file.

    Args:
        ci: Disables interactive mode if True

    Returns:
        Tuple[List[Dict], Dict]: a tuple of deployment configurations and actions
    """
    try:
        with open("prefect.yaml", "r") as f:
            prefect_yaml_contents = yaml.safe_load(f)
    except FileNotFoundError:
        prefect_yaml_contents = {}

    actions = {
        "build": prefect_yaml_contents.get("build", []),
        "push": prefect_yaml_contents.get("push", []),
        "pull": prefect_yaml_contents.get("pull", []),
    }

    # TODO: Remove this after December 2023
    try:
        with open("deployment.yaml", "r") as f:
            deployment_yaml_contents = yaml.safe_load(f)
            if not deployment_yaml_contents:
                deploy_configs = [{}]
            elif deployment_yaml_contents.get("deployments"):
                deploy_configs = deployment_yaml_contents["deployments"]
            else:
                deploy_configs = [deployment_yaml_contents]
        _handle_deployment_yaml_copy(prefect_yaml_contents, ci)
    except FileNotFoundError:
        deploy_configs = prefect_yaml_contents.get("deployments", [])

    return deploy_configs, actions


def _pick_deploy_configs(deploy_configs, names, deploy_all, ci=False):
    """
    Return a list of deploy configs to deploy based on the given
    deploy configs, names, and deploy_all flag.

    Args:
        deploy_configs: A list of deploy configs
        names: A list of names of deploy configs to deploy
        deploy_all: Whether to use all deploy configs
        ci: Disables interactive mode if True

    Returns:
        List[Dict]: a list of deploy configs to deploy
    """
    if not deploy_configs:
        return []
    elif deploy_all:
        return deploy_configs
    elif (not is_interactive() or ci) and len(deploy_configs) == 1 and len(names) <= 1:
        # No name is needed if there is only one deployment configuration
        # and we are not in interactive mode
        return deploy_configs
    elif len(names) >= 1:
        # Return all deployment configurations with the given names
        matched_deploy_configs = [
            deploy_config
            for deploy_config in deploy_configs
            if deploy_config.get("name") in names
        ]
        unfound_names = set(names) - {
            deploy_config.get("name") for deploy_config in matched_deploy_configs
        }
        if unfound_names:
            app.console.print(
                (
                    "The following deployment(s) could not be found and will not be"
                    f" deployed: {' ,'.join(list(unfound_names))}"
                ),
                style="yellow",
            )
        if not matched_deploy_configs:
            app.console.print(
                (
                    "Could not find any deployment configurations with the given"
                    f" name(s): {' ,'.join(names)}. Your flow will be deployed with a"
                    " new deployment configuration."
                ),
                style="yellow",
            )
        return matched_deploy_configs
    elif is_interactive() and not ci:
        # Prompt the user to select one or more deployment configurations
        selectable_deploy_configs = [
            deploy_config
            for deploy_config in deploy_configs
            if deploy_config.get("name")
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
    elif len(deploy_configs) > 1:
        raise ValueError(
            "Discovered one or more deployment configurations, but"
            " no name was given. Please specify the name of at least one"
            " deployment to create or update."
        )
    else:
        return []


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
            cli_option in ["description", "entrypoint", "version", "tags", "flow_name"]
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
                    key, value = variable.split("=", 1)
                    variable_overrides[key] = value
                if not isinstance(deploy_config["work_pool"].get("variables"), dict):
                    deploy_config["work_pool"]["job_variables"] = {}
                deploy_config["work_pool"]["job_variables"].update(variable_overrides)
            else:
                deploy_config["work_pool"][cli_option] = cli_value

        elif (
            cli_option in ["cron", "interval", "anchor_date", "rrule", "timezone"]
            and cli_value
        ):
            if not isinstance(deploy_config.get("schedule"), dict):
                deploy_config["schedule"] = {}
            deploy_config["schedule"][cli_option] = cli_value

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

    return deploy_config, variable_overrides

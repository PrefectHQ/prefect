"""Module containing implementation for deploying projects."""
from getpass import GetPassWarning
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional

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
)
from prefect.cli.root import app, is_interactive
from prefect.client.schemas.schedules import (
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

from prefect._internal.compatibility.deprecated import generate_deprecation_message


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
    # TODO: This function is getting out of hand. It should be refactored into smaller
    # functions.

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
        "interval_anchor": interval_anchor,
        "rrule": rrule,
        "timezone": timezone,
        "param": param,
        "params": params,
    }
    # flag to track deployment.yaml format
    # TODO: remove when deployment.yaml support is removed
    multi_deployment_format = True
    try:
        with open("prefect.yaml", "r") as f:
            project = yaml.safe_load(f)
    except FileNotFoundError:
        project = {}

    try:
        with open("deployment.yaml", "r") as f:
            base_deploy = yaml.safe_load(f)
            if not base_deploy:
                multi_deployment_format = False
                deployments = [{}]
            elif base_deploy.get("deployments"):
                deployments = base_deploy["deployments"]
            else:
                multi_deployment_format = False
                deployments = [base_deploy]
        if is_interactive() and not ci and project:
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

    except FileNotFoundError:
        deployments = project.get("deployments", [])
    try:
        if len(deployments) >= 1:
            if deploy_all or len(names) > 1:
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
                    base_deploys=deployments,
                    project=project,
                    names=names,
                    deploy_all=deploy_all,
                    ci=ci,
                )
            elif len(names) == 1 and multi_deployment_format:
                deployment = next(
                    (d for d in deployments if d.get("name") == names[0]), {}
                )
                if not deployment:
                    app.console.print(
                        (
                            "Could not find deployment configuration with name"
                            f" {names[0]!r}. Your flow will be deployed with a new"
                            " deployment configuration."
                        ),
                        style="yellow",
                    )
                    options["name"] = names[0]
                await _run_single_deploy(
                    base_deploy=deployment, project=project, options=options, ci=ci
                )
            elif not multi_deployment_format:
                options["name"] = names[0] if len(names) == 1 else None
                await _run_single_deploy(
                    base_deploy=deployments[0],
                    project=project,
                    options=options,
                    ci=ci,
                )
            else:
                if not is_interactive() or ci:
                    exit_with_error(
                        "Discovered one or more deployment configurations,"
                        " but no name was given. Please specify the name of at least"
                        " one deployment to create or update."
                    )
                deployments = [
                    deployment
                    for deployment in deployments
                    if deployment.get("name") and deployment.get("entrypoint")
                ]
                if deployments:
                    selected_deployment = prompt_select_from_table(
                        app.console,
                        "Would you like to use an existing deployment configuration?",
                        [
                            {"header": "Name", "key": "name"},
                            {"header": "Entrypoint", "key": "entrypoint"},
                            {"header": "Description", "key": "description"},
                        ],
                        [
                            deployment
                            for deployment in deployments
                            if deployment.get("name")
                        ],
                        opt_out_message="No, configure a new deployment",
                        opt_out_response={},
                    )
                else:
                    selected_deployment = {}
                await _run_single_deploy(
                    base_deploy=selected_deployment,
                    project=project,
                    options=options,
                    ci=ci,
                )
        else:
            options["name"] = names[0] if len(names) == 1 else None
            await _run_single_deploy(
                base_deploy={},
                project=project,
                options=options,
                ci=ci,
            )
    except ValueError as exc:
        exit_with_error(str(exc))


@inject_client
async def _run_single_deploy(
    base_deploy: Dict,
    project: Dict,
    options: Optional[Dict] = None,
    ci: bool = False,
    client: PrefectClient = None,
):
    base_deploy = deepcopy(base_deploy) if base_deploy else {}
    project = deepcopy(project) if project else {}
    options = deepcopy(options) if options else {}

    should_prompt_for_save = is_interactive() and not ci and not bool(base_deploy)
    base_deploy = _merge_with_default_deployment(base_deploy)

    base_deploy_schedule = base_deploy.get("schedule")
    if base_deploy_schedule is None:
        base_deploy_schedule = {}

    name = options.get("name") or base_deploy.get("name")
    flow_name = options.get("flow_name") or base_deploy.get("flow_name")
    entrypoint = options.get("entrypoint") or base_deploy.get("entrypoint")
    param = options.get("param")
    params = options.get("params")
    variables = options.get("variables")
    version = options.get("version")
    tags = options.get("tags")
    description = options.get("description")
    work_pool_name = options.get("work_pool_name")
    work_queue_name = options.get("work_queue_name")
    cron = options.get("cron") or base_deploy_schedule.get("cron")
    rrule = options.get("rrule") or base_deploy_schedule.get("rrule")
    interval = options.get("interval") or base_deploy_schedule.get("interval")
    interval_anchor = options.get("interval_anchor") or base_deploy_schedule.get(
        "anchor_date"
    )
    timezone = options.get("timezone") or base_deploy_schedule.get("timezone")

    build_steps = base_deploy.get("build", project.get("build")) or []
    push_steps = base_deploy.get("push", project.get("push")) or []

    if interval_anchor and not interval:
        raise ValueError(
            "An anchor date can only be provided with an interval schedule"
        )

    if len([value for value in (cron, rrule, interval) if value is not None]) > 1:
        raise ValueError("Only one schedule type can be provided.")

    if not flow_name and not entrypoint:
        raise ValueError(
            "An entrypoint or flow name must be provided.\n\nDeploy a flow by"
            " entrypoint:\n\n\t[yellow]prefect deploy"
            " path/to/file.py:flow_function[/]\n\nDeploy a flow by"
            " name:\n\n\t[yellow]prefect project register-flow"
            " path/to/file.py:flow_function\n\tprefect deploy --flow"
            " registered-flow-name[/]\n\nYou can also provide an entrypoint or flow"
            " name in this project's prefect.yaml file."
        )
    if flow_name and entrypoint:
        raise ValueError(
            "Received an entrypoint and a flow name for this deployment. Please provide"
            " either an entrypoint or a flow name."
        )

    # flow-name and entrypoint logic
    flow = None
    if entrypoint:
        try:
            flow = await register_flow(entrypoint)
        except ModuleNotFoundError:
            raise ValueError(
                f"Could not find a flow at {entrypoint}.\n\nPlease ensure your"
                " entrypoint is in the format path/to/file.py:flow_fn_name and the"
                " file name and flow function name are correct."
            )
        except FileNotFoundError:
            if PREFECT_DEBUG_MODE:
                app.console.print(
                    "Could not find .prefect directory. Flow entrypoint will not be"
                    " registered."
                )
            flow = await run_sync_in_worker_thread(
                load_flow_from_entrypoint, entrypoint
            )
        flow_name = flow.name
    elif flow_name:
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
                f"Flow {flow_name!r} cannot be found; run\n\t[yellow]prefect project"
                " register-flow ./path/to/file.py:flow_fn_name[/yellow]\nto register"
                " its location."
            )
        with open(prefect_dir / "flows.json", "r") as f:
            flows = json.load(f)

        if flow_name not in flows:
            raise ValueError(
                f"Flow {flow_name!r} cannot be found; run\n\t[yellow]prefect project"
                " register-flow ./path/to/file.py:flow_fn_name[/yellow]\nto register"
                " its location."
            )

        # set entrypoint from prior registration
        entrypoint = flows[flow_name]

    base_deploy["flow_name"] = flow_name
    base_deploy["entrypoint"] = entrypoint

    if not name:
        if not is_interactive() or ci:
            raise ValueError("A deployment name must be provided.")
        name = prompt("Deployment name", default="default")

    ## parse parameters
    # minor optimization in case we already loaded the flow
    if not flow:
        flow = await run_sync_in_worker_thread(
            load_flow_from_entrypoint, base_deploy["entrypoint"]
        )

    base_deploy["parameter_openapi_schema"] = parameter_schema(flow)

    if param and (params is not None):
        exit_with_error("Can only pass one of `param` or `params` options")

    parameters = dict()

    if param:
        for p in param or []:
            k, unparsed_value = p.split("=", 1)
            try:
                v = json.loads(unparsed_value)
                app.console.print(
                    f"The parameter value {unparsed_value} is parsed as a JSON string"
                )
            except json.JSONDecodeError:
                v = unparsed_value
            parameters[k] = v

    if params is not None:
        parameters = json.loads(params)

    base_deploy["parameters"].update(parameters)

    # update schedule
    schedule = _construct_schedule(
        cron=cron,
        timezone=timezone,
        interval=interval,
        rrule=rrule,
        interval_anchor=interval_anchor,
        ci=ci,
    )

    variable_overrides = {}
    for variable in variables or []:
        key, value = variable.split("=", 1)
        variable_overrides[key] = value

    if work_pool_name:
        base_deploy["work_pool"]["name"] = work_pool_name
    if work_queue_name:
        base_deploy["work_pool"]["work_queue_name"] = work_queue_name

    base_deploy["work_pool"]["job_variables"].update(variable_overrides)

    # determine work pool
    if base_deploy["work_pool"]["name"]:
        try:
            work_pool = await client.read_work_pool(base_deploy["work_pool"]["name"])

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
                base_deploy["work_pool"]["name"] = await prompt_select_work_pool(
                    app.console,
                    client=client,
                )
        except ObjectNotFound:
            raise ValueError(
                "This deployment configuration references work pool"
                f" {base_deploy['work_pool']['name']!r} which does not exist. This"
                " means no worker will be able to pick up its runs. You can create a"
                " work pool in the Prefect UI."
            )
    else:
        if not is_interactive() or ci:
            raise ValueError(
                "A work pool is required to deploy this flow. Please specify a work"
                " pool name via the '--pool' flag or in your prefect.yaml file."
            )
        base_deploy["work_pool"]["name"] = await prompt_select_work_pool(
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

    # set other CLI flags
    if name:
        base_deploy["name"] = name
    if version:
        base_deploy["version"] = version
    if tags:
        base_deploy["tags"] = tags

    if description:
        base_deploy["description"] = description
    elif not base_deploy["description"]:
        base_deploy["description"] = flow.description

    ## apply templating from build and push steps to the final deployment spec
    _parameter_schema = base_deploy.pop("parameter_openapi_schema")
    base_deploy = apply_values(base_deploy, step_outputs)
    base_deploy["parameter_openapi_schema"] = _parameter_schema

    # set schedule afterwards to avoid templating errors
    base_deploy["schedule"] = schedule

    # prepare the pull step
    pull_steps = base_deploy.get(
        "pull", project.get("pull")
    ) or await _generate_default_pull_action(
        app.console,
        base_deploy=base_deploy,
        ci=ci,
    )
    pull_steps = apply_values(pull_steps, step_outputs)

    flow_id = await client.create_flow_from_name(base_deploy["flow_name"])

    deployment_id = await client.create_deployment(
        flow_id=flow_id,
        name=base_deploy["name"],
        work_queue_name=base_deploy["work_pool"]["work_queue_name"],
        work_pool_name=base_deploy["work_pool"]["name"],
        version=base_deploy["version"],
        schedule=base_deploy["schedule"],
        parameters=base_deploy["parameters"],
        description=base_deploy["description"],
        tags=base_deploy["tags"],
        path=base_deploy.get("path"),
        entrypoint=base_deploy["entrypoint"],
        parameter_openapi_schema=base_deploy["parameter_openapi_schema"].dict(),
        pull_steps=pull_steps,
        infra_overrides=base_deploy["work_pool"]["job_variables"],
    )

    app.console.print(
        Panel(
            f"Deployment '{base_deploy['flow_name']}/{base_deploy['name']}'"
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
            base_deploy,
            build_steps=build_steps or None,
            push_steps=push_steps or None,
            pull_steps=pull_steps or None,
        )
        app.console.print(
            (
                "\n[green]Deployment configuration saved to prefect.yaml![/] You can"
                " now deploy using this deployment configuration with:\n\n\t[blue]$"
                f" prefect deploy -n {base_deploy['name']}[/]\n\nYou can also make"
                " changes to this deployment configuration by making changes to the"
                " prefect.yaml file."
            ),
        )

    app.console.print(
        "\nTo execute flow runs from this deployment, start a worker in a"
        " separate terminal that pulls work from the"
        f" {base_deploy['work_pool']['name']!r} work pool:"
    )
    app.console.print(
        f"\n\t$ prefect worker start --pool {base_deploy['work_pool']['name']!r}",
        style="blue",
    )
    app.console.print(
        "\nTo schedule a run for this deployment, use the following command:"
    )
    app.console.print(
        (
            "\n\t$ prefect deployment run"
            f" '{base_deploy['flow_name']}/{base_deploy['name']}'\n"
        ),
        style="blue",
    )


async def _run_multi_deploy(
    base_deploys, project, names=None, deploy_all=False, ci=False
):
    base_deploys = deepcopy(base_deploys) if base_deploys else []
    project = deepcopy(project) if project else {}
    names = names or []

    if deploy_all:
        app.console.print("Deploying all deployments for current project...")
        for base_deploy in base_deploys:
            if base_deploy.get("name") is None:
                if not is_interactive() or ci:
                    app.console.print(
                        "Discovered unnamed deployment. Skipping...", style="yellow"
                    )
                    continue
                app.console.print("Discovered unnamed deployment.", style="yellow")
                app.console.print_json(data=base_deploy)
                if confirm(
                    "Would you like to give this deployment a name and deploy it?",
                    default=True,
                    console=app.console,
                ):
                    base_deploy["name"] = prompt("Deployment name", default="default")
                else:
                    app.console.print("Skipping unnamed deployment.", style="yellow")
                    continue
            app.console.print(Panel(f"Deploying {base_deploy['name']}", style="blue"))
            await _run_single_deploy(base_deploy, project, ci=ci)
    else:
        picked_base_deploys = [
            base_deploy for base_deploy in base_deploys if base_deploy["name"] in names
        ]
        if len(picked_base_deploys) != len(names):
            missing_deployments = set(names).difference(
                base_deploy["name"] for base_deploy in picked_base_deploys
            )
            app.console.print(
                (
                    "The following deployment(s) could not be found and will not be"
                    f" deployed: {' ,'.join(missing_deployments)}"
                ),
                style="yellow",
            )
        app.console.print("Deploying selected deployments for current project...")
        for base_deploy in picked_base_deploys:
            app.console.print(Panel(f"Deploying {base_deploy['name']}", style="blue"))
            await _run_single_deploy(base_deploy, project, ci=ci)


def _construct_schedule(
    cron: Optional[str] = None,
    timezone: Optional[str] = None,
    interval: Optional[int] = None,
    interval_anchor: Optional[str] = None,
    rrule: Optional[str] = None,
    ci: bool = False,
):
    schedule = None
    if cron:
        cron_kwargs = {"cron": cron, "timezone": timezone}
        schedule = CronSchedule(
            **{k: v for k, v in cron_kwargs.items() if v is not None}
        )
    elif interval:
        interval_kwargs = {
            "interval": timedelta(seconds=interval),
            "anchor_date": interval_anchor,
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


def _merge_with_default_deployment(base_deploy: Dict):
    """
    Merge a base deployment dictionary with the default deployment dictionary.
    If a key is missing in the base deployment, it will be filled with the
    corresponding value from the default deployment.

    Parameters:
        base_deploy: The base deployment dictionary to be merged with
        the default deployment.

    Returns:
        The merged deployment dictionary.
    """
    base_deploy = deepcopy(base_deploy)
    DEFAULT_DEPLOYMENT = {
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

    # merge default and base deployment
    # this allows for missing keys in a user's deployment file
    for key, value in DEFAULT_DEPLOYMENT.items():
        if key not in base_deploy:
            base_deploy[key] = value
        if isinstance(value, dict):
            for k, v in value.items():
                if k not in base_deploy[key]:
                    base_deploy[key][k] = v

    return base_deploy


async def _generate_default_pull_action(
    console: Console, base_deploy: Dict, ci: bool = False
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
            token_secret_block_name = f"deployment-{slugify(base_deploy['name'])}-{slugify(base_deploy['flow_name'])}-repo-token"
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
            git_clone_step["prefect.deployments.steps.git_clone"]["token"] = (
                "{{ prefect.blocks.secret." + token_secret_block_name + " }}"
            )

        return [git_clone_step]
    else:
        entrypoint_path, _ = base_deploy["entrypoint"].split(":")
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

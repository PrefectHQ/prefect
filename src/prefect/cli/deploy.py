"""Module containing implementation for deploying projects."""
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from rich.console import Console

import typer
import typer.core
import yaml
from rich.panel import Panel

import prefect
from prefect.client.collections import get_collections_metadata_client
from prefect.client.orchestration import PrefectClient
from prefect.client.utilities import inject_client
import prefect.context
from prefect.logging.loggers import get_logger
from prefect.server.schemas.actions import WorkPoolCreate
import prefect.settings
from prefect.cli._utilities import exit_with_error, prompt
from prefect.cli.root import app, is_interactive
from prefect.exceptions import ObjectNotFound
from prefect.flows import load_flow_from_entrypoint
from prefect.projects import find_prefect_directory, register_flow
from prefect.projects.steps import run_step
from prefect.server.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.settings import PREFECT_DEBUG_MODE, PREFECT_UI_URL
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.callables import parameter_schema
from prefect.utilities.templating import apply_values
from prefect.cli._utilities import prompt_select_from_table


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
):
    """
    Deploy a flow from this project by creating a deployment.

    Should be run from a project root directory.
    """

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

    try:
        with open("prefect.yaml", "r") as f:
            project = yaml.safe_load(f)
    except FileNotFoundError:
        app.console.print(
            "We were unable to find a prefect.yaml file in the current directory.",
            style="red",
        )
        app.console.print(
            "\nTo get started deploying flows please initialize a new project:",
            style="red",
        )
        app.console.print("\n\t$ prefect project init\n", style="blue")
        raise typer.Exit(1)

    try:
        with open("deployment.yaml", "r") as f:
            base_deploy = yaml.safe_load(f)
            if not base_deploy:
                deployments = []
            elif base_deploy.get("deployments"):
                deployments = base_deploy["deployments"]
            else:
                deployments = [base_deploy]
    except FileNotFoundError:
        app.console.print(
            "No deployment.yaml file found, only provided CLI options will be used.",
            style="yellow",
        )
        deployments = []

    try:
        if len(deployments) > 1:
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
                )
            elif len(names) == 1:
                deployment = next(
                    (d for d in deployments if d.get("name") == names[0]), {}
                )
                if not deployment:
                    app.console.print(
                        (
                            "Could not find deployment declaration with name "
                            f"{names[0]} in deployment.yaml. Only CLI options "
                            "will be used for this deployment."
                        ),
                        style="yellow",
                    )
                    options["name"] = names[0]
                await _run_single_deploy(
                    base_deploy=deployment,
                    project=project,
                    options=options,
                )
            else:
                if not is_interactive():
                    exit_with_error(
                        "Discovered multiple deployments declared in deployment.yaml,"
                        " but no name was given. Please specify the name of at least"
                        " one deployment to create or update."
                    )
                selected_deployment = prompt_select_from_table(
                    app.console,
                    "Which deployment would you like to create or update?",
                    [
                        {"header": "Deployment Name", "key": "name"},
                        {"header": "Description", "key": "description"},
                    ],
                    [
                        deployment
                        for deployment in deployments
                        if deployment.get("name")
                    ],
                )
                await _run_single_deploy(
                    base_deploy=selected_deployment,
                    project=project,
                    options=options,
                )
        elif len(deployments) <= 1:
            if len(names) > 1:
                exit_with_error(
                    "Multiple deployment names were provided, but only one deployment"
                    " was found in deployment.yaml. Please provide a single deployment"
                    " name."
                )
            else:
                options["name"] = names[0] if names else None
                await _run_single_deploy(
                    base_deploy=deployments[0] if deployments else {},
                    project=project,
                    options=options,
                )
    except ValueError as exc:
        exit_with_error(str(exc))


async def _run_single_deploy(
    base_deploy: Dict, project: Dict, options: Optional[Dict] = None
):
    base_deploy = deepcopy(base_deploy) if base_deploy else {}
    project = deepcopy(project) if project else {}
    options = deepcopy(options) if options else {}

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

    build_steps = base_deploy.get("build", project.get("build", [])) or []
    pull_steps = base_deploy.get("pull", project.get("pull", [])) or []
    push_steps = base_deploy.get("push", project.get("push", [])) or []

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
            " name in this project's deployment.yaml file."
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
        flow_name = flow.name
    elif flow_name:
        prefect_dir = find_prefect_directory()
        if not prefect_dir:
            raise ValueError(
                "No .prefect directory could be found - run [yellow]`prefect project"
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
        if not is_interactive():
            raise ValueError("A deployment name must be provided.")
        name = prompt("Deployment name")

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

    ## RUN BUILD AND PUSH STEPS
    step_outputs = {}
    if build_steps:
        app.console.print("Running deployment build steps...")
    step_outputs.update(await _run_steps(build_steps, step_outputs))

    if push_steps:
        app.console.print("Running deployment push steps...")
    step_outputs.update(await _run_steps(push_steps, step_outputs))

    variable_overrides = {}
    for variable in variables or []:
        key, value = variable.split("=", 1)
        variable_overrides[key] = value

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

    if work_pool_name:
        base_deploy["work_pool"]["name"] = work_pool_name
    if work_queue_name:
        base_deploy["work_pool"]["work_queue_name"] = work_queue_name

    base_deploy["work_pool"]["job_variables"].update(variable_overrides)

    ## apply templating from build and push steps to the final deployment spec
    _parameter_schema = base_deploy.pop("parameter_openapi_schema")
    base_deploy = apply_values(base_deploy, step_outputs)
    base_deploy["parameter_openapi_schema"] = _parameter_schema

    # set schedule afterwards to avoid templating errors
    base_deploy["schedule"] = schedule

    # prepare the pull step
    pull_steps = apply_values(pull_steps, step_outputs)

    async with prefect.get_client() as client:
        flow_id = await client.create_flow_from_name(base_deploy["flow_name"])

        if base_deploy["work_pool"]["name"]:
            try:
                work_pool = await client.read_work_pool(
                    base_deploy["work_pool"]["name"]
                )

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
                    base_deploy["work_pool"]["name"] = await _prompt_select_work_pool(
                        app.console,
                        client=client,
                    )
            except ObjectNotFound:
                app.console.print(
                    (
                        "\nThis deployment references a work pool that does not exist."
                        " This means no worker will be able to pick up its runs. You"
                        " can create a work pool in the Prefect UI."
                    ),
                    style="red",
                )
        else:
            if not is_interactive():
                raise ValueError(
                    "A work pool is required to deploy this flow. Please specify a work"
                    " pool name via the '--pool' flag or in your deployment.yaml file."
                )
            base_deploy["work_pool"]["name"] = await _prompt_select_work_pool(
                console=app.console, client=client
            )

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
            (
                f"Deployment '{base_deploy['flow_name']}/{base_deploy['name']}'"
                f" successfully created with id '{deployment_id}'."
            ),
            style="green",
        )

        if PREFECT_UI_URL:
            app.console.print(
                "View Deployment in UI:"
                f" {PREFECT_UI_URL.value()}/deployments/deployment/{deployment_id}"
            )

        if base_deploy["work_pool"]["name"] is not None:
            app.console.print(
                "\nTo execute flow runs from this deployment, start a worker that"
                f" pulls work from the {base_deploy['work_pool']['name']!r} work pool:"
            )
            app.console.print(
                (
                    "\n\t$ prefect worker start --pool"
                    f" {base_deploy['work_pool']['name']!r}\n"
                ),
                style="blue",
            )
        else:
            app.console.print(
                (
                    "\nThis deployment does not specify a work pool or queue, which"
                    " means no worker will be able to pick up its runs. To add a"
                    " work pool, edit the deployment spec and re-run this command,"
                    " or visit the deployment in the UI."
                ),
                style="red",
            )


async def _run_multi_deploy(base_deploys, project, names=None, deploy_all=False):
    base_deploys = deepcopy(base_deploys) if base_deploys else []
    project = deepcopy(project) if project else {}
    names = names or []

    if deploy_all:
        app.console.print("Deploying all deployments for current project...")
        for base_deploy in base_deploys:
            if base_deploy.get("name") is None:
                if not is_interactive():
                    app.console.print(
                        "Discovered unnamed deployment. Skipping...", style="yellow"
                    )
                app.console.print("Discovered unnamed deployment.", style="yellow")
                app.console.print_json(data=base_deploy)
                if typer.confirm(
                    "Would you like to give this deployment a name and deploy it?"
                ):
                    base_deploy["name"] = prompt("Deployment name")
                else:
                    app.console.print("Skipping unnamed deployment.", style="yellow")
                    continue
            app.console.print(Panel(f"Deploying {base_deploy['name']}", style="blue"))
            await _run_single_deploy(base_deploy, project)
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
            await _run_single_deploy(base_deploy, project)


@inject_client
async def _prompt_select_work_pool(
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
        work_pool = await _prompt_create_work_pool(console, client=client)
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
async def _prompt_create_work_pool(
    console: Console,
    client: PrefectClient = None,
):
    if not typer.confirm(
        (
            "Looks like you don't have any work pools this flow can be deployed to."
            " Would you like to create one?"
        ),
        default=True,
    ):
        raise ValueError(
            "A work pool is required to deploy this flow. Please specify a work pool"
            " name via the '--pool' flag or in your deployment.yaml file."
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


async def _run_steps(
    steps: List[Dict[str, Any]],
    step_outputs: Dict[str, Any],
):
    step_outputs = deepcopy(step_outputs)
    for step in steps:
        step_name = list(step.keys())[0].split(".")[-1]
        try:
            app.console.print(f" > Running [blue]{step_name}[/] step...")
        except Exception:
            if PREFECT_DEBUG_MODE:
                get_logger().warning(
                    "Step has unexpected structure: %s", step, exc_info=True
                )
        step_outputs.update(await run_step(step))
    return step_outputs


DEFAULT_DEPLOYMENT = None


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
    global DEFAULT_DEPLOYMENT

    if DEFAULT_DEPLOYMENT is None:
        # load the default deployment file for key consistency
        default_file = (
            Path(__file__).parent.parent / "projects" / "templates" / "deployment.yaml"
        )

        # load default file
        with open(default_file, "r") as df:
            contents = yaml.safe_load(df)
            DEFAULT_DEPLOYMENT = contents["deployments"][0]

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

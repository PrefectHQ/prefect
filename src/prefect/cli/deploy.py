"""Module containing implementation for deploying projects."""
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import typer
import typer.core
import yaml
from pydantic import BaseModel, Field
from rich.panel import Panel

import prefect
import prefect.context
import prefect.settings
from prefect import Flow
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.exceptions import ObjectNotFound
from prefect.flows import load_flow_from_entrypoint
from prefect.projects import find_prefect_directory, register_flow
from prefect.projects.steps import run_step
from prefect.server.schemas.actions import DeploymentCreate
from prefect.server.schemas.schedules import (
    SCHEDULE_TYPES,
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.callables import parameter_schema
from prefect.utilities.templating import apply_values


class BaseProjectConfiguration(BaseModel):
    """
    Model representing the contents of a project's prefect.yaml file
    """

    name: Optional[str] = Field(default=None)
    prefect_version: Optional[str] = Field(default=None)
    build: Optional[List[Dict[str, Any]]] = Field(default=None)
    push: Optional[List[Dict[str, Any]]] = Field(default=None)
    pull: Optional[List[Dict[str, Any]]] = Field(default=None)


class BaseDeploymentWorkPoolConfiguration(BaseModel):
    """
    Model representing the work pool configuration for a deployment
    declared in a project's deployment.yaml file
    """

    name: Optional[str] = Field(default=None)
    work_queue_name: Optional[str] = Field(default=None)
    job_variables: Dict[str, Any] = Field(default_factory=dict)


class BaseDeploymentConfiguration(BaseModel):
    """
    Model representing a deployment declared in a project's deployment.yaml file

    Fields can be strings to accommodate templating
    """

    name: Optional[str] = Field(default=None)
    version: Optional[str] = Field(default=None)
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = Field(default=None)
    schedule: Optional[Union[CronSchedule, IntervalSchedule, RRuleSchedule, str]] = (
        Field(default=None)
    )
    flow_name: Optional[str] = Field(default=None)
    entrypoint: Optional[str] = Field(default=None)
    parameters: Union[Dict[str, Any], str] = Field(default_factory=dict)
    work_pool: Union[BaseDeploymentWorkPoolConfiguration, str] = Field(
        default_factory=BaseDeploymentWorkPoolConfiguration
    )
    build: Optional[Union[List[Dict[str, Any]], str]] = Field(default=None)
    push: Optional[Union[List[Dict[str, Any]], str]] = Field(default=None)
    pull: Optional[Union[List[Dict[str, Any]], str]] = Field(default=None)


class DeployCliOptions(BaseModel):
    """
    Model representing the options passed to the `prefect deploy` command
    """

    entrypoint: Optional[str] = Field(default=None)
    flow_name: Optional[str] = Field(default=None)
    names: List[str] = Field(default_factory=list)
    description: Optional[str] = Field(default=None)
    version: Optional[str] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)
    work_pool_name: Optional[str] = Field(default=None)
    work_queue_name: Optional[str] = Field(default=None)
    variables: Optional[List[str]] = Field(default=None)
    cron: Optional[str] = Field(default=None)
    interval: Optional[int] = Field(default=None)
    interval_anchor: Optional[str] = Field(default=None)
    rrule: Optional[str] = Field(default=None)
    timezone: Optional[str] = Field(default=None)
    param: Optional[List[str]] = Field(default=None)
    params: Optional[str] = Field(default=None)
    deploy_all: bool = Field(default=False)

    def any_non_default_values(self) -> bool:
        return self != self.__class__()


def _load_base_project_configuration() -> BaseProjectConfiguration:
    """
    Loads the base project configuration from the prefect directory.
    """
    prefect_dir = find_prefect_directory()
    if not prefect_dir:
        raise FileNotFoundError("Could not find a prefect directory.")
    base_project_config_path = prefect_dir.parent / "prefect.yaml"

    if not base_project_config_path.exists():
        return BaseProjectConfiguration()
    with open(base_project_config_path, "r") as f:
        raw_base_project_config = yaml.safe_load(f)
        # Handle the case where the user has a hyphen instead of an underscore
        if "prefect-version" in raw_base_project_config:
            raw_base_project_config["prefect_version"] = raw_base_project_config.pop(
                "prefect-version"
            )
        base_project_config = BaseProjectConfiguration(**raw_base_project_config)
    return base_project_config


def _load_base_deployment_configurations() -> (
    Optional[List[BaseDeploymentConfiguration]]
):
    """
    Loads the base deployment configuration from a project's deployment.yaml file.

    Returns a list of deployment configurations discovered in the file.

    Returns None if the file does not exist.
    """
    prefect_dir = find_prefect_directory()
    if not prefect_dir:
        raise FileNotFoundError("Could not find a prefect directory.")
    base_deploy_config_path = prefect_dir.parent / "deployment.yaml"

    if not base_deploy_config_path.exists():
        return None
    with open(base_deploy_config_path, "r") as f:
        deployment_file_contents = yaml.safe_load(f)

    base_project_config = _load_base_project_configuration()
    base_actions = base_project_config.dict(include={"build", "push", "pull"})

    if not deployment_file_contents.get("deployments"):
        raw_base_deployment_configs = [deployment_file_contents]
    else:
        raw_base_deployment_configs = deployment_file_contents["deployments"]

    # Default to project base actions, but allow deployment to override
    return [
        BaseDeploymentConfiguration(**{**base_actions, **raw_base_deployment_config})
        for raw_base_deployment_config in raw_base_deployment_configs
    ]


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
    names: Optional[List[str]] = typer.Option(
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

    options = DeployCliOptions(
        entrypoint=entrypoint,
        flow_name=flow_name,
        names=names or [],
        description=description,
        version=version,
        tags=tags,
        work_pool_name=work_pool_name,
        work_queue_name=work_queue_name,
        variables=variables,
        cron=cron,
        interval=interval,
        interval_anchor=interval_anchor,
        rrule=rrule,
        timezone=timezone,
        param=param,
        params=params,
        deploy_all=deploy_all,
    )

    base_deploys = _load_base_deployment_configurations()
    if base_deploys is None:
        app.console.print(
            "No deployment.yaml file found, only provided CLI options will be used.",
            style="yellow",
        )
        base_deploys = [BaseDeploymentConfiguration()]
    try:
        if len(base_deploys) > 1:
            if deploy_all or len(options.names) > 1:
                if options.any_non_default_values():
                    app.console.print(
                        (
                            "You have passed options to the deploy command, but you are"
                            " creating or updating multiple deployments. These options"
                            " will be ignored."
                        ),
                        style="yellow",
                    )
                await _run_multi_deploy(
                    base_deploys=base_deploys,
                    names=options.names,
                    deploy_all=options.deploy_all,
                )
            elif len(options.names) == 1:
                base_deploy = next(
                    (d for d in base_deploys if d.name == options.names[0]), {}
                )
                await _run_single_deploy(
                    base_deploy=base_deploy,
                    options=options,
                )
            else:
                exit_with_error(
                    "Discovered multiple deployments declared in deployment.yaml, "
                    "but no name was given. Please specify the name of at least one "
                    "deployment to create or update."
                )
        elif len(base_deploys) <= 1:
            if len(options.names) > 1:
                exit_with_error(
                    "Multiple deployment names were provided, but only one deployment"
                    " was found in deployment.yaml. Please provide a single deployment"
                    " name."
                )
            else:
                base_deploys[0].name = options.names[0] if names else None
                await _run_single_deploy(
                    base_deploy=base_deploys[0],
                    options=options,
                )
    except Exception as exc:
        exit_with_error(str(exc))


def _generate_schedule_from_options(
    options: DeployCliOptions,
) -> Optional[SCHEDULE_TYPES]:
    if options.interval_anchor and not options.interval:
        raise ValueError(
            "An anchor date can only be provided with an interval schedule"
        )

    if (
        len(
            [
                value
                for value in (options.cron, options.rrule, options.interval)
                if value is not None
            ]
        )
        > 1
    ):
        raise ValueError("Only one schedule type can be provided.")

    if options.cron:
        cron_kwargs = {"cron": options.cron, "timezone": options.timezone}
        schedule = CronSchedule(
            **{k: v for k, v in cron_kwargs.items() if v is not None}
        )
    elif options.interval:
        interval_kwargs = {
            "interval": timedelta(seconds=options.interval),
            "anchor_date": options.interval_anchor,
            "timezone": options.timezone,
        }
        schedule = IntervalSchedule(
            **{k: v for k, v in interval_kwargs.items() if v is not None}
        )
    elif options.rrule:
        try:
            schedule = RRuleSchedule(**json.loads(options.rrule))
            if options.timezone:
                # override timezone if specified via CLI argument
                schedule.timezone = options.timezone
        except json.JSONDecodeError:
            schedule = RRuleSchedule(rrule=options.rrule, timezone=options.timezone)
    else:
        return None


def _generate_parameters_from_options(options: DeployCliOptions):
    if options.param and (options.params is not None):
        raise ValueError("Can only pass one of `param` or `params` options")

    parameters = dict()

    if options.param:
        for p in options.param or []:
            k, unparsed_value = p.split("=", 1)
            try:
                v = json.loads(unparsed_value)
                app.console.print(
                    f"The parameter value {unparsed_value} is parsed as a JSON string"
                )
            except json.JSONDecodeError:
                v = unparsed_value
            parameters[k] = v

    if options.params is not None:
        parameters = json.loads(options.params)

    return parameters


async def _load_flow(
    flow_name: Optional[str] = None, entrypoint: Optional[str] = None
) -> Tuple[Flow, str]:
    if flow_name and entrypoint:
        raise ValueError("Can only pass an entrypoint or a flow name but not both.")

    # flow-name and entrypoint logic
    flow = None
    if entrypoint:
        flow = await register_flow(entrypoint)
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
                f"Flow {flow_name!r} cannot be found; run\n    [yellow]prefect project"
                " register-flow ./path/to/file.py:flow_fn_name[/yellow]\nto register"
                " its location."
            )
        with open(prefect_dir / "flows.json", "r") as f:
            flows: Dict[str, str] = json.load(f)

        if flow_name not in flows:
            raise ValueError(
                f"Flow {flow_name!r} cannot be found; run\n    [yellow]prefect project"
                " register-flow ./path/to/file.py:flow_fn_name[/yellow]\nto register"
                " its location."
            )

        # set entrypoint from prior registration
        entrypoint = flows[flow_name]
    else:
        raise ValueError("An entrypoint or flow name must be provided.")

    if not flow:
        flow = await run_sync_in_worker_thread(load_flow_from_entrypoint, entrypoint)

    return flow, entrypoint


async def _generate_deployment_create(
    base_deploy: BaseDeploymentConfiguration,
    options: DeployCliOptions,
    flow: Flow,
    entrypoint: str,
) -> DeploymentCreate:
    if not base_deploy.name:
        raise ValueError("A deployment name must be provided.")

    schedule = _generate_schedule_from_options(options) or base_deploy.schedule
    if isinstance(schedule, str):
        raise ValueError("Unable to parse schedule. Please check your syntax.")
    parameters = _generate_parameters_from_options(options) or base_deploy.parameters
    if isinstance(parameters, str):
        raise ValueError("Unable to parse parameters. Please check your syntax.")
    if isinstance(base_deploy.work_pool, str):
        raise ValueError("Unable to parse work_pool. Please check your syntax.")
    if isinstance(base_deploy.pull, str):
        raise ValueError("Unable to parse pull action. Please check your syntax.")

    variable_overrides = {}
    for variable in options.variables or []:
        key, value = variable.split("=", 1)
        variable_overrides[key] = value

    return DeploymentCreate(
        # flow_id=flow_id,
        name=base_deploy.name,
        work_queue_name=options.work_queue_name
        or base_deploy.work_pool.work_queue_name,
        work_pool_name=options.work_pool_name or base_deploy.work_pool.name,
        version=options.version or base_deploy.version,
        schedule=schedule,
        parameters=parameters,
        description=options.description or base_deploy.description,
        tags=options.tags or base_deploy.tags,
        entrypoint=entrypoint,
        parameter_openapi_schema=parameter_schema(flow).dict(),
        pull_steps=base_deploy.pull,
        infra_overrides={**base_deploy.work_pool.job_variables, **variable_overrides},
    )


async def _run_build_and_push_steps(base_deploy: BaseDeploymentConfiguration):
    step_outputs = {}
    build_steps = base_deploy.build or []
    push_steps = base_deploy.push or []
    for step in build_steps + push_steps:
        step_outputs.update(await run_step(step))

    return step_outputs


def _apply_step_outputs_to_base_deployment_config(
    base_deploy: BaseDeploymentConfiguration, step_outputs: Dict[str, Any]
) -> BaseDeploymentConfiguration:
    base_deploy_dict = base_deploy.dict()
    updated_deployment_create_dict: Dict[str, Any] = apply_values(
        base_deploy_dict, step_outputs
    )
    return base_deploy.copy(update=updated_deployment_create_dict)


async def _run_single_deploy(
    base_deploy: BaseDeploymentConfiguration, options: Optional[DeployCliOptions] = None
):
    options = options or DeployCliOptions()

    flow, entrypoint = await _load_flow(
        flow_name=options.flow_name or base_deploy.flow_name,
        entrypoint=options.entrypoint or base_deploy.entrypoint,
    )

    step_outputs = await _run_build_and_push_steps(base_deploy)

    base_deploy = _apply_step_outputs_to_base_deployment_config(
        base_deploy, step_outputs
    )
    deployment_create = await _generate_deployment_create(
        base_deploy, options, flow, entrypoint
    )

    async with prefect.get_client() as client:
        flow_id = await client.create_flow_from_name(flow.name)
        deployment_create.flow_id = flow_id

        if deployment_create.work_pool_name:
            try:
                work_pool = await client.read_work_pool(
                    deployment_create.work_pool_name
                )

                # dont allow submitting to prefect-agent typed work pools
                if work_pool.type == "prefect-agent":
                    exit_with_error(
                        "Cannot deploy project with work pool of type 'prefect-agent'."
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

        deployment_id = await client.create_deployment(
            **deployment_create.dict(exclude_unset=True)
        )

        app.console.print(
            (
                f"Deployment '{flow.name}/{deployment_create.name}'"
                f" successfully created with id '{deployment_id}'."
            ),
            style="green",
        )

        if PREFECT_UI_URL:
            app.console.print(
                "View Deployment in UI:"
                f" {PREFECT_UI_URL.value()}/deployments/deployment/{deployment_id}"
            )

        if deployment_create.work_pool_name is not None:
            app.console.print(
                "\nTo execute flow runs from this deployment, start a worker that"
                f" pulls work from the {deployment_create.work_pool_name!r} work pool"
            )
        elif deployment_create.work_queue_name is not None:
            app.console.print(
                "\nTo execute flow runs from this deployment, start a worker that"
                " pulls work from the"
                f" {deployment_create.work_queue_name!r} work queue"
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


async def _run_multi_deploy(
    base_deploys: List[BaseDeploymentConfiguration],
    names: List[str],
    deploy_all: bool = False,
):
    names = names or []

    if deploy_all:
        app.console.print("Deploying all deployments for current project...")
        for base_deploy in base_deploys:
            if base_deploy.name is None:
                app.console.print(
                    "Discovered deployment with no name. Skipping...", style="yellow"
                )
                continue
            app.console.print(Panel(f"Deploying {base_deploy.name}", style="blue"))
            await _run_single_deploy(base_deploy)
    else:
        picked_base_deploys = [
            base_deploy for base_deploy in base_deploys if base_deploy.name in names
        ]
        if len(picked_base_deploys) != len(names):
            missing_deployments = set(names).difference(
                base_deploy.name for base_deploy in picked_base_deploys
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
            app.console.print(Panel(f"Deploying {base_deploy.name}", style="blue"))
            await _run_single_deploy(base_deploy)

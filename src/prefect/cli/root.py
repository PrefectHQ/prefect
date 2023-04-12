"""
Base `prefect` command-line application
"""
import asyncio
import json
import platform
import sys
from datetime import timedelta
from pathlib import Path
from typing import List, Optional

import pendulum
import rich.console
import typer
import typer.core
import yaml

import prefect
import prefect.context
import prefect.settings
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, with_cli_exception_handling
from prefect.client.orchestration import ServerType
from prefect.exceptions import ObjectNotFound
from prefect.flows import load_flow_from_entrypoint
from prefect.logging.configuration import setup_logging
from prefect.projects import find_prefect_directory, register_flow
from prefect.projects.steps import run_step
from prefect.server.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.settings import (
    PREFECT_CLI_COLORS,
    PREFECT_CLI_WRAP_LINES,
    PREFECT_TEST_MODE,
    PREFECT_UI_URL,
)
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.callables import parameter_schema
from prefect.utilities.templating import apply_values

app = PrefectTyper(add_completion=False, no_args_is_help=True)


def version_callback(value: bool):
    if value:
        print(prefect.__version__)
        raise typer.Exit()


def is_interactive():
    return app.console.is_interactive


@app.callback()
@with_cli_exception_handling
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        # A callback is necessary for Typer to call this without looking for additional
        # commands and erroring when excluded
        callback=version_callback,
        help="Display the current version.",
        is_eager=True,
    ),
    profile: str = typer.Option(
        None,
        "--profile",
        "-p",
        help="Select a profile for this CLI run.",
        is_eager=True,
    ),
):
    if profile and not prefect.context.get_settings_context().profile.name == profile:
        # Generally, the profile should entered by `enter_root_settings_context`.
        # In the cases where it is not (i.e. CLI testing), we will enter it here.
        settings_ctx = prefect.context.use_profile(
            profile, override_environment_variables=True
        )
        try:
            ctx.with_resource(settings_ctx)
        except KeyError:
            print(f"Unknown profile {profile!r}.")
            exit(1)

    # Configure the output console after loading the profile

    app.console = rich.console.Console(
        highlight=False,
        color_system="auto" if PREFECT_CLI_COLORS else None,
        # `soft_wrap` disables wrapping when `True`
        soft_wrap=not PREFECT_CLI_WRAP_LINES.value(),
    )

    if not PREFECT_TEST_MODE:
        # When testing, this entrypoint can be called multiple times per process which
        # can cause logging configuration conflicts. Logging is set up in conftest
        # during tests.
        setup_logging()

    # When running on Windows we need to ensure that the correct event loop policy is
    # in place or we will not be able to spawn subprocesses. Sometimes this policy is
    # changed by other libraries, but here in our CLI we should have ownership of the
    # process and be able to safely force it to be the correct policy.
    # https://github.com/PrefectHQ/prefect/issues/8206
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@app.command()
async def version():
    """Get the current Prefect version."""
    import sqlite3

    from prefect.server.api.server import SERVER_API_VERSION
    from prefect.server.utilities.database import get_dialect
    from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL

    version_info = {
        "Version": prefect.__version__,
        "API version": SERVER_API_VERSION,
        "Python version": platform.python_version(),
        "Git commit": prefect.__version_info__["full-revisionid"][:8],
        "Built": pendulum.parse(
            prefect.__version_info__["date"]
        ).to_day_datetime_string(),
        "OS/Arch": f"{sys.platform}/{platform.machine()}",
        "Profile": prefect.context.get_settings_context().profile.name,
    }

    server_type: str

    try:
        async with prefect.get_client() as client:
            server_type = client.server_type.value
    except Exception:
        server_type = "<client error>"

    version_info["Server type"] = server_type.lower()

    # TODO: Consider adding an API route to retrieve this information?
    if server_type == ServerType.EPHEMERAL.value:
        database = get_dialect(PREFECT_API_DATABASE_CONNECTION_URL.value()).name
        version_info["Server"] = {"Database": database}
        if database == "sqlite":
            version_info["Server"]["SQLite version"] = sqlite3.sqlite_version

    def display(object: dict, nesting: int = 0):
        # Recursive display of a dictionary with nesting
        for key, value in object.items():
            key += ":"
            if isinstance(value, dict):
                app.console.print(key)
                return display(value, nesting + 2)
            prefix = " " * nesting
            app.console.print(f"{prefix}{key.ljust(20 - len(prefix))} {value}")

    display(version_info)


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
    name: str = typer.Option(
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
):
    """
    Deploy a flow from this project by creating a deployment.

    Should be run from a project root directory.
    """
    if len([value for value in (cron, rrule, interval) if value is not None]) > 1:
        exit_with_error("Only one schedule type can be provided.")

    if interval_anchor and not interval:
        exit_with_error("An anchor date can only be provided with an interval schedule")

    # load the default deployment file for key consistency
    default_file = (
        Path(__file__).parent.parent / "projects" / "templates" / "deployment.yaml"
    )

    # load default file
    with open(default_file, "r") as df:
        default_deployment = yaml.safe_load(df)

    try:
        with open("deployment.yaml", "r") as f:
            base_deploy = yaml.safe_load(f)
    except FileNotFoundError:
        app.console.print(
            "No deployment.yaml file found, only provided CLI options will be used.",
            style="yellow",
        )
        base_deploy = {}

    # merge default and base deployment
    # this allows for missing keys in a user's deployment file
    for key, value in default_deployment.items():
        if key not in base_deploy:
            base_deploy[key] = value
        if isinstance(value, dict):
            for k, v in value.items():
                if k not in base_deploy[key]:
                    base_deploy[key][k] = v

    with open("prefect.yaml", "r") as f:
        project = yaml.safe_load(f)

    # sanitize
    if project.get("build") is None:
        project["build"] = []
    if project.get("push") is None:
        project["push"] = []
    if project.get("pull") is None:
        project["pull"] = []

    if (
        not flow_name
        and not base_deploy.get("flow_name")
        and not entrypoint
        and not base_deploy.get("entrypoint")
    ):
        exit_with_error("An entrypoint or flow name must be provided.")
    if not name and not base_deploy.get("name"):
        exit_with_error("A deployment name must be provided.")
    if (flow_name or base_deploy.get("flow_name")) and (
        entrypoint or base_deploy.get("entrypoint")
    ):
        exit_with_error("Can only pass an entrypoint or a flow name but not both.")

    # Pull from deployment config if not passed
    if entrypoint is None:
        entrypoint = base_deploy.get("entrypoint")
    if flow_name is None:
        flow_name = base_deploy.get("flow_name")

    # flow-name and entrypoint logic
    flow = None
    if entrypoint:
        flow = await register_flow(entrypoint)
        flow_name = flow.name
    elif flow_name:
        prefect_dir = find_prefect_directory()
        if not prefect_dir:
            exit_with_error(
                "No .prefect directory could be found - run [yellow]`prefect project"
                " init`[/yellow] to create one."
            )
        if not (prefect_dir / "flows.json").exists():
            exit_with_error(
                f"Flow {flow_name!r} cannot be found; run\n    [yellow]prefect project"
                " register-flow ./path/to/file.py:flow_fn_name[/yellow]\nto register"
                " its location."
            )
        with open(prefect_dir / "flows.json", "r") as f:
            flows = json.load(f)

        if flow_name not in flows:
            exit_with_error(
                f"Flow {flow_name!r} cannot be found; run\n    [yellow]prefect project"
                " register-flow ./path/to/file.py:flow_fn_name[/yellow]\nto register"
                " its location."
            )

        # set entrypoint from prior registration
        entrypoint = flows[flow_name]

    base_deploy["flow_name"] = flow_name
    base_deploy["entrypoint"] = entrypoint

    ## parse parameters
    # minor optimization in case we already loaded the flow
    if not flow:
        try:
            flow = await run_sync_in_worker_thread(
                load_flow_from_entrypoint, base_deploy["entrypoint"]
            )
        except Exception as exc:
            exit_with_error(exc)

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

    base_deploy["parameters"] = parameters

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
    for step in project["build"] + project["push"]:
        step_outputs.update(await run_step(step))

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
    if schedule:
        base_deploy["schedule"] = schedule

    # prepare the pull step
    project["pull"] = apply_values(project["pull"], step_outputs)

    async with prefect.get_client() as client:
        flow_id = await client.create_flow_from_name(base_deploy["flow_name"])

        if base_deploy["work_pool"]:
            try:
                work_pool = await client.read_work_pool(
                    base_deploy["work_pool"]["name"]
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
            pull_steps=project["pull"],
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
                f" pulls work from the {base_deploy['work_pool']['name']!r} work pool"
            )
        elif base_deploy["work_pool"]["work_queue_name"] is not None:
            app.console.print(
                "\nTo execute flow runs from this deployment, start a worker that"
                " pulls work from the"
                f" {base_deploy['work_pool']['work_queue_name']!r} work queue"
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

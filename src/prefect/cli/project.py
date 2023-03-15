"""
Command line interface for working with projects.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer
import yaml

import prefect
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.deployment import _print_deployment_work_pool_instructions
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.flows import load_flow_from_entrypoint
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.callables import parameter_schema
from prefect.utilities.filesystem import set_default_ignore_file

project_app = PrefectTyper(
    name="project", help="Commands for interacting with your Prefect project."
)
app.add_typer(project_app, aliases=["projects"])


def find_prefect_directory() -> Optional[Path]:
    """
    Recurses upward looking for .prefect/ directories.  If found is never found, `None` is returned.
    """
    path = Path(".").resolve()
    parent = path.parent.resolve()
    while path != parent:
        prefect_dir = path.joinpath(".prefect")
        if prefect_dir.is_dir():
            return prefect_dir

        path = parent.resolve()
        parent = path.parent.resolve()


def set_default_deployment_yaml(path: str) -> bool:
    """
    Creates default deployment.yaml file in the provided path if one does not already exist;
    returns boolean specifying whether a file was created.
    """
    path = Path(path)
    if (path / "deployment.yaml").exists():
        return False
    default_file = Path(__file__).parent / "templates" / "deployment.yaml"
    with open(path / "deployment.yaml", "w") as f:
        f.write(default_file.read_text())
    return True


def set_prefect_hidden_dir() -> bool:
    """
    Creates default .prefect directory if one does not already exist.
    Returns boolean specifying whether a directory was created.
    """
    path = Path(".") / ".prefect"

    # use exists so that we dont accidentally overwrite a file
    if path.exists():
        return False
    path.mkdir()
    return True


def set_default_project_yaml(
    path: str, name: str = None, pull_step: dict = None
) -> bool:
    """
    Creates default project.yaml file in the provided path if one does not already exist;
    returns boolean specifying whether a file was created.
    """
    path = Path(path)
    if (path / "project.yaml").exists():
        return False
    default_file = Path(__file__).parent / "templates" / "project.yaml"
    with open(default_file, "r") as df:
        contents = yaml.safe_load(df)
    contents["prefect-version"] = prefect.__version__
    contents["name"] = name

    with open(path / "project.yaml", "w") as f:
        # write header
        f.write(
            "# File for configuring project / deployment build, push and pull steps\n\n"
        )

        f.write("# Generic metadata about this project\n")
        yaml.dump({"name": contents["name"]}, f, sort_keys=False)
        yaml.dump({"prefect-version": contents["prefect-version"]}, f, sort_keys=False)
        f.write("\n")

        # build
        f.write("# build section allows you to manage and build docker images\n")
        yaml.dump({"build": contents["build"]}, f, sort_keys=False)
        f.write("\n")

        # push
        f.write(
            "# push section allows you to manage if and how this project is uploaded to"
            " remote locations\n"
        )
        yaml.dump({"push": contents["push"]}, f, sort_keys=False)
        f.write("\n")

        # pull
        f.write(
            "# pull section allows you to provide instructions for cloning this project"
            " in remote locations\n"
        )
        yaml.dump({"pull": pull_step or contents["pull"]}, f, sort_keys=False)
    return True


@project_app.command()
async def init(name: str = None):
    """
    Initialize a new project.
    """

    # determine if in git repo or use directory name as a default
    is_git_based = False
    repo_name = None
    pull_step = None
    try:
        p = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            shell=sys.platform == "win32",
            stderr=subprocess.DEVNULL,
        )
        repo_name = "/".join(p.decode().strip().split("/")[-2:]).replace(".git", "")
        is_git_based = True
        name = name or repo_name
    except subprocess.CalledProcessError:
        dir_name = os.path.basename(os.getcwd())
        name = name or dir_name

    # hand craft a pull step
    if is_git_based:
        try:
            p = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                shell=sys.platform == "win32",
                stderr=subprocess.DEVNULL,
            )
            branch = p.decode().strip()
        except subprocess.CalledProcessError:
            branch = "main"

        pull_step = [
            {"prefect_github.clone_project": {"repo": repo_name, "branch": branch}}
        ]

    files = []
    if set_default_ignore_file("."):
        files.append("[green].prefectignore[/green]")
    if set_default_deployment_yaml("."):
        files.append("[green]deployment.yaml[/green]")
    if set_default_project_yaml(".", name=name, pull_step=pull_step):
        files.append("[green]project.yaml[/green]")
    if set_prefect_hidden_dir():
        files.append("[green].prefect/[/green]")

    files = "\n".join(files)
    empty_msg = f"Created project [green]{name!r}[/green]; no new files created."
    file_msg = (
        f"Created project [green]{name!r}[/green] with the following new files:\n"
        f" {files}"
    )
    app.console.print(file_msg if files else empty_msg)


@project_app.command()
async def clone():
    """
    Clone an existing project.
    """


@project_app.command()
async def register(
    entrypoint: str = typer.Argument(
        ...,
        help=(
            "The path to a flow entrypoint, in the form of"
            " `./path/to/file.py:flow_func_name`"
        ),
    )
):
    """
    Register a flow with this project.
    """
    try:
        fpath, obj_name = entrypoint.rsplit(":", 1)
    except ValueError as exc:
        if str(exc) == "not enough values to unpack (expected 2, got 1)":
            missing_flow_name_msg = (
                "Your flow entrypoint must include the name of the function that is"
                f" the entrypoint to your flow.\nTry {entrypoint}:<flow_name>"
            )
            exit_with_error(missing_flow_name_msg)
        else:
            raise exc
    try:
        flow = await run_sync_in_worker_thread(load_flow_from_entrypoint, entrypoint)
    except Exception as exc:
        exit_with_error(exc)

    fpath = Path(fpath).absolute()
    prefect_dir = find_prefect_directory()
    if not prefect_dir:
        exit_with_error(
            "No .prefect directory could be found - run [yellow]`prefect project"
            " init`[/yellow] to create one."
        )

    entrypoint = f"{fpath.relative_to(prefect_dir.parent)!s}:{obj_name}"

    if (prefect_dir / "flows.json").exists():
        with open(prefect_dir / "flows.json", "r") as f:
            flows = json.load(f)
    else:
        flows = {}

    flows[flow.name] = entrypoint

    with open(prefect_dir / "flows.json", "w") as f:
        json.dump(flows, f, sort_keys=True, indent=2)

    app.console.print(
        f"Registered flow {flow.name!r} in {(prefect_dir/'flows.json').resolve()!s}",
        style="green",
    )


@project_app.command()
async def deploy(
    flow_name: str = typer.Option(
        None, "--flow", "-f", help="The name of the flow to create a deployment for."
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
        None, "--version", "-v", help="A version to give the deployment."
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
    overrides: List[str] = typer.Option(
        None,
        "--override",
        help=(
            "One or more optional infrastructure overrides provided as a dot delimited"
            " path, e.g., `env.env_key=env_value`"
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
    Deploy this project and create a deployment.
    """
    with open("deployment.yaml", "r") as f:
        base_deploy = yaml.safe_load(f)

    if not flow_name and not base_deploy["flow_name"]:
        exit_with_error("A flow name must be provided with the '--flow' flag.")
    if not name and not base_deploy["name"]:
        exit_with_error("A deployment name must be provided with the '--name' flag.")

    # flow-name logic
    if flow_name:
        prefect_dir = find_prefect_directory()
        if not prefect_dir:
            exit_with_error(
                "No .prefect directory could be found - run [yellow]`prefect project"
                " init`[/yellow] to create one."
            )
        if not (prefect_dir / "flows.json").exists():
            exit_with_error(
                f"Flow {flow_name!r} cannot be found; run\n    [yellow]prefect project"
                f" register ./path/to/file.py:{flow_name}[/yellow]\nto register its"
                " location."
            )
        with open(prefect_dir / "flows.json", "r") as f:
            flows = json.load(f)

        if flow_name not in flows:
            exit_with_error(
                f"Flow {flow_name!r} cannot be found; run\n    [yellow]prefect project"
                f" register ./path/to/file.py:{flow_name}[/yellow]\nto register its"
                " location."
            )
        base_deploy["flow_name"] = flow_name
        base_deploy["entrypoint"] = flows[flow_name]

    ## TODO: HARDCODING THIS, ONLY CORRECT FOR FULLY LOCAL PROJECTS
    base_deploy["path"] = str(Path(".").absolute())

    if not base_deploy["entrypoint"]:
        exit_with_error(
            "No entrypoint for the flow provided; either register your flow with"
            " `prefect project register` or set one manually in `deployment.yaml`."
        )

    ## parse parameters
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

    # set other CLI flags
    if name:
        base_deploy["name"] = name
    if version:
        base_deploy["version"] = version
    if tags:
        base_deploy["tags"] = tags
    if description:
        base_deploy["description"] = description

    # TODO: add schedule

    if work_pool_name:
        base_deploy["work_pool_name"] = work_pool_name
    if work_queue_name:
        base_deploy["work_queue_name"] = work_queue_name

    async with get_client() as client:
        flow_id = await client.create_flow_from_name(base_deploy["flow_name"])

        deployment_id = await client.create_deployment(
            flow_id=flow_id,
            name=base_deploy["name"],
            work_queue_name=base_deploy["work_queue_name"],
            work_pool_name=base_deploy["work_pool_name"],
            version=base_deploy["version"],
            schedule=base_deploy["schedule"],
            parameters=base_deploy["parameters"],
            description=base_deploy["description"],
            tags=base_deploy["tags"],
            path=base_deploy["path"],
            entrypoint=base_deploy["entrypoint"],
            parameter_openapi_schema=base_deploy["parameter_openapi_schema"].dict(),
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

        if base_deploy["work_pool_name"] is not None:
            await _print_deployment_work_pool_instructions(
                work_pool_name=base_deploy["work_pool_name"], client=client
            )
        elif base_deploy["work_queue_name"] is not None:
            app.console.print(
                "\nTo execute flow runs from this deployment, start an agent that"
                f" pulls work from the {base_deploy['work_queue_name']!r} work queue:"
            )
            app.console.print(
                f"$ prefect agent start -q {base_deploy['work_queue_name']!r}",
                style="blue",
            )
        else:
            app.console.print(
                (
                    "\nThis deployment does not specify a work queue name, which"
                    " means agents will not be able to pick up its runs. To add a"
                    " work queue, edit the deployment spec and re-run this command,"
                    " or visit the deployment in the UI."
                ),
                style="red",
            )

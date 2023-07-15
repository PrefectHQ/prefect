"""
Core primitives for managing Prefect projects.  Projects provide a minimally opinionated
build system for managing flows and deployments.

To get started, follow along with [the deloyments tutorial](/tutorials/deployments/).
"""
from copy import deepcopy
import ast
import asyncio
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

import yaml
from ruamel.yaml import YAML

import anyio
from prefect.flows import load_flow_from_entrypoint
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.filesystem import create_default_ignore_file, get_open_file_limit
from prefect.utilities.templating import apply_values
from prefect.settings import PREFECT_DEBUG_MODE
from prefect.logging import get_logger

from prefect.client.schemas.schedules import IntervalSchedule


def find_prefect_directory(path: Path = None) -> Optional[Path]:
    """
    Given a path, recurses upward looking for .prefect/ directories.

    Once found, returns absolute path to the ./prefect directory, which is assumed to reside within the
    root for the current project.

    If one is never found, `None` is returned.
    """
    path = Path(path or ".").resolve()
    parent = path.parent.resolve()
    while path != parent:
        prefect_dir = path.joinpath(".prefect")
        if prefect_dir.is_dir():
            return prefect_dir

        path = parent.resolve()
        parent = path.parent.resolve()


def set_prefect_hidden_dir(path: str = None) -> bool:
    """
    Creates default `.prefect/` directory if one does not already exist.
    Returns boolean specifying whether or not a directory was created.

    If a path is provided, the directory will be created in that location.
    """
    path = Path(path or ".") / ".prefect"

    # use exists so that we dont accidentally overwrite a file
    if path.exists():
        return False
    path.mkdir(mode=0o0700)
    return True


def create_default_prefect_yaml(
    path: str, name: str = None, contents: dict = None
) -> bool:
    """
    Creates default `prefect.yaml` file in the provided path if one does not already exist;
    returns boolean specifying whether a file was created.

    Args:
        name (str, optional): the name of the project; if not provided, the current directory name
            will be used
        contents (dict, optional): a dictionary of contents to write to the file; if not provided,
            defaults will be used
    """
    path = Path(path)
    prefect_file = path / "prefect.yaml"
    if prefect_file.exists():
        return False
    default_file = Path(__file__).parent / "templates" / "prefect.yaml"

    with default_file.open(mode="r") as df:
        default_contents = yaml.safe_load(df)

    import prefect

    contents["prefect-version"] = prefect.__version__
    contents["name"] = name

    with prefect_file.open(mode="w") as f:
        # write header
        f.write(
            "# Welcome to your prefect.yaml file! You can you this file for storing and"
            " managing\n# configuration for deploying your flows. We recommend"
            " committing this file to source\n# control along with your flow code.\n\n"
        )

        f.write("# Generic metadata about this project\n")
        yaml.dump({"name": contents["name"]}, f, sort_keys=False)
        yaml.dump({"prefect-version": contents["prefect-version"]}, f, sort_keys=False)
        f.write("\n")

        # build
        f.write("# build section allows you to manage and build docker images\n")
        yaml.dump(
            {"build": contents.get("build", default_contents.get("build"))},
            f,
            sort_keys=False,
        )
        f.write("\n")

        # push
        f.write(
            "# push section allows you to manage if and how this project is uploaded to"
            " remote locations\n"
        )
        yaml.dump(
            {"push": contents.get("push", default_contents.get("push"))},
            f,
            sort_keys=False,
        )
        f.write("\n")

        # pull
        f.write(
            "# pull section allows you to provide instructions for cloning this project"
            " in remote locations\n"
        )
        yaml.dump(
            {"pull": contents.get("pull", default_contents.get("pull"))},
            f,
            sort_keys=False,
        )
        f.write("\n")

        # deployments
        f.write(
            "# the deployments section allows you to provide configuration for"
            " deploying flows\n"
        )
        yaml.dump(
            {
                "deployments": contents.get(
                    "deployments", default_contents.get("deployments")
                )
            },
            f,
            sort_keys=False,
        )
    return True


def configure_project_by_recipe(recipe: str, **formatting_kwargs) -> dict:
    """
    Given a recipe name, returns a dictionary representing base configuration options.

    Args:
        recipe (str): the name of the recipe to use
        formatting_kwargs (dict, optional): additional keyword arguments to format the recipe

    Raises:
        ValueError: if provided recipe name does not exist.
    """
    # load the recipe
    recipe_path = Path(__file__).parent / "recipes" / recipe / "prefect.yaml"

    if not recipe_path.exists():
        raise ValueError(f"Unknown recipe {recipe!r} provided.")

    with recipe_path.open(mode="r") as f:
        config = yaml.safe_load(f)

    config = apply_values(
        template=config, values=formatting_kwargs, remove_notset=False
    )

    return config


def _get_git_remote_origin_url() -> Optional[str]:
    """
    Returns the git remote origin URL for the current directory.
    """
    try:
        origin_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            shell=sys.platform == "win32",
            stderr=subprocess.DEVNULL,
        )
        origin_url = origin_url.decode().strip()
    except subprocess.CalledProcessError:
        return None

    return origin_url


def _get_git_branch() -> Optional[str]:
    """
    Returns the git branch for the current directory.
    """
    try:
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        branch = branch.decode().strip()
    except subprocess.CalledProcessError:
        return None

    return branch


def initialize_project(
    name: str = None, recipe: str = None, inputs: dict = None
) -> List[str]:
    """
    Initializes a basic project structure with base files.  If no name is provided, the name
    of the current directory is used.  If no recipe is provided, one is inferred.

    Args:
        name (str, optional): the name of the project; if not provided, the current directory name
        recipe (str, optional): the name of the recipe to use; if not provided, one is inferred
        inputs (dict, optional): a dictionary of inputs to use when formatting the recipe

    Returns:
        List[str]: a list of files / directories that were created
    """
    # determine if in git repo or use directory name as a default
    is_git_based = False
    formatting_kwargs = {"directory": str(Path(".").absolute().resolve())}
    dir_name = os.path.basename(os.getcwd())

    remote_url = _get_git_remote_origin_url()
    if remote_url:
        formatting_kwargs["repository"] = remote_url
        is_git_based = True
        branch = _get_git_branch()
        formatting_kwargs["branch"] = branch or "main"

    formatting_kwargs["name"] = dir_name

    has_dockerfile = Path("Dockerfile").exists()

    if has_dockerfile:
        formatting_kwargs["dockerfile"] = "Dockerfile"
    elif recipe is not None and "docker" in recipe:
        formatting_kwargs["dockerfile"] = "auto"

    # hand craft a pull step
    if is_git_based and recipe is None:
        if has_dockerfile:
            recipe = "docker-git"
        else:
            recipe = "git"
    elif recipe is None and has_dockerfile:
        recipe = "docker"
    elif recipe is None:
        recipe = "local"

    formatting_kwargs.update(inputs or {})
    configuration = configure_project_by_recipe(recipe=recipe, **formatting_kwargs)

    project_name = name or dir_name

    files = []
    if create_default_ignore_file("."):
        files.append(".prefectignore")
    if create_default_prefect_yaml(".", name=project_name, contents=configuration):
        files.append("prefect.yaml")
    if set_prefect_hidden_dir():
        files.append(".prefect/")

    return files


async def register_flow(entrypoint: str, force: bool = False):
    """
    Register a flow with this project from an entrypoint.

    Args:
        entrypoint (str): the entrypoint to the flow to register
        force (bool, optional): whether or not to overwrite an existing flow with the same name

    Raises:
        ValueError: if `force` is `False` and registration would overwrite an existing flow
    """
    try:
        fpath, obj_name = entrypoint.rsplit(":", 1)
    except ValueError as exc:
        if str(exc) == "not enough values to unpack (expected 2, got 1)":
            missing_flow_name_msg = (
                "Your flow entrypoint must include the name of the function that is"
                f" the entrypoint to your flow.\nTry {entrypoint}:<flow_name> as your"
                f" entrypoint. If you meant to specify '{entrypoint}' as the deployment"
                f" name, try `prefect deploy -n {entrypoint}`."
            )
            raise ValueError(missing_flow_name_msg)
        else:
            raise exc

    flow = await run_sync_in_worker_thread(load_flow_from_entrypoint, entrypoint)

    fpath = Path(fpath).absolute()
    prefect_dir = find_prefect_directory()
    if not prefect_dir:
        raise FileNotFoundError(
            "No .prefect directory could be found - run `prefect project"
            " init` to create one."
        )

    entrypoint = f"{fpath.relative_to(prefect_dir.parent)!s}:{obj_name}"

    flows_file = prefect_dir / "flows.json"
    if flows_file.exists():
        with flows_file.open(mode="r") as f:
            flows = json.load(f)
    else:
        flows = {}

    ## quality control
    if flow.name in flows and flows[flow.name] != entrypoint:
        if not force:
            raise ValueError(
                f"Conflicting entry found for flow with name {flow.name!r}.\nExisting"
                f" entrypoint: {flows[flow.name]}\nAttempted entrypoint:"
                f" {entrypoint}\n\nYou can try removing the existing entry for"
                f" {flow.name!r} from your [yellow]~./prefect/flows.json[/yellow]."
            )

    flows[flow.name] = entrypoint

    with flows_file.open(mode="w") as f:
        json.dump(flows, f, sort_keys=True, indent=2)

    return flow


def _copy_deployments_into_prefect_file():
    """
    Copy deployments from the `deloyment.yaml` file into the `prefect.yaml` file.

    Used to migrate users from the old `prefect.yaml` + `deployment.yaml` structure
    to a single `prefect.yaml` file.
    """
    prefect_file = Path("prefect.yaml")
    deployment_file = Path("deployment.yaml")
    if not deployment_file.exists() or not prefect_file.exists():
        raise FileNotFoundError(
            "Could not find `prefect.yaml` or `deployment.yaml` files."
        )

    with deployment_file.open(mode="r") as f:
        raw_deployment_file_contents = f.read()
        parsed_deployment_file_contents = yaml.safe_load(raw_deployment_file_contents)

    deployments = parsed_deployment_file_contents.get("deployments")

    with prefect_file.open(mode="a") as f:
        # If deployment.yaml is empty, write an empty deployments list to prefect.yaml.
        if not parsed_deployment_file_contents:
            f.write("\n")
            f.write(yaml.dump({"deployments": []}, sort_keys=False))
        # If there is no 'deployments' key in deployment.yaml, assume that the
        # entire file is a single deployment.
        elif not deployments:
            f.write("\n")
            f.write(
                yaml.dump(
                    {"deployments": [parsed_deployment_file_contents]}, sort_keys=False
                )
            )
        # Write all of deployment.yaml to prefect.yaml.
        else:
            f.write("\n")
            f.write(raw_deployment_file_contents)


def _save_deployment_to_prefect_file(
    deployment: Dict,
    build_steps: Optional[List[Dict]] = None,
    push_steps: Optional[List[Dict]] = None,
    pull_steps: Optional[List[Dict]] = None,
):
    """
    Save a deployment configuration to the `prefect.yaml` file in the
    current directory.

    Will create a prefect.yaml file if one does not already exist.

    Args:
        - deployment: a dictionary containing a deployment configuration
    """
    if not deployment:
        raise ValueError("Deployment must be a non-empty dictionary.")
    deployment = deepcopy(deployment)
    # Parameter schema is not stored in prefect.yaml
    deployment.pop("parameter_openapi_schema")
    # Only want entrypoint to avoid errors
    deployment.pop("flow_name", None)

    if deployment.get("schedule"):
        if isinstance(deployment["schedule"], IntervalSchedule):
            deployment["schedule"] = deployment["schedule"].dict()
            deployment["schedule"]["interval"] = deployment["schedule"][
                "interval"
            ].total_seconds()
            deployment["schedule"]["anchor_date"] = deployment["schedule"][
                "anchor_date"
            ].isoformat()
        elif isinstance(deployment["schedule"], BaseModel):
            deployment["schedule"] = deployment["schedule"].dict()

    current_directory_name = os.path.basename(os.getcwd())
    prefect_file = Path("prefect.yaml")
    if not prefect_file.exists():
        create_default_prefect_yaml(
            ".",
            current_directory_name,
            contents={
                "deployments": [deployment],
                "build": build_steps,
                "push": push_steps,
                "pull": pull_steps,
            },
        )
        create_default_ignore_file(".")
    else:
        # use ruamel.yaml to preserve comments
        ryaml = YAML()
        with prefect_file.open(mode="r") as f:
            parsed_prefect_file_contents = ryaml.load(f)

        if build_steps != parsed_prefect_file_contents.get("build"):
            deployment["build"] = build_steps

        if push_steps != parsed_prefect_file_contents.get("push"):
            deployment["push"] = push_steps

        if pull_steps != parsed_prefect_file_contents.get("pull"):
            deployment["pull"] = pull_steps

        deployments = parsed_prefect_file_contents.get("deployments")
        if deployments is None:
            parsed_prefect_file_contents["deployments"] = [deployment]
        else:
            for i, existing_deployment in enumerate(deployments):
                if existing_deployment.get("name") == deployment.get("name") and (
                    existing_deployment.get("entrypoint")
                    == deployment.get("entrypoint")
                ):
                    deployments[i] = deployment
                    break
            else:
                deployments.append(deployment)

        with prefect_file.open(mode="w") as f:
            ryaml.dump(parsed_prefect_file_contents, f)


# Only allow half of the open file limit to be open at once to allow for other
# actors to open files.
OPEN_FILE_SEMAPHORE = asyncio.Semaphore(math.floor(get_open_file_limit() * 0.5))


async def _find_flow_functions_in_file(filename: str) -> List[Dict]:
    decorator_name = "flow"
    decorator_module = "prefect"
    decorated_functions = []
    async with OPEN_FILE_SEMAPHORE:
        try:
            async with await anyio.open_file(filename) as f:
                try:
                    tree = ast.parse(await f.read())
                except SyntaxError:
                    if PREFECT_DEBUG_MODE:
                        get_logger().debug(
                            f"Could not parse {filename} as a Python file. Skipping."
                        )
                    return decorated_functions
        except Exception as exc:
            if PREFECT_DEBUG_MODE:
                get_logger().debug(f"Could not open {filename}: {exc}. Skipping.")
            return decorated_functions

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                # handles @flow
                is_name_match = (
                    isinstance(decorator, ast.Name) and decorator.id == decorator_name
                )
                # handles @flow()
                is_func_name_match = (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Name)
                    and decorator.func.id == decorator_name
                )
                # handles @prefect.flow
                is_module_attribute_match = (
                    isinstance(decorator, ast.Attribute)
                    and isinstance(decorator.value, ast.Name)
                    and decorator.value.id == decorator_module
                    and decorator.attr == decorator_name
                )
                # handles @prefect.flow()
                is_module_attribute_func_match = (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == decorator_name
                    and isinstance(decorator.func.value, ast.Name)
                    and decorator.func.value.id == decorator_module
                )
                if is_name_match or is_module_attribute_match:
                    decorated_functions.append(
                        {
                            "flow_name": node.name,
                            "function_name": node.name,
                            "filepath": str(filename),
                        }
                    )
                if is_func_name_match or is_module_attribute_func_match:
                    name_kwarg_node = next(
                        (kw for kw in decorator.keywords if kw.arg == "name"), None
                    )
                    flow_name = (
                        name_kwarg_node.value.value
                        if isinstance(name_kwarg_node, ast.Constant)
                        else node.name
                    )
                    decorated_functions.append(
                        {
                            "flow_name": flow_name,
                            "function_name": node.name,
                            "filepath": str(filename),
                        }
                    )
    return decorated_functions


async def _search_for_flow_functions(directory: str = "."):
    """
    Search for flow functions in the provided directory. If no directory is provided,
    the current working directory is used.

    Returns:
        List[Dict]: the flow name, function name, and filepath of all flow functions found
    """
    path = anyio.Path(directory)
    coros = []
    async for file in path.rglob("*.py"):
        coros.append(_find_flow_functions_in_file(file))

    return [fn for file_fns in await asyncio.gather(*coros) for fn in file_fns]

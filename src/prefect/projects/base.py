"""
Core primitives for managing Prefect projects.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import yaml

from prefect.flows import load_flow_from_entrypoint
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.filesystem import create_default_ignore_file
from prefect.utilities.templating import apply_values


def find_prefect_directory(path: Path = None) -> Optional[Path]:
    """
    Recurses upward looking for .prefect/ directories.  If found is never found, `None` is returned.

    Returns the absolute location of the .prefect/ directory.
    """
    path = Path(path or ".").resolve()
    parent = path.parent.resolve()
    while path != parent:
        prefect_dir = path.joinpath(".prefect")
        if prefect_dir.is_dir():
            return prefect_dir

        path = parent.resolve()
        parent = path.parent.resolve()


def create_default_deployment_yaml(path: str) -> bool:
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


def create_default_project_yaml(
    path: str, name: str = None, contents: dict = None
) -> bool:
    """
    Creates default prefect.yaml file in the provided path if one does not already exist;
    returns boolean specifying whether a file was created.
    """
    path = Path(path)
    if (path / "prefect.yaml").exists():
        return False
    default_file = Path(__file__).parent / "templates" / "prefect.yaml"

    if contents is None:
        with open(default_file, "r") as df:
            contents = yaml.safe_load(df)

    import prefect

    contents["prefect-version"] = prefect.__version__
    contents["name"] = name

    with open(path / "prefect.yaml", "w") as f:
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
        yaml.dump({"pull": contents["pull"]}, f, sort_keys=False)
    return True


def configure_project_by_recipe(recipe: str, **formatting_kwargs) -> dict:
    """
    Given a recipe name, returns a dictionary representing base configuration options.

    Raises ValueError if recipe does not exist.
    """
    # load the recipe
    recipe_path = Path(__file__).parent / "recipes" / recipe / "prefect.yaml"

    if not recipe_path.exists():
        raise ValueError(f"Unknown recipe {recipe!r} provided.")

    with open(recipe_path, "r") as f:
        config = yaml.safe_load(f)

    config = apply_values(
        template=config, values=formatting_kwargs, remove_notset=False
    )

    return config


def initialize_project(name: str = None, recipe: str = None) -> List[str]:
    """
    Initializes a basic project structure with base files.  If no name is provided, the name
    of the current directory is used.  If no recipe is provided, one is inferred.

    Returns a list of files / directories that were created.
    """
    # determine if in git repo or use directory name as a default
    is_git_based = False
    formatting_kwargs = {"directory": str(Path(".").absolute().resolve())}
    dir_name = os.path.basename(os.getcwd())

    try:
        p = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            shell=sys.platform == "win32",
            stderr=subprocess.DEVNULL,
        )
        formatting_kwargs["repository"] = p.decode().strip()
        is_git_based = True
        try:
            p = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                shell=sys.platform == "win32",
                stderr=subprocess.DEVNULL,
            )
            formatting_kwargs["branch"] = p.decode().strip()
        except subprocess.CalledProcessError:
            formatting_kwargs["branch"] = "main"

    except subprocess.CalledProcessError:
        pass

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

    configuration = configure_project_by_recipe(recipe=recipe, **formatting_kwargs)

    project_name = name or dir_name

    files = []
    if create_default_ignore_file("."):
        files.append(".prefectignore")
    if create_default_deployment_yaml("."):
        files.append("deployment.yaml")
    if create_default_project_yaml(".", name=project_name, contents=configuration):
        files.append("prefect.yaml")
    if set_prefect_hidden_dir():
        files.append(".prefect/")

    return files


async def register_flow(entrypoint: str, force: bool = False):
    """
    Register a flow with this project from an entrypoint.

    Raises a ValueError if registration will overwrite an existing known flow.
    """
    try:
        fpath, obj_name = entrypoint.rsplit(":", 1)
    except ValueError as exc:
        if str(exc) == "not enough values to unpack (expected 2, got 1)":
            missing_flow_name_msg = (
                "Your flow entrypoint must include the name of the function that is"
                f" the entrypoint to your flow.\nTry {entrypoint}:<flow_name>"
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

    if (prefect_dir / "flows.json").exists():
        with open(prefect_dir / "flows.json", "r") as f:
            flows = json.load(f)
    else:
        flows = {}

    ## quality control
    if flow.name in flows and flows[flow.name] != entrypoint:
        if not force:
            raise ValueError(
                "Conflicting entry found for flow with name"
                f" {flow.name!r}:\n{flow.name}: {flows[flow.name]}"
            )
    flows[flow.name] = entrypoint

    with open(prefect_dir / "flows.json", "w") as f:
        json.dump(flows, f, sort_keys=True, indent=2)

    return flow

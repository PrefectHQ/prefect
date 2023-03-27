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
from prefect.utilities.filesystem import set_default_ignore_file


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
    Creates default prefect.yaml file in the provided path if one does not already exist;
    returns boolean specifying whether a file was created.
    """
    path = Path(path)
    if (path / "prefect.yaml").exists():
        return False
    default_file = Path(__file__).parent / "templates" / "prefect.yaml"
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
        yaml.dump({"pull": pull_step or contents["pull"]}, f, sort_keys=False)
    return True


def initialize_project(name: str = None) -> List[str]:
    """
    Initializes a basic project structure with base files.

    Returns a list of files / directories that were created.
    """
    # determine if in git repo or use directory name as a default
    is_git_based = False
    repository = None
    pull_step = None
    try:
        p = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            shell=sys.platform == "win32",
            stderr=subprocess.DEVNULL,
        )
        repository = p.decode().strip()
        is_git_based = True
        name = name or "/".join(p.decode().strip().split("/")[-2:]).replace(".git", "")
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
            {
                "prefect.projects.steps.git_clone_project": {
                    "repository": repository,
                    "branch": branch,
                }
            }
        ]
    else:
        pull_step = [
            {
                "prefect.projects.steps.set_working_directory": {
                    "directory": str(Path(".").absolute().resolve()),
                }
            }
        ]

    files = []
    if set_default_ignore_file("."):
        files.append(".prefectignore")
    if set_default_deployment_yaml("."):
        files.append("deployment.yaml")
    if set_default_project_yaml(".", name=name, pull_step=pull_step):
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

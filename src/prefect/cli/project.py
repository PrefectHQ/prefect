"""
Command line interface for working with projects.
"""
import os
import pathlib
import subprocess
import sys
import textwrap
import yaml

import prefect
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.utilities.filesystem import set_default_ignore_file

project_app = PrefectTyper(
    name="project", help="Commands for interacting with your Prefect project."
)
app.add_typer(project_app, aliases=["projects"])


def set_default_deployment_yaml(path: str) -> bool:
    """
    Creates default deployment.yaml file in the provided path if one does not already exist;
    returns boolean specifying whether a file was created.
    """
    path = pathlib.Path(path)
    if (path / "deployment.yaml").exists():
        return False
    default_file = pathlib.Path(__file__).parent / "templates" / "deployment.yaml"
    with open(path / "deployment.yaml", "w") as f:
        f.write(default_file.read_text())
    return True


def set_default_project_yaml(path: str, name: str = None) -> bool:
    """
    Creates default project.yaml file in the provided path if one does not already exist;
    returns boolean specifying whether a file was created.
    """
    path = pathlib.Path(path)
    if (path / "project.yaml").exists():
        return False
    default_file = pathlib.Path(__file__).parent / "templates" / "project.yaml"
    with open(default_file, "r") as df:
        contents = yaml.safe_load(df)
    contents["prefect-version"] = prefect.__version__
    contents["name"] = name

    with open(path / "project.yaml", "w") as f:
        # write header
        f.write(
            "###\n### File for configuring project / deployment build, push and pull steps\n###\n\n"
        )

        f.write("### Generic metadata about this project\n")
        yaml.dump({"name": contents["name"]}, f, sort_keys=False)
        yaml.dump({"prefect-version": contents["prefect-version"]}, f, sort_keys=False)
        f.write("\n")

        # build
        f.write(
            "### build section allows you to manage docker images and produce infrastructure configuration\n"
        )
        yaml.dump({"build": contents["build"]}, f, sort_keys=False)
        f.write("\n")

        # push
        f.write(
            "### push section allows you to manage how this project is uploaded to remote locations\n"
        )
        yaml.dump({"push": contents["push"]}, f, sort_keys=False)
        f.write("\n")

        # pull
        f.write(
            "### pull section allows you to provide instructions for cloning this project in new locations.\n"
        )
        yaml.dump({"pull": contents["pull"]}, f, sort_keys=False)
    return True


@project_app.command()
async def init(name: str = None):
    """
    Initialize a new project.
    """

    # determine if in git repo or use directory name as a default
    is_git_based = False
    repo_name = None
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

    files = []
    if set_default_ignore_file("."):
        files.append("[green].prefectignore[/green]")
    if set_default_deployment_yaml("."):
        files.append("[green]deployment.yaml[/green]")
    if set_default_project_yaml(".", name=name):
        files.append("[green]project.yaml[/green]")

    files = "\n".join(files)
    empty_msg = f"Created project [green]{name!r}[/green]; no new files created."
    file_msg = (
        f"Created project [green]{name!r} with the following new files:\n {files}"
    )
    app.console.print(file_msg if files else empty_msg)

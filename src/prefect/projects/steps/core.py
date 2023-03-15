"""
Core set of steps for managing Prefect projects.
"""
import subprocess
import sys

from prefect.utilities.importtools import import_object


def run_step(step: dict) -> dict:
    """
    Runs a step, returns the step's output.

    Steps are assumed to be in the format {"importable.func.name": {"kwarg1": "value1", ...}}
    """
    path, inputs = step.popitem()

    if step:
        raise ValueError(
            f"Step has unexpected additional keys: {', '.join(step.keys())}"
        )

    step_func = import_object(path)
    return step_func(**inputs)


def set_working_directory():
    pass


def git_clone_project(repository: str, branch: str = None) -> dict:
    """
    Just a repo name will be assumed GitHub, otherwise provide a full repo_url.
    """
    cmd = ["git", "clone", repository]
    if branch:
        cmd += ["-b", branch]

    # Limit git history
    cmd += ["--depth", "1"]

    p = subprocess.check_output(cmd, shell=sys.platform == "win32")
    directory = "/".join(repository.strip().split("/")[-1:]).replace(".git", "")
    return {"directory": directory}

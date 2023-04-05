"""
Core set of steps for specifying a Prefect project pull step.
"""
import os
import subprocess
import sys


def set_working_directory(directory: str) -> dict:
    os.chdir(directory)
    return dict(directory=directory)


def git_clone_project(repository: str, branch: str = None) -> dict:
    """
    Just a repo name will be assumed GitHub, otherwise provide a full repo_url.
    """
    cmd = ["git", "clone", repository]
    if branch:
        cmd += ["-b", branch]

    # Limit git history
    cmd += ["--depth", "1"]

    subprocess.check_output(cmd, shell=sys.platform == "win32")
    directory = "/".join(repository.strip().split("/")[-1:]).replace(".git", "")
    return {"directory": directory}

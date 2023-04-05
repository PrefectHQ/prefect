"""
Core set of steps for specifying a Prefect project pull step.
"""
import os
import subprocess
import sys
import urllib.parse
from typing import Optional


def set_working_directory(directory: str) -> dict:
    os.chdir(directory)
    return dict(directory=directory)


def git_clone_project(
    repository: str, branch: Optional[str] = None, access_token: Optional[str] = None
) -> dict:
    """
    Just a repo name will be assumed GitHub, otherwise provide a full repo_url.
    """
    url_components = urllib.parse.urlparse(repository)
    if url_components.scheme == "https" and access_token is not None:
        updated_components = url_components._replace(
            netloc=f"{access_token}@{url_components.netloc}"
        )
        repository_url = urllib.parse.urlunparse(updated_components)
    else:
        repository_url = repository

    cmd = ["git", "clone", repository_url]
    if branch:
        cmd += ["-b", branch]

    # Limit git history
    cmd += ["--depth", "1"]

    subprocess.check_output(cmd, shell=sys.platform == "win32")
    directory = "/".join(repository.strip().split("/")[-1:]).replace(".git", "")
    return {"directory": directory}

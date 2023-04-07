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

    try:
        subprocess.check_call(
            cmd, shell=sys.platform == "win32", stderr=sys.stderr, stdout=sys.stdout
        )
    except subprocess.CalledProcessError as exc:
        # Hide the command used to avoid leaking the access token
        exc_chain = None if access_token else exc
        raise RuntimeError(
            f"Failed to clone repository {repository!r} with exit code"
            f" {exc.returncode}."
        ) from exc_chain

    directory = "/".join(repository.strip().split("/")[-1:]).replace(".git", "")
    return {"directory": directory}

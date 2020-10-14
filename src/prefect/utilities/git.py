"""
Utility functions for interacting with git-based clients.
"""
import os
import prefect

from typing import Any

try:
    from github import Github
except ImportError:
    Github = None  # type: ignore

try:
    from gitlab import Gitlab
except ImportError:
    Gitlab = None  # type: ignore


def get_github_client(credentials: dict = None, **kwargs: Any) -> "Github":
    """
    Utility function for loading github client objects from a given set of credentials.

    Args:
        - credentials (dict, optional): a dictionary of AWS credentials used to
            initialize the Client; if not provided, will attempt to load the
            Client using ambient environment settings
        - **kwargs (Any, optional): additional keyword arguments to pass to the github Client

    Returns:
        - Client: an initialized and authenticated github Client
    """
    if not Github:
        raise ImportError(
            "Unable to import Github, please ensure you have installed the github extra"
        )

    access_token = None

    if credentials:
        access_token = credentials.get("GITHUB_ACCESS_TOKEN")
    else:
        access_token = prefect.context.get("secrets", {}).get(
            "GITHUB_ACCESS_TOKEN", None
        )

    # Attempt to grab out of env if not provided directly or through Prefect Secret
    if not access_token:
        access_token = os.getenv("GITHUB_ACCESS_TOKEN", None)

    return Github(access_token, **kwargs)


def get_gitlab_client(
    credentials: dict = None, host: str = None, **kwargs: Any
) -> "Gitlab":
    """
    Utility function for loading gitlab client objects from a given set of credentials.

    Args:
        - credentials (dict, optional): a dictionary of AWS credentials used to
            initialize the Client; if not provided, will attempt to load the
            Client using ambient environment settings
        - host (str, optional): the host string for gitlab server users. If not provided, defaults
            to https://gitlab.com
        - **kwargs (Any, optional): additional keyword arguments to pass to the gitlab Client

    Returns:
        - Client: an initialized and authenticated gitlab Client
    """
    if not Gitlab:
        raise ImportError(
            "Unable to import Gitlab, please ensure you have installed the gitlab extra"
        )

    if credentials:
        access_token = credentials.get("GITLAB_ACCESS_TOKEN")
    else:
        access_token = prefect.context.get("secrets", {}).get(
            "GITLAB_ACCESS_TOKEN", None
        )

    if not access_token:
        access_token = os.getenv("GITLAB_ACCESS_TOKEN", None)

    if not host:
        host = "https://gitlab.com"

    return Gitlab(host, private_token=access_token, **kwargs)

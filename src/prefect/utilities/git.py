"""
Utility functions for interacting with git-based clients.
"""
import os
from typing import TYPE_CHECKING

import requests

import prefect

if TYPE_CHECKING:
    from github import Github
    from gitlab import Gitlab
    from atlassian import Bitbucket


def get_github_client() -> "Github":
    """
    Utility function for loading github client objects from the default prefect
    credentials.

    Returns:
        - Github: an initialized and authenticated github client
    """
    try:
        from github import Github
    except ImportError as exc:
        raise ImportError(
            "Unable to import Github, please ensure you have installed the github extra"
        ) from exc

    # Load the access token from (in priority order)
    # - Active credentials
    # - Local secrets
    # - Environment variable
    key = "GITHUB_ACCESS_TOKEN"
    access_token = prefect.context.get("credentials", {}).get(key)
    if access_token is None:
        access_token = prefect.context.get("secrets", {}).get(key)
    if access_token is None:
        access_token = os.getenv(key)

    return Github(access_token)


def get_gitlab_client(host: str = None) -> "Gitlab":
    """
    Utility function for loading gitlab client objects from a given set of credentials.

    Args:
        - host (str, optional): the host string for gitlab server users.
            If not provided, defaults to `https://gitlab.com`.

    Returns:
        - Gitlab: an initialized and authenticated gitlab client
    """
    try:
        from gitlab import Gitlab
    except ImportError as exc:
        raise ImportError(
            "Unable to import Gitlab, please ensure you have installed the gitlab extra"
        ) from exc

    # Load the access token from (in priority order)
    # - Active credentials
    # - Local secrets
    # - Environment variable
    key = "GITLAB_ACCESS_TOKEN"
    access_token = prefect.context.get("credentials", {}).get(key)
    if access_token is None:
        access_token = prefect.context.get("secrets", {}).get(key)
    if access_token is None:
        access_token = os.getenv(key)

    if host is None:
        host = "https://gitlab.com"

    return Gitlab(host, private_token=access_token)


def get_bitbucket_client(host: str = None) -> "Bitbucket":
    """
    Utility function for loading Bitbucket client objects from a given set of credentials.

    Args:
        - host (str, optional): the host string for bitbucket server users.
            If not provided, defaults to `https://bitbucket.org`.

    Returns:
        - Client: an initialized and authenticated Bitbucket Client
    """
    try:
        from atlassian import Bitbucket
    except ImportError as exc:
        raise ImportError(
            "Unable to import Bitbucket, please ensure you have installed the bitbucket extra"
        ) from exc

    key = "BITBUCKET_ACCESS_TOKEN"
    access_token = prefect.context.get("credentials", {}).get(key)
    if access_token is None:
        access_token = prefect.context.get("secrets", {}).get(key)
    if access_token is None:
        access_token = os.getenv(key)

    if not host:
        host = "https://bitbucket.org"

    session = requests.Session()
    if access_token is None:
        session.headers["Authorization"] = "Bearer "
    else:
        session.headers["Authorization"] = "Bearer " + access_token
    return Bitbucket(host, session=session)

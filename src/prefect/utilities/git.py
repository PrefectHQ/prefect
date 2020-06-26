"""
Utility functions for interacting with git.
"""
import os
import prefect

from github import Github
from typing import Any


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

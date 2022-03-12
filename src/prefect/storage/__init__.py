"""
The Prefect Storage interface encapsulates logic for storing flows. Each
storage unit is able to store _multiple_ flows (with the constraint of name
uniqueness within a given unit).
"""

from warnings import warn

import prefect
from prefect import config
from prefect.storage.base import Storage
from prefect.storage.azure import Azure
from prefect.storage.bitbucket import Bitbucket
from prefect.storage.codecommit import CodeCommit
from prefect.storage.docker import Docker
from prefect.storage.gcs import GCS
from prefect.storage.github import GitHub
from prefect.storage.gitlab import GitLab
from prefect.storage.local import Local
from prefect.storage.module import Module
from prefect.storage.s3 import S3
from prefect.storage.webhook import Webhook
from prefect.storage.git import Git


def get_default_storage_class() -> type:
    """
    Returns the `Storage` class specified in
    `prefect.config.flows.defaults.storage.default_class`. If the value is a string, it will
    attempt to load the already-imported object. Otherwise, the value is returned.

    Defaults to `Local` if the string config value can not be loaded
    """
    config_value = config.flows.defaults.storage.default_class
    if isinstance(config_value, str):
        try:
            return prefect.utilities.serialization.from_qualified_name(config_value)
        except ValueError:
            warn(
                f"Could not import {config_value}; using prefect.storage.Local instead."
            )
            return Local
    else:
        return config_value


__all__ = [
    "Azure",
    "Bitbucket",
    "CodeCommit",
    "Docker",
    "GCS",
    "Git",
    "GitHub",
    "GitLab",
    "Local",
    "Module",
    "S3",
    "Storage",
    "Webhook",
]

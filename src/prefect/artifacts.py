"""
The functions here have been moved to `prefect.backend.artifacts`
"""
# flake8: noqa
import warnings
from typing import Optional

from prefect.backend import (
    create_link_artifact,
    create_markdown_artifact,
    delete_artifact as delete_artifact_new,
    update_link_artifact,
    update_markdown_artifact,
)


def create_link(link: str) -> Optional[str]:
    """
    Create a link artifact

    Args:
        - link (str): the link to post

    Returns:
        - str: the task run artifact ID
    """
    warnings.warn(
        "`prefect.artifacts.create_link` has been moved to `prefect.backend.create_link_artifact`. "
        "Please update your imports. This import path will be removed in 1.0.0."
    )
    return create_link_artifact(link)


def update_link(task_run_artifact_id: str, link: str) -> None:
    """
    Update an existing link artifact. This function will replace the current link
    artifact with the new link provided.

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact
        - link (str): the new link to update the artifact with
    """
    warnings.warn(
        "`prefect.artifacts.update_link` has been moved to `prefect.backend.update_link_artifact`. "
        "Please update your imports. This import path will be removed in 1.0.0."
    )
    return update_link_artifact(task_run_artifact_id, link)


def create_markdown(markdown: str) -> Optional[str]:
    """
    Create a markdown artifact

    Args:
        - markdown (str): the markdown to post

    Returns:
        - str: the task run artifact ID
    """
    warnings.warn(
        "`prefect.artifacts.create_markdown` has been moved to `prefect.backend.create_markdown_artifact`. "
        "Please update your imports. This import path will be removed in 1.0.0."
    )
    return create_markdown_artifact(markdown)


def update_markdown(task_run_artifact_id: str, markdown: str) -> None:
    """
    Update an existing markdown artifact. This function will replace the current markdown
    artifact with the new markdown provided.

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact
        - markdown (str): the new markdown to update the artifact with
    """
    warnings.warn(
        "`prefect.artifacts.update_markdown` has been moved to `prefect.backend.update_markdown_artifact`. "
        "Please update your imports. This import path will be removed in 1.0.0."
    )
    return update_markdown_artifact(task_run_artifact_id, markdown)


def delete_artifact(task_run_artifact_id: str) -> None:
    """
    Delete an existing artifact

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact
    """
    warnings.warn(
        "`prefect.artifacts.delete_artifact` has been moved to `prefect.backend.delete_artifact`. "
        "Please update your imports. This import path will be removed in 1.0.0."
    )
    return delete_artifact_new(task_run_artifact_id)

import time
from typing import Optional

from prefect import context, Client
from prefect.exceptions import ClientError


def _running_with_backend() -> bool:
    """
    Determine if running in context of a backend. This is always true when running
    using the `CloudTaskRunner`.

    Returns:
        - bool: if `_running_with_backend` is set in context
    """
    return bool(context.get("running_with_backend"))


def _create_task_run_artifact(kind: str, data: dict) -> str:
    client = Client()
    task_run_id = context.get("task_run_id")
    # XXX: there's a race condition in the cloud backend for mapped tasks where
    # the task run lookup might fail temporarily. This should last a few
    # seconds max, for now we retry a few times.
    retries = 5
    while True:
        try:
            return client.create_task_run_artifact(
                task_run_id=task_run_id, kind=kind, data=data
            )
        except ClientError as exc:
            # If it's a not found error and we still have retries left, retry
            if "not found" in str(exc).lower() and retries:
                time.sleep(1)
                retries -= 1
                continue
            raise


def create_link(link: str) -> Optional[str]:
    """
    Create a link artifact

    Args:
        - link (str): the link to post

    Returns:
        - str: the task run artifact ID
    """
    if not _running_with_backend():
        return None
    return _create_task_run_artifact("link", {"link": link})


def update_link(task_run_artifact_id: str, link: str) -> None:
    """
    Update an existing link artifact. This function will replace the current link
    artifact with the new link provided.

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact
        - link (str): the new link to update the artifact with
    """
    if not _running_with_backend():
        return

    client = Client()
    client.update_task_run_artifact(
        task_run_artifact_id=task_run_artifact_id, data={"link": link}
    )


def create_markdown(markdown: str) -> Optional[str]:
    """
    Create a markdown artifact

    Args:
        - markdown (str): the markdown to post

    Returns:
        - str: the task run artifact ID
    """
    if not _running_with_backend():
        return None
    return _create_task_run_artifact("markdown", {"markdown": markdown})


def update_markdown(task_run_artifact_id: str, markdown: str) -> None:
    """
    Update an existing markdown artifact. This function will replace the current markdown
    artifact with the new markdown provided.

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact
        - markdown (str): the new markdown to update the artifact with
    """
    if not _running_with_backend():
        return

    client = Client()
    client.update_task_run_artifact(
        task_run_artifact_id=task_run_artifact_id, data={"markdown": markdown}
    )


def delete_artifact(task_run_artifact_id: str) -> None:
    """
    Delete an existing artifact

    Args:
        - task_run_artifact_id (str): the ID of an existing task run artifact
    """
    if not _running_with_backend():
        return

    client = Client()
    client.delete_task_run_artifact(task_run_artifact_id=task_run_artifact_id)

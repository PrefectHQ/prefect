"""
Objects for specifying deployments and utilities for loading flows from deployments.
"""

from typing import Any, Dict, Optional, Union
from uuid import UUID

from prefect.client.orchestration import PrefectClient
from prefect.client.utilities import inject_client
from prefect.context import FlowRunContext, TaskRunContext
from prefect.server.schemas.actions import ArtifactCreate
from prefect.utilities.asyncutils import sync_compatible


@inject_client
@sync_compatible
async def _create_artifact(
    type: str,
    key: Optional[str] = None,
    description: Optional[str] = None,
    data: Optional[Union[Dict[str, Any], Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    client: Optional[PrefectClient] = None,
):
    """
    Helper function to create an artifact.

    Args:
        - type (str): The type of artifact to create.
        - key (str, optional): User-specified name of the artifact.
        - description (str, optional): User-specified description of the artifact.
        - data (Union[Dict[str, Any], Any], optional): User-specified information of the artifact.
        - metadata (Dict[str, Any], optional): User-specified metadata of the artifact.

    Returns:
        - Artifact: The created artifact.
    """
    artifact_args = {}
    task_run_ctx = TaskRunContext.get()
    flow_run_ctx = FlowRunContext.get()

    if task_run_ctx:
        artifact_args["task_run_id"] = task_run_ctx.task_run.id
        artifact_args["flow_run_id"] = task_run_ctx.task_run.flow_run_id
    elif flow_run_ctx:
        artifact_args["flow_run_id"] = flow_run_ctx.flow_run.id

    if key is not None:
        artifact_args["key"] = key
    if type is not None:
        artifact_args["type"] = type
    if description is not None:
        artifact_args["description"] = description
    if data is not None:
        artifact_args["data"] = data
    if metadata is not None:
        artifact_args["metadata_"] = metadata

    artifact = ArtifactCreate(**artifact_args)

    return await client.create_artifact(artifact=artifact)


@sync_compatible
async def create_link(
    link: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Create a link artifact.

    Args:
        - link (str): The link to create.

    Returns:
        - str: The link artifact ID.
    """
    artifact = await _create_artifact(
        key=name, type="link", description=description, data=link, metadata=metadata
    )

    return artifact.id


@sync_compatible
async def create_markdown(
    markdown: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Create a markdown artifact.

    Args:
        - markdown (str): The markdown to create.

    Returns:
        - str: The markdown artifact ID.
    """
    artifact = await _create_artifact(
        key=name,
        type="markdown",
        description=description,
        data=markdown,
        metadata=metadata,
    )

    return artifact.id


@sync_compatible
async def create_table(
    table: Optional[Dict[str, Any]],
    name: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Create a table artifact.

    Args:
        - table (List[Dict[str, Any]]): The table to create.

    Returns:
        - str: The table artifact ID.
    """
    # TODO: validate table, support other formats
    artifact = await _create_artifact(
        key=name,
        type="table",
        description=description,
        data=table,
        metadata=metadata,
    )

    return artifact.id


@inject_client
@sync_compatible
async def _read_artifact(
    artifact_id: Union[str, UUID],
    client: Optional[PrefectClient] = None,
):
    """
    Helper function to read an artifact.
    """
    if isinstance(artifact_id, str):
        artifact_id = UUID(artifact_id)

    return await client.read_artifact(artifact_id=artifact_id)


@sync_compatible
async def read_markdown(
    artifact_id: Union[str, UUID],
):
    """
    Read a markdown artifact.
    """
    artifact = await _read_artifact(artifact_id=artifact_id)
    return artifact


@sync_compatible
async def read_table(
    artifact_id: Union[str, UUID],
):
    """
    Read a table artifact.
    """
    artifact = await _read_artifact(artifact_id=artifact_id)
    return artifact


@sync_compatible
async def read_link(artifact_id: Union[str, UUID]):
    """
    Read a link artifact.
    """
    artifact = await _read_artifact(artifact_id=artifact_id)
    return artifact

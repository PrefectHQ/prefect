"""
Objects for creating and reading artifacts.
"""

import json
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from prefect.client.orchestration import PrefectClient
from prefect.client.utilities import inject_client
from prefect.context import FlowRunContext, TaskRunContext
from prefect.server.schemas.actions import ArtifactCreate
from prefect.server.schemas.core import Artifact
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
) -> UUID:
    """
    Helper function to create an artifact.

    Args:
        - type: The type of artifact to create.
        - key: User-specified name of the artifact.
        - description: User-specified description of the artifact.
        - data: User-specified information of the artifact.
        - metadata: User-specified metadata of the artifact.

    Returns:
        - The table artifact ID.
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
    link_text: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> UUID:
    """
    Create a link artifact.

    Args:
        - link: The link to create.

    Returns:
        - The table artifact ID.
    """
    formatted_link = f"[{link_text}]({link})" if link_text else f"[{link}]({link})"
    artifact = await _create_artifact(
        key=name,
        type="markdown",
        description=description,
        data=formatted_link,
        metadata=metadata,
    )

    return artifact.id


@sync_compatible
async def create_markdown(
    markdown: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> UUID:
    """
    Create a markdown artifact.

    Args:
        - markdown: The markdown to create.

    Returns:
        - The table artifact ID.
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
    table: Union[Dict[str, List[Any]], List[Dict[str, Any]]],
    name: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> UUID:
    """
    Create a table artifact.

    Args:
        - table: The table to create.

    Returns:
        - The table artifact ID.
    """
    formatted_table = json.dumps(table) if isinstance(table, list) else table

    artifact = await _create_artifact(
        key=name,
        type="table",
        description=description,
        data=formatted_table,
        metadata=metadata,
    )

    return artifact.id


@inject_client
@sync_compatible
async def _read_artifact(
    artifact_id: Union[str, UUID],
    client: Optional[PrefectClient] = None,
) -> Artifact:
    """
    Helper function to read an artifact.
    """
    if isinstance(artifact_id, str):
        artifact_id = UUID(artifact_id)

    return await client.read_artifact(artifact_id=artifact_id)


@sync_compatible
async def read_markdown(
    artifact_id: Union[str, UUID],
) -> Artifact:
    """
    Read a markdown artifact.
    """
    artifact = await _read_artifact(artifact_id=artifact_id)
    return artifact


@sync_compatible
async def read_table(
    artifact_id: Union[str, UUID],
) -> Artifact:
    """
    Read a table artifact.
    """
    artifact = await _read_artifact(artifact_id=artifact_id)
    if artifact:
        if artifact.data is not None and isinstance(artifact.data, str):
            try:
                artifact.data = json.loads(artifact.data)
            except json.JSONDecodeError:
                print(
                    f"The data in table artifact with id '{artifact_id}' was in a JSON"
                    " format and could not be formatted back into a valid table. It"
                    " will be returned as a string."
                )
    return artifact


@sync_compatible
async def read_link(artifact_id: Union[str, UUID]) -> Artifact:
    """
    Read a link artifact.
    """
    artifact = await _read_artifact(artifact_id=artifact_id)
    return artifact

"""
Interface for creating and reading artifacts.
"""

import json
import math
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import ArtifactCreate
from prefect.client.utilities import inject_client
from prefect.context import FlowRunContext, TaskRunContext
from prefect.utilities.asyncutils import sync_compatible


INVALID_TABLE_TYPE_ERROR = (
    "`create_table_artifact` requires a `table` argument of type `dict[list]` or"
    " `list[dict]`."
)


@inject_client
async def _create_artifact(
    type: str,
    key: Optional[str] = None,
    description: Optional[str] = None,
    data: Optional[Union[Dict[str, Any], Any]] = None,
    client: Optional[PrefectClient] = None,
) -> UUID:
    """
    Helper function to create an artifact.

    Arguments:
        type: A string identifying the type of artifact.
        key: A user-provided string identifier.
          The key must only contain lowercase letters, numbers, and dashes.
        description: A user-specified description of the artifact.
        data: A JSON payload that allows for a result to be retrieved.
        client: The PrefectClient

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

    artifact = ArtifactCreate(**artifact_args)

    return await client.create_artifact(artifact=artifact)


@sync_compatible
async def create_link_artifact(
    link: str,
    link_text: Optional[str] = None,
    key: Optional[str] = None,
    description: Optional[str] = None,
) -> UUID:
    """
    Create a link artifact.

    Arguments:
        link: The link to create.
        link_text: The link text.
        key: A user-provided string identifier.
          Required for the artifact to show in the Artifacts page in the UI.
          The key must only contain lowercase letters, numbers, and dashes.
        description: A user-specified description of the artifact.


    Returns:
        The table artifact ID.
    """
    formatted_link = f"[{link_text}]({link})" if link_text else f"[{link}]({link})"
    artifact = await _create_artifact(
        key=key,
        type="markdown",
        description=description,
        data=formatted_link,
    )

    return artifact.id


@sync_compatible
async def create_markdown_artifact(
    markdown: str,
    key: Optional[str] = None,
    description: Optional[str] = None,
) -> UUID:
    """
    Create a markdown artifact.

    Arguments:
        markdown: The markdown to create.
        key: A user-provided string identifier.
          Required for the artifact to show in the Artifacts page in the UI.
          The key must only contain lowercase letters, numbers, and dashes.
        description: A user-specified description of the artifact.

    Returns:
        The table artifact ID.
    """
    artifact = await _create_artifact(
        key=key,
        type="markdown",
        description=description,
        data=markdown,
    )

    return artifact.id


@sync_compatible
async def create_table_artifact(
    table: Union[Dict[str, List[Any]], List[Dict[str, Any]], List[List[Any]]],
    key: Optional[str] = None,
    description: Optional[str] = None,
) -> UUID:
    """
    Create a table artifact.

    Arguments:
        table: The table to create.
        key: A user-provided string identifier.
          Required for the artifact to show in the Artifacts page in the UI.
          The key must only contain lowercase letters, numbers, and dashes.
        description: A user-specified description of the artifact.

    Returns:
        The table artifact ID.
    """

    def _sanitize_nan_values(item):
        """
        Sanitize NaN values in a given item. The item can be a dict, list or float.
        """

        if isinstance(item, list):
            return [_sanitize_nan_values(sub_item) for sub_item in item]

        elif isinstance(item, dict):
            return {k: _sanitize_nan_values(v) for k, v in item.items()}

        elif isinstance(item, float) and math.isnan(item):
            return None

        else:
            return item

    sanitized_table = _sanitize_nan_values(table)

    if isinstance(table, dict) and all(isinstance(v, list) for v in table.values()):
        pass
    elif isinstance(table, list) and all(isinstance(v, (list, dict)) for v in table):
        pass
    else:
        raise TypeError(INVALID_TABLE_TYPE_ERROR)

    formatted_table = json.dumps(sanitized_table)

    artifact = await _create_artifact(
        key=key,
        type="table",
        description=description,
        data=formatted_table,
    )

    return artifact.id

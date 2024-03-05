"""
Interface for creating and reading artifacts.
"""

import json
from typing import Any, Dict, List, Optional, Union, cast
from uuid import UUID

from pydantic import BaseModel
from regex import B
from prefect.blocks.core import _is_subclass

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import ArtifactCreate
from prefect.client.utilities import inject_client
from prefect.context import FlowRunContext, TaskRunContext
from prefect.utilities.asyncutils import sync_compatible
import abc
from prefect.client.schemas.objects import Artifact as ObjectArtifact, TaskRun, FlowRun
from prefect.utilities.tables import _sanitize_nan_values  # type: ignore


class BaseArtifact(ObjectArtifact, abc.ABC):

    def format(self) -> str:
        return json.dumps(self.data)

    def get_flow_run_id(self) -> Optional[UUID]:
        if context := TaskRunContext.get():
            return cast(TaskRun, getattr(context, "task_run")).flow_run_id
        elif context := FlowRunContext.get():
            return cast(FlowRun, getattr(context, "flow_run")).id
        else:
            return None

    def get_task_run_id(self) -> Optional[UUID]:
        if context := TaskRunContext.get():
            return cast(TaskRun, getattr(context, "task_run")).id
        else:
            return None

    @sync_compatible
    @inject_client
    async def create(self, client: Optional[PrefectClient] = None) -> UUID:
        return (
            await cast(PrefectClient, client).create_artifact(
                artifact=ArtifactCreate(
                    key=self.key,
                    type=self.type,
                    description=self.description,
                    data=self.format(),
                    metadata_=self.metadata_,
                    task_run_id=self.get_task_run_id(),
                    flow_run_id=self.get_flow_run_id(),
                )
            )
        ).id


class Link(BaseArtifact):
    type: Optional[str] = "link"
    link: str
    link_text: Optional[str] = None

    def format(self) -> str:
        return (
            f"[{self.link_text}]({self.link})"
            if self.link_text
            else f"[{self.link}]({self.link})"
        )


class Markdown(BaseArtifact):
    type: Optional[str] = "markdown"
    markdown: str

    def format(self) -> str:
        return self.markdown


class Table(BaseArtifact):
    type: Optional[str] = "table"
    table: Union[Dict[str, List[Any]], List[Dict[str, Any]], List[List[Any]]]

    def format(self) -> str:
        return json.dumps(_sanitize_nan_values(self.table))


class Artifact(BaseArtifact):
    type: Optional[str] = "json"


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
    return await Link(
        link=link,
        link_text=link_text,
        key=key,
        description=description,
    ).create()


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
    return await Markdown(
        markdown=markdown,
        key=key,
        description=description,
    ).create()


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

    return await Table(
        table=table,
        key=key,
        description=description,
    ).create()

"""
Interface for creating and reading artifacts.
"""

from __future__ import annotations

import json  # noqa: I001
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from typing_extensions import Self

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import ArtifactCreate as ArtifactRequest
from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterKey
from prefect.client.schemas.objects import Artifact as ArtifactResponse
from prefect.client.schemas.sorting import ArtifactSort
from prefect.client.utilities import get_or_create_client, inject_client
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.context import get_task_and_flow_run_ids


class Artifact(ArtifactRequest):
    """
    An artifact is a piece of data that is created by a flow or task run.
    https://docs.prefect.io/latest/concepts/artifacts/

    Arguments:
        type: A string identifying the type of artifact.
        key: A user-provided string identifier.
          The key must only contain lowercase letters, numbers, and dashes.
        description: A user-specified description of the artifact.
        data: A JSON payload that allows for a result to be retrieved.
    """

    @sync_compatible
    async def create(
        self: Self,
        client: Optional[PrefectClient] = None,
    ) -> ArtifactResponse:
        """
        A method to create an artifact.

        Arguments:
            client: The PrefectClient

        Returns:
            - The created artifact.
        """
        client, _ = get_or_create_client(client)
        task_run_id, flow_run_id = get_task_and_flow_run_ids()
        return await client.create_artifact(
            artifact=ArtifactRequest(
                type=self.type,
                key=self.key,
                description=self.description,
                task_run_id=self.task_run_id or task_run_id,
                flow_run_id=self.flow_run_id or flow_run_id,
                data=await self.format(),
            )
        )

    @classmethod
    @sync_compatible
    async def get(
        cls, key: Optional[str] = None, client: Optional[PrefectClient] = None
    ) -> Optional[ArtifactResponse]:
        """
        A method to get an artifact.

        Arguments:
            key (str, optional): The key of the artifact to get.
            client (PrefectClient, optional): The PrefectClient

        Returns:
            (ArtifactResponse, optional): The artifact (if found).
        """
        client, _ = get_or_create_client(client)
        return next(
            iter(
                await client.read_artifacts(
                    limit=1,
                    sort=ArtifactSort.UPDATED_DESC,
                    artifact_filter=ArtifactFilter(key=ArtifactFilterKey(any_=[key])),
                )
            ),
            None,
        )

    @classmethod
    @sync_compatible
    async def get_or_create(
        cls,
        key: Optional[str] = None,
        description: Optional[str] = None,
        data: Optional[Union[Dict[str, Any], Any]] = None,
        client: Optional[PrefectClient] = None,
        **kwargs: Any,
    ) -> Tuple[ArtifactResponse, bool]:
        """
        A method to get or create an artifact.

        Arguments:
            key (str, optional): The key of the artifact to get or create.
            description (str, optional): The description of the artifact to create.
            data (Union[Dict[str, Any], Any], optional): The data of the artifact to create.
            client (PrefectClient, optional): The PrefectClient

        Returns:
            (ArtifactResponse): The artifact, either retrieved or created.
        """
        artifact = await cls.get(key, client)
        if artifact:
            return artifact, False
        else:
            return (
                await cls(key=key, description=description, data=data, **kwargs).create(
                    client
                ),
                True,
            )

    async def format(self) -> Optional[Union[Dict[str, Any], Any]]:
        return json.dumps(self.data)


class LinkArtifact(Artifact):
    link: str
    link_text: Optional[str] = None
    type: Optional[str] = "markdown"

    async def format(self) -> str:
        return (
            f"[{self.link_text}]({self.link})"
            if self.link_text
            else f"[{self.link}]({self.link})"
        )


class MarkdownArtifact(Artifact):
    markdown: str
    type: Optional[str] = "markdown"

    async def format(self) -> str:
        return self.markdown


class TableArtifact(Artifact):
    table: Union[Dict[str, List[Any]], List[Dict[str, Any]], List[List[Any]]]
    type: Optional[str] = "table"

    @classmethod
    def _sanitize(
        cls, item: Union[Dict[str, Any], List[Any], float]
    ) -> Union[Dict[str, Any], List[Any], int, float, None]:
        """
        Sanitize NaN values in a given item.
        The item can be a dict, list or float.
        """
        if isinstance(item, list):
            return [cls._sanitize(sub_item) for sub_item in item]
        elif isinstance(item, dict):
            return {k: cls._sanitize(v) for k, v in item.items()}
        elif isinstance(item, float) and math.isnan(item):
            return None
        else:
            return item

    async def format(self) -> str:
        return json.dumps(self._sanitize(self.table))


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

    artifact = await Artifact(
        type=type,
        key=key,
        description=description,
        data=data,
    ).create(client)

    return artifact.id


@sync_compatible
async def create_link_artifact(
    link: str,
    link_text: Optional[str] = None,
    key: Optional[str] = None,
    description: Optional[str] = None,
    client: Optional[PrefectClient] = None,
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
    artifact = await LinkArtifact(
        key=key,
        description=description,
        link=link,
        link_text=link_text,
    ).create(client)

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
    artifact = await MarkdownArtifact(
        key=key,
        description=description,
        markdown=markdown,
    ).create()

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

    artifact = await TableArtifact(
        key=key,
        description=description,
        table=table,
    ).create()

    return artifact.id

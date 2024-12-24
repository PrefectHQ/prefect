from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Optional

from httpx import AsyncClient, Client, HTTPStatusError
from pydantic import Field
from typing_extensions import TypedDict, Unpack

from prefect.client.orchestration.routes import arequest, request
from prefect.exceptions import ObjectNotFound

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.actions import ArtifactCreate, ArtifactUpdate
    from prefect.client.schemas.filters import (
        ArtifactCollectionFilter,
        ArtifactFilter,
        FlowRunFilter,
        TaskRunFilter,
    )
    from prefect.client.schemas.objects import Artifact, ArtifactCollection
    from prefect.client.schemas.sorting import ArtifactCollectionSort, ArtifactSort


class BaseArtifactReadParams(TypedDict, total=False):
    flow_run_filter: Annotated[Optional["FlowRunFilter"], Field(default=None)]
    task_run_filter: Annotated[Optional["TaskRunFilter"], Field(default=None)]
    limit: Annotated[Optional[int], Field(default=None)]
    offset: Annotated[int, Field(default=0)]


class ArtifactReadParams(BaseArtifactReadParams, total=False):
    artifact_filter: Annotated[Optional["ArtifactFilter"], Field(default=None)]
    sort: Annotated[Optional["ArtifactSort"], Field(default=None)]


class ArtifactCollectionReadParams(BaseArtifactReadParams, total=False):
    artifact_filter: Annotated[
        Optional["ArtifactCollectionFilter"], Field(default=None)
    ]
    sort: Annotated[Optional["ArtifactCollectionSort"], Field(default=None)]


class ArtifactClient:
    def __init__(self, client: Client):
        self._client = client

    def create_artifact(self, artifact: "ArtifactCreate") -> "Artifact":
        response = request(
            self._client,
            "POST",
            "/artifacts/",
            json=artifact.model_dump(mode="json", exclude_unset=True),
        )
        from prefect.client.schemas.objects import Artifact

        return Artifact.model_validate(response.json())

    def update_artifact(self, artifact_id: "UUID", artifact: "ArtifactUpdate") -> None:
        request(
            self._client,
            "PATCH",
            "/artifacts/{artifact_id}",
            json=artifact.model_dump(mode="json", exclude_unset=True),
            path_params={"artifact_id": artifact_id},
        )
        return None

    def delete_artifact(self, artifact_id: "UUID") -> None:
        try:
            request(
                self._client,
                "DELETE",
                "/artifacts/{artifact_id}",
                path_params={"artifact_id": artifact_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise
        return None

    def read_artifacts(
        self, **kwargs: Unpack["ArtifactReadParams"]
    ) -> list["Artifact"]:
        response = request(
            self._client,
            "POST",
            "/artifacts/",
            json={
                "artifact_filter": (
                    artifact_filter.model_dump(mode="json", exclude_unset=True)
                    if (artifact_filter := kwargs.get("artifact_filter"))
                    else None
                ),
                "flow_run_filter": (
                    flow_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (flow_run_filter := kwargs.get("flow_run_filter"))
                    else None
                ),
                "task_run_filter": (
                    task_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (task_run_filter := kwargs.get("task_run_filter"))
                    else None
                ),
                "limit": kwargs.get("limit"),
                "offset": kwargs.get("offset"),
                "sort": kwargs.get("sort"),
            },
        )
        from prefect.client.schemas.objects import Artifact

        return Artifact.model_validate_list(response.json())


class ArtifactAsyncClient:
    def __init__(self, client: AsyncClient):
        self._client = client

    async def create_artifact(self, artifact: "ArtifactCreate") -> "Artifact":
        response = await arequest(
            self._client,
            "POST",
            "/artifacts/",
            json=artifact.model_dump(mode="json", exclude_unset=True),
        )
        from prefect.client.schemas.objects import Artifact

        return Artifact.model_validate(response.json())

    async def update_artifact(
        self, artifact_id: "UUID", artifact: "ArtifactUpdate"
    ) -> None:
        await arequest(
            self._client,
            "PATCH",
            "/artifacts/{artifact_id}",
            path_params={"artifact_id": artifact_id},
            json=artifact.model_dump(mode="json", exclude_unset=True),
        )
        return None

    async def read_artifacts(
        self, **kwargs: Unpack["ArtifactReadParams"]
    ) -> list["Artifact"]:
        response = await arequest(
            self._client,
            "POST",
            "/artifacts/",
            params={
                "artifact_filter": (
                    artifact_filter.model_dump(mode="json", exclude_unset=True)
                    if (artifact_filter := kwargs.get("artifact_filter"))
                    else None
                ),
                "flow_run_filter": (
                    flow_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (flow_run_filter := kwargs.get("flow_run_filter"))
                    else None
                ),
                "task_run_filter": (
                    task_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (task_run_filter := kwargs.get("task_run_filter"))
                    else None
                ),
                "limit": kwargs.get("limit", None),
                "offset": kwargs.get("offset", 0),
                "sort": kwargs.get("sort", None),
            },
        )
        from prefect.client.schemas.objects import Artifact

        return Artifact.model_validate_list(response.json())

    async def delete_artifact(self, artifact_id: "UUID") -> None:
        try:
            await arequest(
                self._client,
                "DELETE",
                "/artifacts/{artifact_id}",
                path_params={"artifact_id": artifact_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise


class ArtifactCollectionClient:
    def __init__(self, client: Client):
        self._client = client

    def read_latest_artifacts(
        self, **kwargs: Unpack["ArtifactCollectionReadParams"]
    ) -> list["ArtifactCollection"]:
        response = request(
            self._client,
            "POST",
            "/artifacts/latest/filter",
            json={
                "artifact_filter": (
                    artifact_filter.model_dump(mode="json", exclude_unset=True)
                    if (artifact_filter := kwargs.get("artifact_filter"))
                    else None
                ),
                "flow_run_filter": (
                    flow_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (flow_run_filter := kwargs.get("flow_run_filter"))
                    else None
                ),
                "task_run_filter": (
                    task_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (task_run_filter := kwargs.get("task_run_filter"))
                    else None
                ),
                "limit": kwargs.get("limit", None),
                "offset": kwargs.get("offset", 0),
                "sort": kwargs.get("sort", None),
            },
        )
        return ArtifactCollection.model_validate_list(response.json())


class ArtifactCollectionAsyncClient:
    def __init__(self, client: AsyncClient):
        self._client = client

    async def read_latest_artifacts(
        self, **kwargs: Unpack["ArtifactCollectionReadParams"]
    ) -> list["ArtifactCollection"]:
        response = await arequest(
            self._client,
            "POST",
            "/artifacts/latest/filter",
            json={
                "artifact_filter": (
                    artifact_filter.model_dump(mode="json", exclude_unset=True)
                    if (artifact_filter := kwargs.get("artifact_filter"))
                    else None
                ),
                "flow_run_filter": (
                    flow_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (flow_run_filter := kwargs.get("flow_run_filter"))
                    else None
                ),
                "task_run_filter": (
                    task_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (task_run_filter := kwargs.get("task_run_filter"))
                    else None
                ),
                "limit": kwargs.get("limit", None),
                "offset": kwargs.get("offset", 0),
                "sort": kwargs.get("sort", None),
            },
        )
        return ArtifactCollection.model_validate_list(response.json())

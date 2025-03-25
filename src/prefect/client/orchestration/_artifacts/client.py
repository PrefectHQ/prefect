from typing import TYPE_CHECKING, Annotated, Optional

from httpx import HTTPStatusError
from pydantic import Field
from typing_extensions import TypedDict, Unpack

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
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


class ArtifactClient(BaseClient):
    def create_artifact(self, artifact: "ArtifactCreate") -> "Artifact":
        response = self.request(
            "POST",
            "/artifacts/",
            json=artifact.model_dump(mode="json", exclude_unset=True),
        )
        from prefect.client.schemas.objects import Artifact

        return Artifact.model_validate(response.json())

    def update_artifact(self, artifact_id: "UUID", artifact: "ArtifactUpdate") -> None:
        self.request(
            "PATCH",
            "/artifacts/{id}",
            json=artifact.model_dump(mode="json", exclude_unset=True),
            path_params={"id": artifact_id},
        )
        return None

    def delete_artifact(self, artifact_id: "UUID") -> None:
        try:
            self.request(
                "DELETE",
                "/artifacts/{id}",
                path_params={"id": artifact_id},
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
        response = self.request(
            "POST",
            "/artifacts/filter",
            json={
                "artifacts": (
                    artifact_filter.model_dump(mode="json", exclude_unset=True)
                    if (artifact_filter := kwargs.get("artifact_filter"))
                    else None
                ),
                "flow_runs": (
                    flow_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (flow_run_filter := kwargs.get("flow_run_filter"))
                    else None
                ),
                "task_runs": (
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


class ArtifactAsyncClient(BaseAsyncClient):
    async def create_artifact(self, artifact: "ArtifactCreate") -> "Artifact":
        response = await self.request(
            "POST",
            "/artifacts/",
            json=artifact.model_dump(mode="json", exclude_unset=True),
        )
        from prefect.client.schemas.objects import Artifact

        return Artifact.model_validate(response.json())

    async def update_artifact(
        self, artifact_id: "UUID", artifact: "ArtifactUpdate"
    ) -> None:
        await self.request(
            "PATCH",
            "/artifacts/{id}",
            path_params={"id": artifact_id},
            json=artifact.model_dump(mode="json", exclude_unset=True),
        )
        return None

    async def read_artifacts(
        self, **kwargs: Unpack["ArtifactReadParams"]
    ) -> list["Artifact"]:
        response = await self.request(
            "POST",
            "/artifacts/filter",
            json={
                "artifacts": (
                    artifact_filter.model_dump(mode="json", exclude_unset=True)
                    if (artifact_filter := kwargs.get("artifact_filter"))
                    else None
                ),
                "flow_runs": (
                    flow_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (flow_run_filter := kwargs.get("flow_run_filter"))
                    else None
                ),
                "task_runs": (
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
            await self.request(
                "DELETE",
                "/artifacts/{id}",
                path_params={"id": artifact_id},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise


class ArtifactCollectionClient(BaseClient):
    def read_latest_artifacts(
        self, **kwargs: Unpack["ArtifactCollectionReadParams"]
    ) -> list["ArtifactCollection"]:
        response = self.request(
            "POST",
            "/artifacts/latest/filter",
            json={
                "artifacts": (
                    artifact_filter.model_dump(mode="json", exclude_unset=True)
                    if (artifact_filter := kwargs.get("artifact_filter"))
                    else None
                ),
                "flow_runs": (
                    flow_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (flow_run_filter := kwargs.get("flow_run_filter"))
                    else None
                ),
                "task_runs": (
                    task_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (task_run_filter := kwargs.get("task_run_filter"))
                    else None
                ),
                "limit": kwargs.get("limit", None),
                "offset": kwargs.get("offset", 0),
                "sort": kwargs.get("sort", None),
            },
        )
        from prefect.client.schemas.objects import ArtifactCollection

        return ArtifactCollection.model_validate_list(response.json())


class ArtifactCollectionAsyncClient(BaseAsyncClient):
    async def read_latest_artifacts(
        self, **kwargs: Unpack["ArtifactCollectionReadParams"]
    ) -> list["ArtifactCollection"]:
        response = await self.request(
            "POST",
            "/artifacts/latest/filter",
            json={
                "artifacts": (
                    artifact_filter.model_dump(mode="json", exclude_unset=True)
                    if (artifact_filter := kwargs.get("artifact_filter"))
                    else None
                ),
                "flow_runs": (
                    flow_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (flow_run_filter := kwargs.get("flow_run_filter"))
                    else None
                ),
                "task_runs": (
                    task_run_filter.model_dump(mode="json", exclude_unset=True)
                    if (task_run_filter := kwargs.get("task_run_filter"))
                    else None
                ),
                "limit": kwargs.get("limit", None),
                "offset": kwargs.get("offset", 0),
                "sort": kwargs.get("sort", None),
            },
        )
        from prefect.client.schemas.objects import ArtifactCollection

        return ArtifactCollection.model_validate_list(response.json())

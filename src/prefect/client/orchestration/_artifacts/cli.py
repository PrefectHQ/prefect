from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Protocol

from typer import Argument, Option
from typer import Context as BaseContext
from typing_extensions import TypedDict

if TYPE_CHECKING:
    from uuid import UUID

    from rich.console import Console

    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import Artifact, ArtifactCollection


class ContextMeta(TypedDict):
    get_client: Callable[[], "PrefectClient"]
    console: Console


class ClientProvider(Protocol):
    def meta(self) -> ContextMeta: ...


class Context(BaseContext, ClientProvider):
    pass


async def read(
    context: Context,
    limit: int = Option(
        10, "--limit", help="The maximum number of artifacts to return."
    ),
    offset: int = Option(0, "--offset", help="The offset of the artifacts to return."),
) -> list["Artifact"]:
    async with context.meta["get_client"]() as client:
        return await client.read_artifacts(
            limit=limit,
            offset=offset,
        )


async def latest(
    context: Context,
    limit: int = Option(
        100, "--limit", help="The maximum number of artifacts to return."
    ),
    offset: int = Option(0, "--offset", help="The offset of the artifacts to return."),
) -> list["ArtifactCollection"]:
    async with context.meta["get_client"]() as client:
        return await client.read_latest_artifacts(
            limit=limit,
            offset=offset,
        )


async def get(
    context: Context,
    key: str,
    limit: int = Option(
        100, "--limit", help="The maximum number of artifacts to return."
    ),
    offset: int = Option(0, "--offset", help="The offset of the artifacts to return."),
) -> "Artifact | None":
    async with context.meta["get_client"]() as client:
        from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterKey

        return next(
            iter(
                await client.read_artifacts(
                    artifact_filter=ArtifactFilter(key=ArtifactFilterKey(any_=[key])),
                    limit=limit,
                    offset=offset,
                )
            )
        )


async def delete(
    context: Context,
    key: str | None = Argument(None, help="The key of the artifact to delete."),
    artifact_id: UUID | None = Option(
        None, "--id", help="The ID of the artifact to delete."
    ),
) -> None:
    async with context.meta["get_client"]() as client:
        if artifact_id is not None:
            await client.delete_artifact(artifact_id)
        elif key is not None:
            from prefect.client.schemas.filters import (
                ArtifactFilter,
                ArtifactFilterId,
                ArtifactFilterKey,
            )

            if artifact := next(
                iter(
                    await client.read_artifacts(
                        artifact_filter=ArtifactFilter(
                            id=artifact_id and ArtifactFilterId(any_=[artifact_id]),
                            key=ArtifactFilterKey(any_=[key]),
                        ),
                        limit=1,
                    )
                )
            ):
                await client.delete_artifact(artifact.id)

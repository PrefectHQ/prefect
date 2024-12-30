from __future__ import annotations

from typing import Optional
from uuid import UUID

import typer
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterKey
from prefect.client.schemas.sorting import ArtifactCollectionSort, ArtifactSort
from prefect.exceptions import ObjectNotFound

artifact_app: PrefectTyper = PrefectTyper(
    name="artifact", help="Inspect and delete artifacts."
)
app.add_typer(artifact_app)


@artifact_app.command("ls")
async def list_artifacts(
    limit: int = typer.Option(
        100,
        "--limit",
        help="The maximum number of artifacts to return.",
    ),
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Whether or not to only return the latest version of each artifact.",
    ),
):
    """
    List artifacts.
    """
    table = Table(
        title="Artifacts",
        caption="List Artifacts using `prefect artifact ls`",
        show_header=True,
    )

    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Key", style="blue", no_wrap=True)
    table.add_column("Type", style="blue", no_wrap=True)
    table.add_column("Updated", style="blue", no_wrap=True)

    async with get_client() as client:
        if all:
            artifacts = await client.read_artifacts(
                sort=ArtifactSort.KEY_ASC,
                limit=limit,
            )

            for artifact in sorted(artifacts, key=lambda x: f"{x.key}"):
                updated = artifact.updated.diff_for_humans() if artifact.updated else ""
                table.add_row(
                    str(artifact.id),
                    artifact.key,
                    artifact.type,
                    updated,
                )

        else:
            artifacts = await client.read_latest_artifacts(
                sort=ArtifactCollectionSort.KEY_ASC,
                limit=limit,
            )

            for artifact in sorted(artifacts, key=lambda x: f"{x.key}"):
                updated = artifact.updated.diff_for_humans() if artifact.updated else ""
                table.add_row(
                    str(artifact.latest_id),
                    artifact.key,
                    artifact.type,
                    updated,
                )

        app.console.print(table)


@artifact_app.command("inspect")
async def inspect(
    key: str,
    limit: int = typer.Option(
        10,
        "--limit",
        help="The maximum number of artifacts to return.",
    ),
):
    """
        View details about an artifact.

        Arguments:
            key: the key of the artifact to inspect

        Examples:
            $ prefect artifact inspect "my-artifact"
           [
            {
                'id': 'ba1d67be-0bd7-452e-8110-247fe5e6d8cc',
                'created': '2023-03-21T21:40:09.895910+00:00',
                'updated': '2023-03-21T21:40:09.895910+00:00',
                'key': 'my-artifact',
                'type': 'markdown',
                'description': None,
                'data': 'my markdown',
                'metadata_': None,
                'flow_run_id': '8dc54b6f-6e24-4586-a05c-e98c6490cb98',
                'task_run_id': None
            },
            {
                'id': '57f235b5-2576-45a5-bd93-c829c2900966',
                'created': '2023-03-27T23:16:15.536434+00:00',
                'updated': '2023-03-27T23:16:15.536434+00:00',
                'key': 'my-artifact',
                'type': 'markdown',
                'description': 'my-artifact-description',
                'data': 'my markdown',
                'metadata_': None,
                'flow_run_id': 'ffa91051-f249-48c1-ae0f-4754fcb7eb29',
                'task_run_id': None
            }
    ]
    """

    async with get_client() as client:
        artifacts = await client.read_artifacts(
            limit=limit,
            sort=ArtifactSort.UPDATED_DESC,
            artifact_filter=ArtifactFilter(key=ArtifactFilterKey(any_=[key])),
        )
        if not artifacts:
            exit_with_error(f"Artifact {key!r} not found.")

        artifacts = [a.model_dump(mode="json") for a in artifacts]

        app.console.print(Pretty(artifacts))


@artifact_app.command("delete")
async def delete(
    key: Optional[str] = typer.Argument(
        None, help="The key of the artifact to delete."
    ),
    artifact_id: Optional[UUID] = typer.Option(
        None, "--id", help="The ID of the artifact to delete."
    ),
):
    """
    Delete an artifact.

    Arguments:
        key: the key of the artifact to delete

    Examples:
        $ prefect artifact delete "my-artifact"
    """
    if key and artifact_id:
        exit_with_error("Please provide either a key or an artifact_id but not both.")

    async with get_client() as client:
        if artifact_id is not None:
            try:
                if is_interactive() and not typer.confirm(
                    (
                        "Are you sure you want to delete artifact with id"
                        f" {str(artifact_id)!r}?"
                    ),
                    default=False,
                ):
                    exit_with_error("Deletion aborted.")

                await client.delete_artifact(artifact_id)
                exit_with_success(f"Deleted artifact with id {str(artifact_id)!r}.")
            except ObjectNotFound:
                exit_with_error(f"Artifact with id {str(artifact_id)!r} not found!")

        elif key is not None:
            artifacts = await client.read_artifacts(
                artifact_filter=ArtifactFilter(key=ArtifactFilterKey(any_=[key])),
            )
            if not artifacts:
                exit_with_error(
                    f"Artifact with key {key!r} not found. You can also specify an"
                    " artifact id with the --id flag."
                )

            if is_interactive() and not typer.confirm(
                (
                    f"Are you sure you want to delete {len(artifacts)} artifact(s) with"
                    f" key {key!r}?"
                ),
                default=False,
            ):
                exit_with_error("Deletion aborted.")

            for a in artifacts:
                await client.delete_artifact(a.id)

            exit_with_success(f"Deleted {len(artifacts)} artifact(s) with key {key!r}.")

        else:
            exit_with_error("Please provide a key or an artifact_id.")

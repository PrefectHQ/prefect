"""
Artifact command — native cyclopts implementation.

Inspect and delete artifacts.
"""

from typing import Annotated, Optional
from uuid import UUID

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

artifact_app: cyclopts.App = cyclopts.App(
    name="artifact",
    help="Inspect and delete artifacts.",
    version_flags=[],
    help_flags=["--help"],
)


@artifact_app.command(name="ls")
@with_cli_exception_handling
async def list_artifacts(
    *,
    limit: Annotated[
        int,
        cyclopts.Parameter(
            "--limit", help="The maximum number of artifacts to return."
        ),
    ] = 100,
    all: Annotated[
        bool,
        cyclopts.Parameter(
            "--all",
            alias="-a",
            help="Whether or not to only return the latest version of each artifact.",
        ),
    ] = False,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """List artifacts."""
    import orjson
    from rich.table import Table

    from prefect.client.orchestration import get_client
    from prefect.client.schemas.sorting import ArtifactCollectionSort, ArtifactSort
    from prefect.types._datetime import human_friendly_diff

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        if all:
            artifacts = await client.read_artifacts(
                sort=ArtifactSort.KEY_ASC,
                limit=limit,
            )
        else:
            artifacts = await client.read_latest_artifacts(
                sort=ArtifactCollectionSort.KEY_ASC,
                limit=limit,
            )

    if output and output.lower() == "json":
        artifacts_json = [artifact.model_dump(mode="json") for artifact in artifacts]
        json_output = orjson.dumps(artifacts_json, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
        table = Table(
            title="Artifacts",
            caption="List Artifacts using `prefect artifact ls`",
            show_header=True,
        )

        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Key", style="blue", no_wrap=True)
        table.add_column("Type", style="blue", no_wrap=True)
        table.add_column("Updated", style="blue", no_wrap=True)

        for artifact in sorted(artifacts, key=lambda x: x.key):
            updated = human_friendly_diff(artifact.updated) if artifact.updated else ""
            table.add_row(
                str(artifact.id if all else artifact.latest_id),
                artifact.key,
                artifact.type,
                updated,
            )

        _cli.console.print(table)


@artifact_app.command(name="inspect")
@with_cli_exception_handling
async def inspect(
    key: str,
    *,
    limit: Annotated[
        int,
        cyclopts.Parameter(
            "--limit", help="The maximum number of artifacts to return."
        ),
    ] = 10,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """View details about an artifact."""
    import orjson
    from rich.pretty import Pretty

    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterKey
    from prefect.client.schemas.sorting import ArtifactSort

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    async with get_client() as client:
        artifacts = await client.read_artifacts(
            limit=limit,
            sort=ArtifactSort.UPDATED_DESC,
            artifact_filter=ArtifactFilter(key=ArtifactFilterKey(any_=[key])),
        )
        if not artifacts:
            exit_with_error(f"Artifact {key!r} not found.")

        artifacts_json = [a.model_dump(mode="json") for a in artifacts]

        if output and output.lower() == "json":
            json_output = orjson.dumps(
                artifacts_json, option=orjson.OPT_INDENT_2
            ).decode()
            _cli.console.print(json_output)
        else:
            _cli.console.print(Pretty(artifacts_json))


@artifact_app.command(name="delete")
@with_cli_exception_handling
async def delete(
    key: Annotated[
        Optional[str],
        cyclopts.Parameter(help="The key of the artifact to delete."),
    ] = None,
    *,
    artifact_id: Annotated[
        Optional[UUID],
        cyclopts.Parameter("--id", help="The ID of the artifact to delete."),
    ] = None,
):
    """Delete an artifact."""
    from prefect.cli._prompts import confirm
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterKey
    from prefect.exceptions import ObjectNotFound

    if key and artifact_id:
        exit_with_error("Please provide either a key or an artifact_id but not both.")

    async with get_client() as client:
        if artifact_id is not None:
            try:
                if _cli.is_interactive() and not confirm(
                    (
                        "Are you sure you want to delete artifact with id"
                        f" {str(artifact_id)!r}?"
                    ),
                    default=False,
                    console=_cli.console,
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

            if _cli.is_interactive() and not confirm(
                (
                    f"Are you sure you want to delete {len(artifacts)} artifact(s) with"
                    f" key {key!r}?"
                ),
                default=False,
                console=_cli.console,
            ):
                exit_with_error("Deletion aborted.")

            for a in artifacts:
                await client.delete_artifact(a.id)

            exit_with_success(f"Deleted {len(artifacts)} artifact(s) with key {key!r}.")

        else:
            exit_with_error("Please provide a key or an artifact_id.")

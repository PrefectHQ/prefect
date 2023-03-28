import pendulum
import typer
from rich.pretty import Pretty
from rich.table import Table

from prefect import get_client
from prefect._internal.compatibility.experimental import experimental
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.server import schemas

artifact_app = PrefectTyper(
    name="artifact", help="Commands for starting and interacting with artifacts."
)
app.add_typer(artifact_app)


@artifact_app.command("ls")
@experimental(
    feature="The Artifact CLI",
    group="artifacts",
)
async def list_artifacts(
    limit: int = typer.Option(
        100,
        "--limit",
        help="The maximum number of artifacts to return.",
    ),
    latest: bool = typer.Option(
        False,
        "--latest",
        help="Whether or not to only return the latest version of each artifact.",
    ),
):
    """
    List artifacts.
    """
    async with get_client() as client:
        latest_artifact_filter = schemas.filters.ArtifactFilter(
            is_latest=schemas.filters.ArtifactFilterLatest(is_latest=latest)
        )
        artifacts = await client.read_artifacts(
            artifact_filter=latest_artifact_filter, limit=limit
        )

        table = Table(
            title="Artifacts",
            caption="List Artifacts using `prefect artifact ls`",
            show_header=True,
        )

        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Key", style="blue", no_wrap=True)
        table.add_column("Type", style="blue", no_wrap=True)
        table.add_column("Updated", style="blue", no_wrap=True)

        for artifact in sorted(artifacts, key=lambda x: f"{x.key}"):
            table.add_row(
                str(artifact.id),
                artifact.key,
                artifact.type,
                pendulum.instance(artifact.updated).diff_for_humans(),
            )

        app.console.print(table)


@artifact_app.command("inspect")
@experimental(
    feature="The Artifact CLI",
    group="artifacts",
)
async def inspect(key: str):
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
            artifact_filter=schemas.filters.ArtifactFilter(
                key=schemas.filters.ArtifactFilterKey(any_=[key])
            )
        )
        if not artifacts:
            exit_with_error(f"Artifact {key!r} not found.")

        artifacts = [a.dict(json_compatible=True) for a in artifacts]

        app.console.print(Pretty(artifacts))

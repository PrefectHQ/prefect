import pendulum
import typer
from rich.table import Table

from prefect import get_client
from prefect._internal.compatibility.experimental import experimental
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.client.orchestration import get_client
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

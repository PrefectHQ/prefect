import typer
import uvicorn

from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.experimental.workers.base import BaseWorker
from prefect.utilities.dispatch import lookup_type

worker_app = PrefectTyper(
    name="worker", help="Commands for starting and interacting with workers."
)
app.add_typer(worker_app)


@worker_app.command()
async def start(
    worker_name: str = typer.Option(..., "--name"),
    worker_pool_name: str = typer.Option(...),
    worker_type: str = typer.Option("process", "--type"),
    limit: int = typer.Option(
        None,
        "-l",
        "--limit",
        help="Maximum number of flow runs to start simultaneously.",
    ),
    port: int = typer.Option(5000, "--port"),
):
    Worker = lookup_type(BaseWorker, worker_type)
    async with Worker(
        name=worker_name, worker_pool_name=worker_pool_name, limit=limit
    ) as worker:
        config = uvicorn.Config(
            worker.create_app(),
            port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

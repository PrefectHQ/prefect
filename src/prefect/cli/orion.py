import typer
import uvicorn

from prefect.orion.api.server import app as orion_fastapi_app
from prefect.cli.base import app, console
from prefect import settings

orion_app = typer.Typer(name="orion")
app.add_typer(orion_app)


@orion_app.command()
def start(
    host: str = settings.orion.api.host,
    port: int = settings.orion.api.port,
    log_level: str = settings.orion.api.uvicorn_log_level,
    run_services: bool = True,
):
    console.print("Starting Orion API...")
    # Toggle `run_in_app` (settings are frozen and so it requires a forced update)
    # See https://github.com/PrefectHQ/orion/issues/281
    object.__setattr__(settings.orion.services, "run_in_app", run_services)
    uvicorn.run(orion_fastapi_app, host=host, port=port, log_level=log_level.lower())
    console.print("Orion stopped!")

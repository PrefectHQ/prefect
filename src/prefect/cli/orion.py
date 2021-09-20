import typer
import uvicorn

from prefect.orion.api.server import app as orion_fastapi_app
from prefect.cli.base import app, console
from prefect import settings

orion_app = typer.Typer(name="orion")
app.add_typer(orion_app)


@orion_app.command()
def start(
    host: str = "127.0.0.1",
    port: int = 5000,
    log_level: str = "info",
    run_services: bool = True,
):
    console.print("Starting Orion API...")
    # Toggle `run_in_app` (settings are frozen and so it requires a forced update)
    object.__setattr__(settings.orion.services, "run_in_app", run_services)
    uvicorn.run(orion_fastapi_app, host=host, port=port, log_level=log_level.lower())
    console.print("Orion stopped!")

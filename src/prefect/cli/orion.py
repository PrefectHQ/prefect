import typer
import uvicorn

from prefect.orion.api.server import app as orion_fastapi_app
from prefect.cli.base import app, console

orion_app = typer.Typer(name="orion")
app.add_typer(orion_app)


@orion_app.command()
def start(host: str = "127.0.0.1", port: int = 5000, log_level: str = "info"):
    console.print("Starting Orion API...")
    uvicorn.run(orion_fastapi_app, host=host, port=port, log_level=log_level.lower())
    console.print("Orion stopped!")

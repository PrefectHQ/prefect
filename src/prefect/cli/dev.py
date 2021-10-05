"""
Command line interface for working with Orion
"""
import json
import shutil
import subprocess
import os

import typer

import prefect
from prefect.cli.base import app, console
from prefect.utilities.filesystem import tmpchdir


dev_app = typer.Typer(name="dev")
app.add_typer(dev_app)


@dev_app.command()
def build_docs(
    schema_path: str = None,
):
    """
    Builds REST API reference documentation for static display.

    Note that this command only functions properly with an editable install.
    """
    # Delay this import so we don't instantiate the API uncessarily
    from prefect.orion.api.server import app as orion_fastapi_app

    schema = orion_fastapi_app.openapi()

    if not schema_path:
        schema_path = (
            prefect.__root_path__ / "docs" / "api-ref" / "schema.json"
        ).absolute()
    # overwrite info for display purposes
    schema["info"] = {}
    with open(schema_path, "w") as f:
        json.dump(schema, f)
    console.print(f"OpenAPI schema written to {schema_path}")


@dev_app.command()
def build_ui():
    with tmpchdir(prefect.__root_path__):
        with tmpchdir(prefect.__root_path__ / "orion-ui"):

            console.print("Installing npm packages...")
            subprocess.check_output(["npm", "install"])

            console.print("Building for distribution...")
            env = os.environ.copy()
            env["ORION_UI_SERVE_BASE"] = "/ui/"
            subprocess.check_output(["npm", "run", "build"], env=env)

        if os.path.exists(prefect.__ui_static_path__):
            console.print("Removing existing build files...")
            shutil.rmtree(prefect.__ui_static_path__)

        console.print("Copying build into src...")
        shutil.copytree("orion-ui/dist", prefect.__ui_static_path__)

    console.print("Complete!")

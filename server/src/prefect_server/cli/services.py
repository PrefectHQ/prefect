# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import os
import subprocess
import time
from pathlib import Path

import click
import pendulum

import prefect_server
from prefect_server import config

root_dir = Path(prefect_server.__file__).parents[2]
services_dir = root_dir / "src" / "prefect_server" / "services"


@click.group()
def services():
    """
    Commands for running services
    """


def run_proc_forever(proc):
    try:
        while True:
            time.sleep(0.5)
    except:
        click.secho("Exception caught; killing process.", fg="white", bg="red")
        proc.kill()
        raise


@services.command()
def graphql():
    """
    Start the Python GraphQL server
    """
    run_proc_forever(
        subprocess.Popen(
            ["python", services_dir / "graphql" / "server.py"],
            env=dict(os.environ, SERVER_VERSION="development"),
        )
    )


@services.command()
def ui():
    """
    Start the UI
    """
    ui_path = (
        os.environ.get("PREFECT_SERVER_WEB_UI_PATH")
        or root_dir.parent / "server-web-ui"
    )

    ui_path = Path(ui_path)

    if not ui_path.exists():
        raise RuntimeError(
            "Cannot find server-web-ui repository path. Please set PREFECT_SERVER_WEB_UI_PATH environment variable."
        )

    run_proc_forever(
        subprocess.Popen(
            ["npm", "run", "serve"],
            cwd=ui_path,
            env=dict(
                os.environ,
                SERVER_VERSION="development",
                VUE_APP_GRAPHQL_HTTP=f"http://localhost:{config.services.apollo.port}",
            ),
        )
    )


@services.command()
def scheduler():
    """
    Start the scheduler service
    """
    run_proc_forever(
        subprocess.Popen(["python", services_dir / "scheduler" / "scheduler.py"])
    )


@services.command()
def apollo():
    """
    Start the Apollo GraphQL server
    """
    run_proc_forever(
        subprocess.Popen(
            ["npm", "run", "start"],
            cwd=root_dir / "services" / "apollo",
            env=dict(
                os.environ,
                SERVER_VERSION="development",
                HASURA_API_URL=config.hasura.graphql_url,
                PREFECT_API_URL=f"http://{config.services.graphql.host}:{config.services.graphql.port}{config.services.graphql.path}",
            ),
        )
    )

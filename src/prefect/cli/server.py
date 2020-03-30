import click
import os
import subprocess
import time

from pathlib import Path
from prefect import config
from prefect.utilities.configuration import set_temporary_config


def make_env(fname=None):

    # replace localhost with postgres to use docker-compose dns
    PREFECT_ENV = dict(
        DB_CONNECTION_URL=config.server.database.connection_url.replace(
            "localhost", "postgres"
        ),
        GRAPHQL_HOST_PORT=config.server.graphql.host_port,
        UI_HOST_PORT=config.server.ui.port,
    )

    APOLLO_ENV = dict(
        HASURA_API_URL="http://hasura:{}/v1alpha1/graphql".format(
            config.server.hasura.port
        ),
        HASURA_WS_URL="ws://hasura:{}/v1alpha1/graphql".format(
            config.server.hasura.port
        ),
        PREFECT_API_URL="http://graphql:{port}{path}".format(
            port=config.server.graphql.port, path=config.server.graphql.path,
        ),
        PREFECT_API_HEALTH_URL="http://graphql:{port}/health".format(
            port=config.server.graphql.port
        ),
        APOLLO_HOST_PORT=config.server.port,
    )

    POSTGRES_ENV = dict(
        POSTGRES_HOST_PORT=config.server.database.host_port,
        POSTGRES_USER=config.server.database.username,
        POSTGRES_PASSWORD=config.server.database.password,
        POSTGRES_DB=config.server.database.name,
    )

    HASURA_ENV = dict(HASURA_HOST_PORT=config.server.hasura.host_port)

    ENV = os.environ.copy()
    ENV.update(**PREFECT_ENV, **APOLLO_ENV, **POSTGRES_ENV, **HASURA_ENV)

    if fname is not None:
        list_of_pairs = [
            "{k}={repr(v)}".format(k=k, v=v)
            if "\n" in v
            else "{k}={v}".format(k=k, v=v)
            for k, v in ENV.items()
        ]
        with open(fname, "w") as f:
            f.write("\n".join(list_of_pairs))
    return ENV.copy()


@click.group(hidden=True)
def server():
    """
    Commands for interacting with the Prefect Server

    \b
    Usage:
        $ prefect server ...

    \b
    Arguments:
        start   ...

    \b
    Examples:
        $ prefect server start
        ...
    """


@server.command(hidden=True)
@click.option(
    "--version",
    "-v",
    help="The server image versions to use (for example, '0.10.0' or 'master')",
    # TODO: update this default to use prefect.__version__ logic
    default="latest",
)
@click.option(
    "--skip-pull",
    help="Pass this flag to skip pulling new images (if available)",
    is_flag=True,
)
@click.option(
    "--no-upgrade",
    "-n",
    help="Pass this flag to avoid running a database upgrade when the database spins up",
    is_flag=True,
)
@click.option(
    "--no-ui", "-u", help="Pass this flag to avoid starting the UI", is_flag=True,
)
@click.option(
    "--postgres-port",
    help="The port used to serve Postgres",
    default=config.server.database.host_port,
    type=str,
)
@click.option(
    "--hasura-port",
    help="The port used to serve Hasura",
    default=config.server.hasura.host_port,
    type=str,
)
@click.option(
    "--graphql-port",
    help="The port used to serve the GraphQL API",
    default=config.server.graphql.host_port,
    type=str,
)
@click.option(
    "--ui-port",
    help="The port used to serve the UI",
    default=config.server.ui.port,
    type=str,
)
@click.option(
    "--server-port",
    help="The port used to serve the Core server",
    default=config.server.port,
    type=str,
)
def start(
    version,
    skip_pull,
    no_upgrade,
    no_ui,
    postgres_port,
    hasura_port,
    graphql_port,
    ui_port,
    server_port,
):
    """
    This command spins up all infrastructure and services for Prefect Server
    """
    docker_dir = Path(__file__).parents[0]

    # Temporary config set for port allocation
    with set_temporary_config(
        {
            "server.database.host_port": postgres_port,
            "server.hasura.host_port": hasura_port,
            "server.graphql.host_port": graphql_port,
            "server.ui.port": ui_port,
            "server.port": server_port,
        }
    ):
        env = make_env()

    if "PREFECT_SERVER_TAG" not in env:
        env.update(PREFECT_SERVER_TAG=version)
    if "PREFECT_SERVER_DB_CMD" not in env:
        cmd = (
            "prefect-server database upgrade -y"
            if not no_upgrade
            else "echo 'DATABASE MIGRATIONS SKIPPED'"
        )
        env.update(PREFECT_SERVER_DB_CMD=cmd)

    proc = None
    try:
        if not skip_pull:
            subprocess.check_call(["docker-compose", "pull"], cwd=docker_dir, env=env)

        cmd = ["docker-compose", "up"]
        if no_ui:
            cmd += ["--scale", "ui=0"]
        proc = subprocess.Popen(cmd, cwd=docker_dir, env=env)
        while True:
            time.sleep(0.5)
    except:
        click.secho(
            "Exception caught; killing services (press ctrl-C to force)",
            fg="white",
            bg="red",
        )
        subprocess.check_output(["docker-compose", "down"], cwd=docker_dir, env=env)
        if proc:
            proc.kill()
        raise

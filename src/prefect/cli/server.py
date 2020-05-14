import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import click
import yaml

import prefect
from prefect import config
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.docker_util import platform_is_linux, get_docker_ip


def make_env(fname=None):
    # replace localhost with postgres to use docker-compose dns
    PREFECT_ENV = dict(
        DB_CONNECTION_URL=config.server.database.connection_url.replace(
            "localhost", "postgres"
        ),
        GRAPHQL_HOST_PORT=config.server.graphql.host_port,
        UI_HOST_PORT=config.server.ui.host_port,
    )

    APOLLO_ENV = dict(
        HASURA_API_URL="http://hasura:{}/v1alpha1/graphql".format(
            config.server.hasura.port
        ),
        HASURA_WS_URL="ws://hasura:{}/v1alpha1/graphql".format(
            config.server.hasura.port
        ),
        PREFECT_API_URL="http://graphql:{port}{path}".format(
            port=config.server.graphql.port, path=config.server.graphql.path
        ),
        PREFECT_API_HEALTH_URL="http://graphql:{port}/health".format(
            port=config.server.graphql.port
        ),
        APOLLO_HOST_PORT=config.server.host_port,
        PREFECT_SERVER__TELEMETRY__ENABLED=(
            "true" if config.server.telemetry.enabled is True else "false"
        ),
    )

    POSTGRES_ENV = dict(
        POSTGRES_HOST_PORT=config.server.database.host_port,
        POSTGRES_USER=config.server.database.username,
        POSTGRES_PASSWORD=config.server.database.password,
        POSTGRES_DB=config.server.database.name,
    )

    UI_ENV = dict(GRAPHQL_URL=config.server.ui.graphql_url)

    HASURA_ENV = dict(HASURA_HOST_PORT=config.server.hasura.host_port)

    ENV = os.environ.copy()
    ENV.update(**PREFECT_ENV, **APOLLO_ENV, **POSTGRES_ENV, **UI_ENV, **HASURA_ENV)

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
    Commands for interacting with the Prefect Core server

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
    hidden=True,
)
@click.option(
    "--skip-pull",
    help="Pass this flag to skip pulling new images (if available)",
    is_flag=True,
    hidden=True,
)
@click.option(
    "--no-upgrade",
    "-n",
    help="Pass this flag to avoid running a database upgrade when the database spins up",
    is_flag=True,
    hidden=True,
)
@click.option(
    "--no-ui",
    "-u",
    help="Pass this flag to avoid starting the UI",
    is_flag=True,
    hidden=True,
)
@click.option(
    "--postgres-port",
    help="The port used to serve Postgres",
    default=config.server.database.host_port,
    type=str,
    hidden=True,
)
@click.option(
    "--hasura-port",
    help="The port used to serve Hasura",
    default=config.server.hasura.host_port,
    type=str,
    hidden=True,
)
@click.option(
    "--graphql-port",
    help="The port used to serve the GraphQL API",
    default=config.server.graphql.host_port,
    type=str,
    hidden=True,
)
@click.option(
    "--ui-port",
    help="The port used to serve the UI",
    default=config.server.ui.host_port,
    type=str,
    hidden=True,
)
@click.option(
    "--server-port",
    help="The port used to serve the Core server",
    default=config.server.host_port,
    type=str,
    hidden=True,
)
@click.option(
    "--no-postgres-port",
    help="Disable port map of Postgres to host",
    is_flag=True,
    hidden=True,
)
@click.option(
    "--no-hasura-port",
    help="Disable port map of Hasura to host",
    is_flag=True,
    hidden=True,
)
@click.option(
    "--no-graphql-port",
    help="Disable port map of the GraphqlAPI to host",
    is_flag=True,
    hidden=True,
)
@click.option(
    "--no-ui-port", help="Disable port map of the UI to host", is_flag=True, hidden=True
)
@click.option(
    "--no-server-port",
    help="Disable port map of the Core server to host",
    is_flag=True,
    hidden=True,
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
    no_postgres_port,
    no_hasura_port,
    no_graphql_port,
    no_ui_port,
    no_server_port,
):
    """
    This command spins up all infrastructure and services for the Prefect Core server

    \b
    Options:
        --version, -v   TEXT    The server image versions to use (for example, '0.10.0' or 'master')
                                Defaults to the current installed Prefect version.
        --skip-pull             Flag to skip pulling new images (if available)
        --no-upgrade, -n        Flag to avoid running a database upgrade when the database spins up
        --no-ui, -u             Flag to avoid starting the UI

    \b
        --postgres-port TEXT    Port used to serve Postgres, defaults to '5432'
        --hasura-port   TEXT    Port used to serve Hasura, defaults to '3001'
        --graphql-port  TEXT    Port used to serve the GraphQL API, defaults to '4001'
        --ui-port       TEXT    Port used to serve the UI, defaults to '8080'
        --server-port   TEXT    Port used to serve the Core server, defaults to '4200'

    \b
        --no-postgres-port      Disable port map of Postgres to host
        --no-hasura-port        Disable port map of Hasura to host
        --no-graphql-port       Disable port map of the GraphQL API to host
        --no-ui-port            Disable port map of the UI to host
        --no-server-port        Disable port map of the Core server to host
    """

    docker_dir = Path(__file__).parents[0]
    compose_dir_path = docker_dir

    # Remove port mappings if specified
    if (
        no_postgres_port
        or no_hasura_port
        or no_graphql_port
        or no_ui_port
        or no_server_port
        or platform_is_linux()
    ):
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, "docker-compose.yml")
        shutil.copy2(os.path.join(docker_dir, "docker-compose.yml"), temp_path)

        with open(temp_path, "r") as file:
            y = yaml.safe_load(file)

            if no_postgres_port:
                del y["services"]["postgres"]["ports"]

            if no_hasura_port:
                del y["services"]["hasura"]["ports"]

            if no_graphql_port:
                del y["services"]["graphql"]["ports"]

            if no_ui_port:
                del y["services"]["ui"]["ports"]

            if no_server_port:
                del y["services"]["apollo"]["ports"]

            if platform_is_linux():
                docker_internal_ip = get_docker_ip()
                for service in list(y["services"]):
                    y["services"][service]["extra_hosts"] = [
                        "host.docker.internal:{}".format(docker_internal_ip)
                    ]

        with open(temp_path, "w") as f:
            y = yaml.safe_dump(y, f)

        compose_dir_path = temp_dir

    # Temporary config set for port allocation
    with set_temporary_config(
        {
            "server.database.host_port": postgres_port,
            "server.hasura.host_port": hasura_port,
            "server.graphql.host_port": graphql_port,
            "server.ui.host_port": ui_port,
            "server.host_port": server_port,
        }
    ):
        env = make_env()

    if "PREFECT_SERVER_TAG" not in env:
        env.update(
            PREFECT_SERVER_TAG=version
            or (
                "master"
                if len(prefect.__version__.split("+")) > 1
                else prefect.__version__
            )
        )
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
            subprocess.check_call(
                ["docker-compose", "pull"], cwd=compose_dir_path, env=env
            )

        cmd = ["docker-compose", "up"]
        if no_ui:
            cmd += ["--scale", "ui=0"]
        proc = subprocess.Popen(cmd, cwd=compose_dir_path, env=env)
        while True:
            time.sleep(0.5)
    except:
        click.secho(
            "Exception caught; killing services (press ctrl-C to force)",
            fg="white",
            bg="red",
        )
        subprocess.check_output(
            ["docker-compose", "down"], cwd=compose_dir_path, env=env
        )
        if proc:
            proc.kill()
        raise

import click
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import warnings
from pathlib import Path

import yaml

import prefect
from prefect import config
from prefect.utilities.cli import add_options


@click.group(hidden=True)
def server():
    """
    Commands for interacting with the Prefect Core server

    \b
    Usage:
        $ prefect server [COMMAND]

    \b
    Arguments:
        start                   Start Prefect Server using docker-compose
        stop                    Stop Prefect Server by removing all containers and networks
        create-tenant           Creates a new tenant in the server instance
                                    Note: running `start` already creates a default tenant
        config                  Write the configured docker-compose.yml to standard
                                    output for manual deployment

    \b
    Examples:
        $ prefect server start
        ...

        $ prefect server config > docker-compose.yml
    """


COMMON_SERVER_OPTIONS = [
    click.option(
        "--version",
        "-v",
        help="The server image versions to use (for example, '0.1.0' or 'master')",
        hidden=True,
    ),
    click.option(
        "--ui-version",
        "-uv",
        help="The UI image version to use (for example, '0.1.0' or 'master')",
        hidden=True,
    ),
    click.option(
        "--no-upgrade",
        "-n",
        help="Pass this flag to avoid running a database upgrade when the database spins up",
        is_flag=True,
        hidden=True,
    ),
    click.option(
        "--no-ui",
        "-u",
        help="Pass this flag to avoid starting the UI",
        is_flag=True,
        hidden=True,
    ),
    click.option(
        "--external-postgres",
        "-ep",
        help="This will remove the Postgres service from the docker-compose setup",
        is_flag=True,
        hidden=True,
    ),
    click.option(
        "--postgres-url",
        help="Postgres connection url to use. Expected format is "
        "postgres://<username>:<password>@hostname:<port>/<dbname>",
        default=None,
        type=str,
        hidden=True,
    ),
    click.option(
        "--postgres-port",
        help="The port used to serve Postgres. Not valid for external Postgres.",
        default=config.server.database.host_port,
        type=str,
        hidden=True,
    ),
    click.option(
        "--hasura-port",
        help="The port used to serve Hasura",
        default=config.server.hasura.host_port,
        type=str,
        hidden=True,
    ),
    click.option(
        "--graphql-port",
        help="The port used to serve the GraphQL API",
        default=config.server.graphql.host_port,
        type=str,
        hidden=True,
    ),
    click.option(
        "--ui-port",
        help="The port used to serve the UI",
        default=config.server.ui.host_port,
        type=str,
        hidden=True,
    ),
    click.option(
        "--server-port",
        help="The port used to serve the Core server",
        default=config.server.host_port,
        type=str,
        hidden=True,
    ),
    click.option(
        "--no-postgres-port",
        help="Disable port map of Postgres to host. Not valid for external Postgres.",
        is_flag=True,
        hidden=True,
    ),
    click.option(
        "--no-hasura-port",
        help="Disable port map of Hasura to host",
        is_flag=True,
        hidden=True,
    ),
    click.option(
        "--no-graphql-port",
        help="Disable port map of the GraphqlAPI to host",
        is_flag=True,
        hidden=True,
    ),
    click.option(
        "--no-ui-port",
        help="Disable port map of the UI to host",
        is_flag=True,
        hidden=True,
    ),
    click.option(
        "--no-server-port",
        help="Disable port map of the Core server to host",
        is_flag=True,
        hidden=True,
    ),
    click.option(
        "--use-volume",
        help="Enable the use of a volume for the postgres service. Not valid for external Postgres.",
        is_flag=True,
        hidden=True,
    ),
    click.option(
        "--volume-path",
        help="A path to use for the postgres volume. Not valid for external Postgres.",
        default=config.server.database.volume_path,
        type=str,
        hidden=True,
    ),
]


def setup_compose_file(
    no_ui=False,
    external_postgres=False,
    no_postgres_port=False,
    no_hasura_port=False,
    no_graphql_port=False,
    no_ui_port=False,
    no_server_port=False,
    use_volume=True,
    temp_dir: str = None,
) -> str:
    # Defaults should be set in the `click` command option, these defaults are to
    # simplify testing

    base_compose_path = Path(__file__).parents[0].joinpath("docker-compose.yml")

    temp_dir = temp_dir or tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, "docker-compose.yml")

    # Copy the docker-compose file to the temp location
    shutil.copy2(base_compose_path, temp_path)

    # Exit early if no changes have been made to the compose file
    if not (
        no_postgres_port
        or external_postgres
        or no_hasura_port
        or no_graphql_port
        or no_ui_port
        or no_server_port
        or not use_volume
        or no_ui
    ):
        return temp_path

    # Otherwise, modify the file
    with open(temp_path, "r") as file:
        compose_yml = yaml.safe_load(file)

        if no_postgres_port:
            del compose_yml["services"]["postgres"]["ports"]

        if no_hasura_port:
            del compose_yml["services"]["hasura"]["ports"]

        if no_graphql_port:
            del compose_yml["services"]["graphql"]["ports"]

        if no_ui_port:
            del compose_yml["services"]["ui"]["ports"]

        if no_server_port:
            del compose_yml["services"]["apollo"]["ports"]

        if not use_volume:
            del compose_yml["services"]["postgres"]["volumes"]

        if no_ui:
            del compose_yml["services"]["ui"]

        if external_postgres:
            del compose_yml["services"]["postgres"]
            compose_yml["services"]["hasura"]["depends_on"].remove("postgres")

    with open(temp_path, "w") as f:
        yaml.safe_dump(compose_yml, f)

    return temp_path


def setup_compose_env(
    version=None,
    ui_version=None,
    no_upgrade=None,
    external_postgres=False,
    postgres_url=None,
    postgres_port=None,
    hasura_port=None,
    graphql_port=None,
    ui_port=None,
    server_port=None,
    volume_path=None,
):
    # Defaults should be set in the `click` command option, these should _not_ be `None`
    # at runtime.

    # if postgres url is provided explicitly, we're using external postgres
    if postgres_url:
        external_postgres = True

    # Pull current version information
    base_version = prefect.__version__.split("+")
    if len(base_version) > 1:
        default_tag = "master"
    else:
        default_tag = f"core-{base_version[0]}"

    db_connection_url = (
        config.server.database.connection_url if postgres_url is None else postgres_url
    )
    if not external_postgres:
        # replace localhost with postgres to use docker-compose dns
        db_connection_url = db_connection_url.replace("localhost", "postgres")

    PREFECT_ENV = dict(
        DB_CONNECTION_URL=db_connection_url,
        GRAPHQL_HOST_PORT=str(graphql_port),
        UI_HOST_PORT=str(ui_port),
        # Pass the Core version so the Server API can return it
        PREFECT_CORE_VERSION=prefect.__version__,
        # Set the server image tag
        PREFECT_SERVER_TAG=version or default_tag,
    )

    APOLLO_ENV = dict(
        HASURA_API_URL=f"http://hasura:{hasura_port}/v1alpha1/graphql",
        HASURA_WS_URL=f"ws://hasura:{hasura_port}/v1alpha1/graphql",
        PREFECT_API_URL=f"http://graphql:{graphql_port}{config.server.graphql.path}",
        PREFECT_API_HEALTH_URL=f"http://graphql:{graphql_port}/health",
        APOLLO_HOST_PORT=str(server_port),
        PREFECT_SERVER__TELEMETRY__ENABLED=(
            "true" if config.server.telemetry.enabled is True else "false"
        ),
    )

    POSTGRES_ENV = (
        dict(
            POSTGRES_HOST_PORT=str(postgres_port),
            POSTGRES_USER=config.server.database.username,
            POSTGRES_PASSWORD=config.server.database.password,
            POSTGRES_DB=config.server.database.name,
            POSTGRES_DATA_PATH=volume_path,
        )
        if not external_postgres
        else dict()
    )

    UI_ENV = dict(
        APOLLO_URL=config.server.ui.apollo_url, PREFECT_UI_TAG=ui_version or default_tag
    )

    HASURA_ENV = dict(HASURA_HOST_PORT=str(hasura_port))

    env = os.environ.copy()

    # Check for env var / cli conflict
    # TODO: Consider removal in next major version, previously the env would override
    #       the cli without warning

    if "PREFECT_UI_TAG" in env and ui_version and env["PREFECT_UI_TAG"] != ui_version:
        warnings.warn(
            "The UI version has been set in the environment via `PREFECT_UI_TAG` and "
            f"the CLI. The environment variable value (={env['PREFECT_UI_TAG']}) will "
            "be ignored."
        )

    if "PREFECT_SERVER_TAG" in env and version and env["PREFECT_SERVER_TAG"] != version:
        warnings.warn(
            "The version has been set in the environment via `PREFECT_SERVER_TAG` and "
            f"the CLI. The environment variable value (={env['PREFECT_SERVER_TAG']}) "
            "will be ignored."
        )

    if "PREFECT_SERVER_DB_CMD" in env and no_upgrade:
        warnings.warn(
            "The database startup command has been set in the environment via "
            "`PREFECT_SERVER_DB_CMD` and `--no-upgrade` has been passed via CLI. The "
            "environment variable value (={env['PREFECT_SERVER_DB_CMD']}) will be "
            "ignored."
        )
        env.pop("PREFECT_SERVER_DB_CMD")

    # Allow a more complex database command to be passed via env
    env.setdefault(
        "PREFECT_SERVER_DB_CMD",
        "prefect-server database upgrade -y"
        if not no_upgrade
        else "echo 'DATABASE MIGRATIONS SKIPPED'",
    )

    env.update(**PREFECT_ENV, **APOLLO_ENV, **POSTGRES_ENV, **UI_ENV, **HASURA_ENV)

    return env


def warn_for_postgres_settings_when_using_external_postgres(
    no_postgres_port, postgres_port, use_volume, volume_path
) -> None:
    """
    Issue user warnings if Postgres related settings have changed
    """
    if no_postgres_port:
        warnings.warn(
            "Using external Postgres instance, `--no-postgres-port` flag will be ignored."
        )
    if postgres_port != config.server.database.host_port:
        warnings.warn(
            "Using external Postgres instance, `--postgres-port` flag will be ignored."
        )
    if use_volume:
        warnings.warn(
            "Using external Postgres instance, `--use-volume` flag will be ignored."
        )
    if volume_path != config.server.database.volume_path:
        warnings.warn(
            "Using external Postgres instance, `--volume-path` flag will be ignored."
        )


@server.command(hidden=True, name="config")
@add_options(COMMON_SERVER_OPTIONS)
def config_cmd(
    version,
    ui_version,
    no_upgrade,
    no_ui,
    external_postgres,
    postgres_url,
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
    use_volume,
    volume_path,
):
    """
    This command writes the configured docker-compose.yml file to standard output

    \b
    Options:
        --version, -v       TEXT    The server image versions to use (for example, '0.1.0'
                                    or 'master'). Defaults to `core-a.b.c` where `a.b.c.`
                                    is the version of Prefect Core currently running.
        --ui-version, -uv   TEXT    The UI image version to use (for example, '0.1.0' or
                                    'master'). Defaults to `core-a.b.c` where `a.b.c.` is
                                    the version of Prefect Core currently running.
        --no-upgrade, -n            Flag to avoid running a database upgrade when the
                                    database spins up
        --no-ui, -u                 Flag to avoid starting the UI

    \b
        --external-postgres, -ep    Disable the Postgres service, connect to an external one instead
        --postgres-url      TEXT    Postgres connection url to use. Expected format is
                                    postgres://<username>:<password>@hostname:<port>/<dbname>

    \b
        --postgres-port     TEXT    Port used to serve Postgres, defaults to '5432'.
                                    Not valid for external Postgres.
        --hasura-port       TEXT    Port used to serve Hasura, defaults to '3000'
        --graphql-port      TEXT    Port used to serve the GraphQL API, defaults to '4201'
        --ui-port           TEXT    Port used to serve the UI, defaults to '8080'
        --server-port       TEXT    Port used to serve the Core server, defaults to '4200'

    \b
        --no-postgres-port          Disable port map of Postgres to host.
                                    Not valid for external Postgres.
        --no-hasura-port            Disable port map of Hasura to host
        --no-graphql-port           Disable port map of the GraphQL API to host
        --no-ui-port                Disable port map of the UI to host
        --no-server-port            Disable port map of the Core server to host

    \b
        --use-volume                Enable the use of a volume for the Postgres service.
                                    Not valid for external Postgres.
        --volume-path       TEXT    A path to use for the Postgres volume, defaults to
                                    '~/.prefect/pg_data'. Not valid for external Postgres.
    """
    # set external postgres flag if the user has provided `--postgres-url`
    if postgres_url is not None:
        external_postgres = True

    if external_postgres:
        warn_for_postgres_settings_when_using_external_postgres(
            no_postgres_port=no_postgres_port,
            postgres_port=postgres_port,
            use_volume=use_volume,
            volume_path=volume_path,
        )

    compose_path = setup_compose_file(
        no_ui=no_ui,
        external_postgres=external_postgres,
        no_postgres_port=no_postgres_port,
        no_hasura_port=no_hasura_port,
        no_graphql_port=no_graphql_port,
        no_ui_port=no_ui_port,
        no_server_port=no_server_port,
        use_volume=use_volume,
    )

    compose_dir_path = str(Path(compose_path).parent)

    env = setup_compose_env(
        version=version,
        ui_version=ui_version,
        no_upgrade=no_upgrade,
        external_postgres=external_postgres,
        postgres_url=postgres_url,
        postgres_port=postgres_port,
        hasura_port=hasura_port,
        graphql_port=graphql_port,
        ui_port=ui_port,
        server_port=server_port,
        volume_path=volume_path,
    )

    subprocess.check_call(["docker-compose", "config"], cwd=compose_dir_path, env=env)


@server.command(hidden=True)
@add_options(COMMON_SERVER_OPTIONS)
@click.option(
    "--detach",
    "-d",
    help="Detached mode. Runs Server containers in the background",
    is_flag=True,
    hidden=True,
)
@click.option(
    "--skip-pull",
    help="Pass this flag to skip pulling new images (if available)",
    is_flag=True,
    hidden=True,
)
def start(
    version,
    ui_version,
    skip_pull,
    no_upgrade,
    no_ui,
    external_postgres,
    postgres_url,
    detach,
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
    use_volume,
    volume_path,
):
    """
    This command spins up all infrastructure and services for the Prefect Core server

    \b
    Options:
        --version, -v       TEXT    The server image versions to use (for example, '0.1.0'
                                    or 'master'). Defaults to `core-a.b.c` where `a.b.c.`
                                    is the version of Prefect Core currently running.
        --ui-version, -uv   TEXT    The UI image version to use (for example, '0.1.0' or
                                    'master'). Defaults to `core-a.b.c` where `a.b.c.` is
                                    the version of Prefect Core currently running.
        --no-upgrade, -n            Flag to avoid running a database upgrade when the
                                    database spins up
        --no-ui, -u                 Flag to avoid starting the UI

    \b
        --external-postgres, -ep    Disable the Postgres service, connect to an external one instead
        --postgres-url      TEXT    Postgres connection url to use. Expected format
                                    is postgres://<username>:<password>@hostname:<port>/<dbname>

    \b
        --postgres-port     TEXT    Port used to serve Postgres, defaults to '5432'.
                                    Not valid for external Postgres.
        --hasura-port       TEXT    Port used to serve Hasura, defaults to '3000'
        --graphql-port      TEXT    Port used to serve the GraphQL API, defaults to '4201'
        --ui-port           TEXT    Port used to serve the UI, defaults to '8080'
        --server-port       TEXT    Port used to serve the Core server, defaults to '4200'

    \b
        --no-postgres-port          Disable port map of Postgres to host.
                                    Not valid for external Postgres.
        --no-hasura-port            Disable port map of Hasura to host
        --no-graphql-port           Disable port map of the GraphQL API to host
        --no-ui-port                Disable port map of the UI to host
        --no-server-port            Disable port map of the Core server to host

    \b
        --use-volume                Enable the use of a volume for the Postgres service.
                                    Not valid for external Postgres.
        --volume-path       TEXT    A path to use for the Postgres volume, defaults to
                                    '~/.prefect/pg_data' Not valid for external Postgres.

    \b
        --detach, -d                Detached mode. Runs Server containers in the background
        --skip-pull                 Flag to skip pulling new images (if available)
    """
    # set external postgres flag if the user has provided `--postgres-url`
    if postgres_url is not None:
        external_postgres = True

    if external_postgres:
        warn_for_postgres_settings_when_using_external_postgres(
            no_postgres_port=no_postgres_port,
            postgres_port=postgres_port,
            use_volume=use_volume,
            volume_path=volume_path,
        )

    compose_path = setup_compose_file(
        no_ui=no_ui,
        external_postgres=external_postgres,
        no_postgres_port=no_postgres_port,
        no_hasura_port=no_hasura_port,
        no_graphql_port=no_graphql_port,
        no_ui_port=no_ui_port,
        no_server_port=no_server_port,
        use_volume=use_volume,
    )

    compose_dir_path = str(Path(compose_path).parent)

    env = setup_compose_env(
        version=version,
        ui_version=ui_version,
        no_upgrade=no_upgrade,
        external_postgres=external_postgres,
        postgres_url=postgres_url,
        postgres_port=postgres_port,
        hasura_port=hasura_port,
        graphql_port=graphql_port,
        ui_port=ui_port,
        server_port=server_port,
        volume_path=volume_path,
    )

    proc = None
    try:
        if not skip_pull:
            subprocess.check_call(
                ["docker-compose", "pull"], cwd=compose_dir_path, env=env
            )

        cmd = ["docker-compose", "up"]
        if detach:
            cmd.append("--detach")
        proc = subprocess.Popen(cmd, cwd=compose_dir_path, env=env)
        started = False
        with prefect.utilities.configuration.set_temporary_config(
            {
                "cloud.api": "http://localhost:4200",
                "cloud.graphql": "http://localhost:4200/graphql",
                "backend": "server",
            }
        ):
            while not started:
                try:
                    # Get a client with the correct server port
                    client = prefect.Client(
                        api_server=f"{config.server.host}:{server_port}"
                    )
                    client.graphql("query{hello}", retry_on_api_error=False)
                    started = True
                    # Create a default tenant if no tenant exists
                    if not client.get_available_tenants():
                        client.create_tenant(name="default")
                    print(ascii_welcome(ui_port=str(ui_port)))
                except Exception:
                    time.sleep(0.5)
                    pass
            if detach:
                return
            while True:
                time.sleep(0.5)
    except BaseException:
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


def ascii_welcome(ui_port="8080"):
    ui_url = click.style(
        f"http://localhost:{ui_port}", fg="white", bg="blue", bold=True
    )
    docs_url = click.style("https://docs.prefect.io", fg="white", bg="blue", bold=True)

    title = r"""
   _____  _____  ______ ______ ______ _____ _______    _____ ______ _______      ________ _____
  |  __ \|  __ \|  ____|  ____|  ____/ ____|__   __|  / ____|  ____|  __ \ \    / /  ____|  __ \
  | |__) | |__) | |__  | |__  | |__ | |       | |    | (___ | |__  | |__) \ \  / /| |__  | |__) |
  |  ___/|  _  /|  __| |  __| |  __|| |       | |     \___ \|  __| |  _  / \ \/ / |  __| |  _  /
  | |    | | \ \| |____| |    | |___| |____   | |     ____) | |____| | \ \  \  /  | |____| | \ \
  |_|    |_|  \_\______|_|    |______\_____|  |_|    |_____/|______|_|  \_\  \/   |______|_|  \_\

    """

    message = f"""
                                            {click.style('WELCOME TO', fg='blue', bold=True)}
  {click.style(title, bold=True)}
   Visit {ui_url} to get started, or check out the docs at {docs_url}
    """

    return message


@server.command(hidden=True)
def stop():
    """
    This command stops all Prefect Server containers that are connected to the
    `prefect-server` network. Note: This will completely remove the `prefect-server` network
    and all associated containers.
    """
    import docker

    client = docker.APIClient()

    networks = client.networks(names=["prefect-server"])

    if not networks:
        click.echo("No running Prefect Server found")
        return
    network_id = networks[0].get("Id")

    click.echo("Stopping Prefect Server containers and network")
    for container in client.inspect_network(network_id).get("Containers").keys():
        client.disconnect_container_from_network(container, network_id)
        client.remove_container(container, force=True)

    client.remove_network(network_id)
    click.echo("Prefect Server stopped")


@server.command(hidden=True)
@click.option(
    "--name",
    "-n",
    help="The name of a tenant to create",
    hidden=True,
)
@click.option(
    "--slug",
    "-s",
    help="The slug of a tenant to create",
    default=None,
    hidden=True,
)
def create_tenant(name, slug):
    """
    This command creates a tenant for the Prefect Server

    \b
    Options:
        --name, -n       TEXT    The name of a tenant to create
        --slug, -n       TEXT    The slug of a tenant to create (optional)
    """
    client = prefect.Client()
    tenant_id = client.create_tenant(name=name, slug=slug)

    click.secho(f"Tenant created with ID: {tenant_id}", fg="green")

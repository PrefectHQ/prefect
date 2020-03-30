# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import glob
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import click
import pendulum
import toml
import yaml
from click.testing import CliRunner

import prefect
import prefect_server
from prefect_server import api, cli, config, utilities
from prefect_server.database import models


@click.group()
def dev():
    """
    Commands for developing Server

    \b
    Usage:
        $ prefect-server ...
    
    \b
    Arguments:
        build   builds prefect server, ui, apollo from source
    """


def make_env(fname=None):

    # replace localhost with postgres to use docker-compose dns
    PREFECT_ENV = dict(
        DB_CONNECTION_URL=config.database.connection_url.replace(
            "localhost", "postgres"
        )
    )

    APOLLO_ENV = dict(
        HASURA_API_URL=f"http://hasura:{config.hasura.port}/v1alpha1/graphql",
        HASURA_WS_URL=f"ws://hasura:{config.hasura.port}/v1alpha1/graphql",
        PREFECT_API_URL=f"http://graphql:{config.services.graphql.port}{config.services.graphql.path}",
        PREFECT_API_HEALTH_URL=f"http://graphql:{config.services.graphql.port}/health",
    )

    POSTGRES_ENV = dict(
        POSTGRES_USER=config.database.username,
        POSTGRES_PASSWORD=config.database.password,
        POSTGRES_DB=config.database.name,
    )

    HASURA_ENV = dict()

    ENV = os.environ.copy()
    ENV.update(**PREFECT_ENV, **APOLLO_ENV, **POSTGRES_ENV, **HASURA_ENV)

    if fname is not None:
        list_of_pairs = [
            f"{k}={repr(v)}" if "\n" in v else f"{k}={v}" for k, v in ENV.items()
        ]
        with open(fname, "w") as f:
            f.write("\n".join(list_of_pairs))
    return ENV.copy()


@dev.command(hidden=True)
@click.option(
    "--version",
    "-v",
    help="The server image versions to build (for example, '0.10.0' or 'master')",
    # TODO: update this default to use prefect.__version__ logic
    default="latest",
)
def build(version):
    """
    foobar
    """
    docker_dir = Path(prefect_server.__file__).parents[2] / "docker"
    print(docker_dir)

    env = make_env()

    if "PREFECT_SERVER_TAG" not in env:
        env.update(PREFECT_SERVER_TAG=version)

    proc = None
    cmd = ["docker-compose", "build"]
    proc = subprocess.Popen(cmd, cwd=docker_dir, env=env)


@dev.command()
@click.option("--tag", "-t", help="The server image/tag to use", default="latest")
@click.option(
    "--skip-pull",
    help="Pass this flag to skip pulling new images (if available)",
    is_flag=True,
)
def infrastructure(tag, skip_pull):
    """
    This command:
        - starts a PostgreSQL database
        - starts Hasura
    """
    docker_dir = Path(prefect_server.__file__).parents[2] / "docker"

    env = make_env()

    proc = None
    try:
        if not skip_pull:
            subprocess.check_call(
                ["docker-compose", "pull", "postgres", "hasura"],
                cwd=docker_dir,
                env=env,
            )
        proc = subprocess.Popen(
            ["docker-compose", "up", "postgres", "hasura"], cwd=docker_dir, env=env
        )

        # if not initialize, just run hasura (and dependencies), which will skip the init step
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


@dev.command()
@click.option("--skip-ui", help="Pass this flag to skip UI dependencies", is_flag=True)
@click.option(
    "--skip-apollo", help="Pass this flag to skip Apollo dependencies", is_flag=True
)
def install_dependencies(skip_ui, skip_apollo):
    """
    This command:
        - installs Apollo dependencies
        - install UI dependencies
    """
    if not skip_ui:
        click.secho("Installing UI dependencies...")
        time.sleep(0.5)
        install_ui_dependencies()

    if not skip_apollo:
        click.secho("Installing Apollo dependencies...")
        time.sleep(0.5)
        install_apollo_dependencies()

    if skip_ui and skip_apollo:
        click.secho("No dependencies were installed because all were skipped.")


def install_apollo_dependencies():
    apollo_dir = Path(prefect_server.__file__).parents[2] / "services" / "apollo"

    proc = None
    try:
        proc = subprocess.check_call(["npm", "install"], cwd=apollo_dir)
        click.secho("Apollo dependencies installed! 🚀🚀🚀")
    except:
        click.secho(
            "Exception caught while installing Apollo dependencies.",
            fg="white",
            bg="red",
        )
        if proc:
            proc.kill()
        raise


def install_ui_dependencies():
    ui_dir = Path(prefect_server.__file__).parents[2] / "services" / "ui"

    proc = None
    try:
        proc = subprocess.check_call(["npm", "install"], cwd=ui_dir)
        click.secho("UI dependencies installed! 🕹🕹🕹")
    except:
        click.secho(
            "Exception caught while installing UI dependencies.", fg="white", bg="red"
        )
        if proc:
            proc.kill()
        raise


def is_process_group_empty(pgid: int):
    proc = subprocess.Popen(
        ["pgrep", "-g", str(pgid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    proc.wait()
    return proc.returncode != 0


def kill_process_group(proc, timeout: int = 3):
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        proc.terminate()

        for _ in range(timeout):
            if is_process_group_empty(pgid):
                return
            click.secho("Waiting for process group to exit...", fg="white", bg="blue")
            time.sleep(1)

        click.secho("Timeout while shutting down, killing!", fg="white", bg="red")
        os.killpg(pgid, signal.SIGKILL)
        proc.kill()
    except Exception as exc:
        click.secho(exc)


@dev.command()
@click.option(
    "--include", "-i", help="A comma-seperated list of serivces that should be run"
)
@click.option(
    "--exclude", "-e", help="A comma-seperated list of services that should not be run"
)
def services(include, exclude):
    """
    This command starts services
    """

    all_services = ["graphql", "scheduler", "apollo", "ui"]
    if not include:
        include = all_services
    else:
        include = include.split(",")
    if not exclude:
        exclude = ""
    run_services = sorted(set(include).difference(exclude.split(",")))

    click.secho(
        f"\n\nStarting Prefect Server services: {' '.join(run_services)}\n\n",
        fg="green",
    )

    procs = []
    for service in run_services:
        procs.append(
            subprocess.Popen(
                ["prefect-server", "services", service],
                env=make_env(),
                preexec_fn=os.setsid,
            )
        )

    try:
        while True:
            time.sleep(1)
    except:
        click.secho("Exception caught; shutting down!", fg="white", bg="red")
        for proc in procs:
            kill_process_group(proc)


def config_to_dict(config):
    if isinstance(config, (list, tuple, set)):
        return type(config)([config_to_dict(d) for d in config])
    elif isinstance(config, prefect.configuration.Config):
        return dict({k: config_to_dict(v) for k, v in config.items()})
    return config


def set_nested(dictionary, path: str, value: str):
    path = path.split(".")
    for level in path[:-1]:
        dictionary = dictionary.setdefault(level, {})
    dictionary[path[-1]] = value


@dev.command()
@click.option("-m", "--migration-message", required=True)
def generate_migration(migration_message):
    # ensure this is called from the root server directory
    if Path(prefect_server.__file__).parents[2] != Path(os.getcwd()):
        raise click.ClickException(
            "generate-migration must be run from the server root directory."
        )
    # find the most recent revision
    alembic_migrations_path = "../../../services/postgres/alembic/versions"
    versions = glob.glob(
        os.path.join(os.path.dirname(__file__), alembic_migrations_path, "*.py")
    )
    versions.sort()
    most_recent_migration = versions[-1]
    with open(
        os.path.join(
            os.path.dirname(__file__), alembic_migrations_path, most_recent_migration
        )
    ) as migration:
        for line in migration.readlines():
            if line.startswith("Revision ID:"):
                revision = line.split(": ")[1].strip()
    click.echo(f"Most recent Alembic revision is {revision}")
    # copy metadata to a backup for corresponding revision
    hasura_migrations_path = "../../../services/hasura/migrations"
    backup_metadata_file = f"metadata-{revision}.yaml"
    backup_metadata_destination = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            hasura_migrations_path,
            "versions",
            backup_metadata_file,
        )
    )
    shutil.copy(
        os.path.join(
            os.path.dirname(__file__), hasura_migrations_path, "metadata.yaml"
        ),
        backup_metadata_destination,
    )
    click.echo(f"Copied metadata to {backup_metadata_destination}")
    # create a new revision
    click.echo(
        subprocess.check_output(["alembic", "revision", "-m", migration_message])
    )
    click.secho("Prefect Server migration generated!", fg="green")

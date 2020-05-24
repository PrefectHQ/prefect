# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import argparse
from pathlib import Path

import click
from click.testing import CliRunner

import prefect
import prefect_server
from prefect_server import config


@click.group()
def database():
    """
    Commands for working with the Prefect Server database
    """


def alembic_config(apply_hasura_metadata=True):
    # lazy import for performance
    import alembic
    from alembic.config import Config

    root_dir = Path(prefect_server.__file__).parents[2]
    if not root_dir.joinpath("alembic.ini").exists():
        raise ValueError(f"Couldn't find alembic.ini at {root_dir}/alembic.ini")

    if apply_hasura_metadata:
        cmd_opts = argparse.Namespace(x=["apply_hasura_metadata=true"])
    else:
        cmd_opts = None

    alembic_config = Config(root_dir / "alembic.ini", cmd_opts=cmd_opts)
    alembic_config.set_main_option(
        "script_location", str(root_dir / "services" / "postgres" / "alembic")
    )

    return alembic_config


def alembic_upgrade(n=None, apply_hasura_metadata=True):
    # lazy import for performance
    import alembic.command

    alembic.command.upgrade(
        alembic_config(apply_hasura_metadata=apply_hasura_metadata),
        f"{n}" if n else "heads",
    )


def alembic_downgrade(n=None, apply_hasura_metadata=True):
    # lazy import for performance
    import alembic.command

    alembic.command.downgrade(
        alembic_config(apply_hasura_metadata=apply_hasura_metadata),
        f"{n}" if n else "base",
    )


@database.command()
@click.option(
    "--database-url",
    "-d",
    help="The database connection URL",
    default=prefect_server.config.database.connection_url,
)
def create(database_url):
    """
    Creates a Prefect database
    """
    # defer import for performance
    from sqlalchemy_utils import create_database

    try:
        create_database(database_url)
        click.secho("\nDatabase created!", fg="green")
    except Exception as e:
        click.secho("Could not create the database!", bg="red", bold=True)
        raise click.ClickException(e)


@database.command()
@click.option(
    "--database-url",
    "-d",
    help="The database connection URL",
    default=prefect_server.config.database.connection_url,
)
@click.option(
    "-n",
    help="The argument to `alembic upgrade`. If not provided, runs all.",
    default=None,
)
@click.option(
    "--yes",
    "-y",
    help="Pass --yes to confirm that you want to upgrade the database",
    is_flag=True,
)
def upgrade(database_url, yes, n=None):
    """
    Upgrades the Prefect database by running any Alembic migrations
    """
    if not yes:
        if not click.confirm(
            click.style(
                "Are you sure you want to upgrade the database?", bg="red", bold=True
            )
        ):
            return
    try:
        click.secho("\nRunning Alembic migrations...")
        alembic_upgrade(n)
        click.secho("\nDatabase upgraded!", fg="green")
    except Exception as e:
        click.secho("\nCould not upgrade the database!", bg="red", bold=True)
        raise click.ClickException(e)


@database.command()
@click.option(
    "--unsafe",
    "-u",
    help="Force DB reset even if the DB/Hasura is not on localhost (or potentially a dev docker container)",
    default=False,
    is_flag=True,
)
@click.option(
    "--yes",
    "-y",
    help="Pass --yes to confirm that you want to reset the database",
    is_flag=True,
)
def reset(unsafe, yes):
    """
    Destroys and recreates the Prefect Server database.

    WARNING: ALL DATA IS LOST.
    """

    if unsafe and yes:
        click.secho(
            "Not permitted to automatically disregard safety precautions. Use either --unsafe or --yes, not both.",
            bg="red",
            bold=True,
        )
        raise click.Abort()

    if not unsafe:
        # we only want to allow communication with a hasura/postgres instance that is positively local
        # or probably in a docker-compose maintained container (where the hosts are named from the service names).
        # There is no definitive way to easily verify the docker container assumption, this is enforced by
        # convention via a common service name.
        hasura_hosts = ("localhost", "hasura", "127.0.0.1")
        postgres_hosts = ("localhost", "postgres", "127.0.0.1")

        if config.hasura.host not in hasura_hosts:
            click.secho(
                "Failed safety check: bad 'hasura.host': '{}'\n  expected to be one of: {}".format(
                    config.hasura.host, ",".join(repr(c) for c in hasura_hosts)
                ),
                bg="red",
                bold=True,
            )
            raise click.Abort()

        # only allow graphql comms to a approved hasura instances:
        # 1) over http (not https). Https is an indirect indication that this could be a remote environment.
        # 2) the hasura host is one of the approved hasura instances
        found_valid_candidate = False
        valid_candidates = []
        for candidate in hasura_hosts:
            expected = "http://{}:{}".format(candidate, config.hasura.port)
            valid_candidates.append(expected)
            if expected in config.hasura.graphql_url:
                found_valid_candidate = True
                break

        if not found_valid_candidate:
            click.secho(
                "Failed safety check: bad 'hasura.graphql_url': '{}'\n  expected to contain one of: {}".format(
                    config.hasura.graphql_url,
                    ",".join(repr(c) for c in valid_candidates),
                ),
                bg="red",
                bold=True,
            )
            raise click.Abort()

        # only allow comms to an approved postgres instance. The `database.connection_url` is used as a default
        # for other config variables. This verification is validating the host and port of a database connection string
        # (only after the '@' host declaration)
        found_valid_candidate = False
        valid_candidates = []
        for candidate in postgres_hosts:
            expected = "@{}:5432".format(candidate)
            valid_candidates.append(expected)
            if expected in prefect_server.config.database.connection_url:
                found_valid_candidate = True
                break

        if not found_valid_candidate:
            click.secho(
                "Failed safety check: bad 'database.connection_url': '{}'\n  expected to contain one of: {}".format(
                    config.database.connection_url,
                    ",".join(repr(c) for c in valid_candidates),
                ),
                bg="red",
                bold=True,
            )
            raise click.Abort()

        # only allow hasura comms to an approved postgres instance. This verification is validating the host and
        # port of a database connection string (only after the '@' host declaration)
        found_valid_candidate = False
        valid_candidates = []
        for candidate in postgres_hosts:
            expected = "@{}:5432".format(candidate)
            valid_candidates.append(expected)
            if expected in config.database.connection_url:
                found_valid_candidate = True
                break

        if not found_valid_candidate:
            click.secho(
                "Failed safety check: bad 'database.connection_url': '{}'\n  expected to contain one of: {}".format(
                    config.database.connection_url,
                    ",".join(repr(c) for c in valid_candidates),
                ),
                bg="red",
                bold=True,
            )
            raise click.Abort()
    else:
        click.secho(
            "Warning: Elected to reset database WITHOUT safety precautions!\n",
            bg="red",
            bold=True,
        )

    if not yes:
        if not click.confirm(
            click.style(
                "Are you sure you want to reset the database?", bg="red", bold=True
            )
        ):
            return
    try:
        CliRunner().invoke(prefect_server.cli.hasura.clear_metadata)
        alembic_downgrade(apply_hasura_metadata=False)
        alembic_upgrade(apply_hasura_metadata=True)
        click.secho("\nDatabase reset!", fg="green")
    except Exception as e:
        click.secho("\nCould not reset the database!", bg="red", bold=True)
        raise click.ClickException(e)


@database.command()
@click.option(
    "--database-url",
    "-d",
    help="The database connection URL",
    default=prefect_server.config.database.connection_url,
)
@click.option(
    "-n",
    help="The argument to `alembic upgrade`. If not provided, runs all.",
    default=None,
)
@click.option(
    "--yes",
    "-y",
    help="Pass --yes to confirm that you want to downgrade the database",
    is_flag=True,
)
def downgrade(database_url, yes, n=None):
    """
    Deletes all content and tables in the Prefect Server database, but does not delete the
    database itself.

    WARNING: ALL DATA IS LOST.
    """
    if not yes:
        if not click.confirm(
            click.style(
                "Are you sure you want to downgrade the database?", bg="red", bold=True
            )
        ):
            return
    try:

        alembic_downgrade(n)
        click.secho("\nDatabase downgraded!", fg="green")
    except Exception as e:
        click.secho("\nCould not downgrade the database!", bg="red", bold=True)
        raise click.ClickException(e)


@database.command()
@click.option(
    "--database-url",
    "-d",
    help="The database connection URL",
    default=prefect_server.config.database.connection_url,
)
@click.option(
    "--skip-downgrades",
    help="Skip downgrades (only issues DROP DATABASE instruction)",
    is_flag=True,
)
@click.option(
    "--yes",
    "-y",
    help="Pass --yes to confirm that you want to destroy the database",
    is_flag=True,
)
def destroy(database_url, skip_downgrades, yes):
    """
    Destroys the Prefect Server database.

    WARNING: ALL DATA IS LOST.
    """
    # defer import for performance
    from sqlalchemy_utils import drop_database

    if not yes:
        if not click.confirm(
            click.style(
                "Are you sure you want to destroy the database?", bg="red", bold=True
            )
        ):
            return
    try:
        if not skip_downgrades:
            alembic_downgrade()
        drop_database(database_url)
        click.secho("\nDatabase destroyed!", fg="green")
    except Exception as e:
        click.secho("\nCould not destroy the database!", bg="red", bold=True)
        raise click.ClickException(e)

# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import click
import os

import prefect_server

# import to avoid shadowing the actual modules
from .dev import dev as _dev
from .database import database as _database
from .hasura import hasura as _hasura
from .services import services as _services


@click.group()
def cli():
    """
    The Prefect Server CLI
    """


cli.add_command(_dev)
cli.add_command(_database)
cli.add_command(_hasura)
cli.add_command(_services)


@cli.command()
def make_user_config():
    """
    Generates a user configuration file
    """
    user_config_path = prefect_server.config.get("user_config_path")
    if not user_config_path:
        raise ValueError("No user config path set!")
    elif os.path.isfile(user_config_path):
        raise ValueError("A file already exists at {}".format(user_config_path))

    os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
    with open(user_config_path, "w") as user_config:
        user_config.write(
            "# This is a user configuration file.\n"
            "# Settings placed here will overwrite Prefect Server's defaults."
        )
    click.secho("Config created at {}".format(user_config_path), fg="green")

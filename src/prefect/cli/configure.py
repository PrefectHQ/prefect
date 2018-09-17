# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import json
import os
from pathlib import Path
import sys

import click
import toml


@click.group()
def configure():
    """
    Configure communication with Prefect Cloud
    """
    pass


@configure.command()
@click.argument("path", required=False)
def init(path):
    """
    Initialize cloud communication config options
    """

    if not path:
        path = "{}/.prefect/config.toml".format(os.getenv("HOME"))

    if Path(path).is_file():
        config_data = toml.load(path)
    else:
        config_data = {}

    # Do under .server block
    config_data["REGISTRY_URL"] = click.prompt(
        "Registry URL", default=config_data.get("REGISTRY_URL")
    )
    config_data["API_URL"] = click.prompt("API URL", default=config_data.get("API_URL"))
    config_data["API_ACCESS_KEY"] = click.prompt(
        "API Access Key", default=config_data.get("API_ACCESS_KEY")
    )

    config_data["api_server"] = config_data["API_URL"]
    config_data["graphql_server"] = os.path.join(config_data["API_URL"], "graphql/")

    with open(path, "w") as config_file:
        toml.dump(config_data, config_file)


@configure.command()
@click.argument("variable")
@click.argument("path", required=False)
def set_variable(variable, path):
    """
    Sets a specific configuration variable
    """
    if not path:
        path = "{}/.prefect/config.toml".format(os.getenv("HOME"))

    if Path(path).is_file():
        config_data = toml.load(path)
    else:
        config_data = {}

    config_data[variable] = click.prompt(
        "{}".format(variable), default=config_data.get(variable)
    )

    with open(path, "w") as config_file:
        toml.dump(config_data, config_file)


@configure.command()
@click.argument("path", required=False)
def list_config(path):
    """
    List all configuration variables
    """
    if not path:
        path = "{}/.prefect/config.toml".format(os.getenv("HOME"))

    if Path(path).is_file():
        config_data = toml.load(path)
    else:
        config_data = {}

    click.echo(config_data)


@configure.command()
@click.argument("path", required=False)
def open_config(path):
    """
    Opens the configuration file
    """
    if not path:
        path = "{}/.prefect/config.toml".format(os.getenv("HOME"))

    click.launch(path)

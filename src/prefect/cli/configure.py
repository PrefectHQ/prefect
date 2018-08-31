# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import json
from pathlib import Path
import sys

import click


@click.group()
def configure():
    """
    Configure communication with Prefect Cloud
    """
    pass


@configure.command()
def init():
    """
    Initialize cloud communication config options
    """

    config_file_path = "{}/prefect_cloud_configuration".format(sys.exec_prefix)

    if Path(config_file_path).is_file():
        with open(config_file_path, "r+") as config_file:
            config_data = json.load(config_file)
    else:
        config_data = {}

    config_data["REGISTRY_URL"] = click.prompt(
        "Registry URL", default=config_data.get("REGISTRY_URL")
    )
    config_data["API_URL"] = click.prompt("API URL", default=config_data.get("API_URL"))
    config_data["API_ACCESS_KEY"] = click.prompt(
        "API Access Key", default=config_data.get("API_ACCESS_KEY")
    )

    with open(config_file_path, "w+") as config_file:
        json.dump(config_data, config_file)


@configure.command()
@click.argument("variable")
def set(variable):
    """
    Sets a specific configuration variable
    """
    config_file_path = "{}/prefect_cloud_configuration".format(sys.exec_prefix)

    if Path(config_file_path).is_file():
        with open(config_file_path, "r+") as config_file:
            config_data = json.load(config_file)
    else:
        config_data = {}

    config_data[variable] = click.prompt(
        "{}".format(variable), default=config_data.get(variable)
    )

    with open(config_file_path, "w+") as config_file:
        json.dump(config_data, config_file)


@configure.command()
def list():
    """
    List all configuration variables
    """
    config_file_path = "{}/prefect_cloud_configuration".format(sys.exec_prefix)

    if Path(config_file_path).is_file():
        with open(config_file_path, "r+") as config_file:
            config_data = json.load(config_file)
    else:
        config_data = {}

    click.echo(config_data)


@configure.command()
def open():
    """
    Opens the configuration file
    """
    click.launch("{}/prefect_cloud_configuration".format(sys.exec_prefix))

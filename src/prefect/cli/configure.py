# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import os
from pathlib import Path

import click
import toml

from prefect.client import Client

PATH = os.path.join(os.getenv("HOME"), '.prefect/config.toml')


def load_prefect_config():
    if Path(PATH).is_file():
        config_data = toml.load(PATH)

    if not config_data:
        raise click.ClickException("CLI not configured. Run 'prefect configure init'")

    return config_data


@click.group()
def configure():
    """
    Configure communication with Prefect Cloud.
    """
    pass


@configure.command()
def init():
    """
    Initialize cloud communication config options.
    """
    config_data = load_prefect_config()

    config_data["REGISTRY_URL"] = click.prompt(
        "Registry URL", default=config_data.get("REGISTRY_URL")
    )
    config_data["API_URL"] = click.prompt("API URL", default=config_data.get("API_URL"))

    with open(PATH, "w") as config_file:
        toml.dump(config_data, config_file)


@configure.command()
@click.argument("variable")
def set_variable(variable):
    """
    Sets a specific configuration variable.
    """
    config_data = load_prefect_config()

    config_data[variable] = click.prompt(
        "{}".format(variable), default=config_data.get(variable)
    )

    with open(PATH, "w") as config_file:
        toml.dump(config_data, config_file)


@configure.command()
def list_config():
    """
    List all configuration variables.
    """
    config_data = load_prefect_config()

    click.echo(config_data)


@configure.command()
def open_config():
    """
    Opens the configuration file.
    """
    click.launch(PATH)


@configure.command()
def login():
    """
    Login to Prefect Cloud.
    """
    config_data = load_prefect_config()

    config_data["EMAIL"] = click.prompt("email", default=config_data.get("EMAIL"))
    config_data["PASSWORD"] = click.prompt(
        "password", hide_input=True, confirmation_prompt=True
    )

    client = Client(
        config_data["API_URL"], os.path.join(config_data["API_URL"], "graphql/")
    )

    client.login(email=config_data["EMAIL"], password=config_data["PASSWORD"])

    with open(PATH, "w") as config_file:
        toml.dump(config_data, config_file)

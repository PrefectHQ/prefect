# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import os

import click
import toml

from prefect import config
from prefect.client import Client


PATH = os.path.join(os.getenv("HOME"), ".prefect/config.toml")


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
    config["registry_url"] = click.prompt(
        "Registry URL", default=config.get("registry_url")
    )
    config["api_url"] = click.prompt("API URL", default=config.get("api_url"))

    with open(PATH, "w") as config_file:
        toml.dump(config, config_file)


@configure.command()
@click.argument("variable")
def set_variable(variable):
    """
    Sets a specific configuration variable.
    """
    config[variable] = click.prompt("{}".format(variable), default=config.get(variable))

    with open(PATH, "w") as config_file:
        toml.dump(config, config_file)


@configure.command()
def list_config():
    """
    List all configuration variables.
    """
    click.echo(config)


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
    config["email"] = click.prompt("email", default=config.get("email"))
    config["password"] = click.prompt(
        "password", hide_input=True, confirmation_prompt=True
    )

    client = Client()

    client.login(email=config["email"], password=config["password"])

    with open(PATH, "w") as config_file:
        toml.dump(config, config_file)

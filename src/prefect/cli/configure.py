# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import os

import click
import toml

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
    config["REGISTRY_URL"] = click.prompt(
        "Registry URL", default=config.get("REGISTRY_URL")
    )
    config["API_URL"] = click.prompt("API URL", default=config.get("API_URL"))

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
    config["EMAIL"] = click.prompt("email", default=config.get("EMAIL"))
    config["PASSWORD"] = click.prompt(
        "password", hide_input=True, confirmation_prompt=True
    )

    client = Client(config["API_URL"], os.path.join(config["API_URL"], "graphql/"))

    client.login(email=config["EMAIL"], password=config["PASSWORD"])

    with open(PATH, "w") as config_file:
        toml.dump(config, config_file)

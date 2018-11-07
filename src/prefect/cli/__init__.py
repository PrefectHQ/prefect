#!/usr/bin/env python

# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import click
import logging
import os
import requests
import sys
import prefect

from .flows import flows
from .configure import configure


@click.group()
@click.option("--registry-path")
@click.option("--registry-encryption-key")
def cli(registry_path=None, registry_encryption_key=None):
    """
    The Prefect CLI
    """
    if registry_path:
        prefect.core.registry.load_serialized_registry_from_path(
            registry_path, encryption_key=registry_encryption_key
        )


cli.add_command(flows)
cli.add_command(configure)


@cli.command()
def make_user_config():
    """
    Generates a user configuration file
    """
    user_config_path = prefect.config.get("user_config_path")
    if not user_config_path:
        raise ValueError("No user config path set!")
    elif os.path.isfile(user_config_path):
        raise ValueError("A file already exists at {}".format(user_config_path))

    config_path = os.path.join(os.path.dirname(prefect.__file__), "config.toml")
    with open(config_path, "r") as standard_config:
        os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
        with open(user_config_path, "w") as user_config:
            user_config.write(standard_config.read())

    click.secho("Config created at {}".format(user_config_path), fg="green")

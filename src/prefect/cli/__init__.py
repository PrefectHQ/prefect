#!/usr/bin/env python

# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import click
import logging
import os
import requests
import sys
import prefect


@click.group()
def cli():
    """
    The Prefect CLI
    """
    pass


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

    os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
    with open(user_config_path, "w") as user_config:
        user_config.write(
            "# This is a user configuration file.\n"
            "# Settings placed here will overwrite Prefect's defaults."
        )

    click.secho("Config created at {}".format(user_config_path), fg="green")

#!/usr/bin/env python


import click
import json
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


@cli.command()
@click.argument("environment_file", type=click.Path(exists=True))
@click.option("--runner_kwargs", default={})
def run(environment_file, runner_kwargs):
    """
    Run a flow from an environment file.
    """
    schema = prefect.serialization.environment.EnvironmentSchema()
    with open(environment_file, "r") as f:
        environment = schema.load(json.load(f))

    click.echo(environment.run(runner_kwargs=runner_kwargs))


@cli.command()
@click.argument("environment_metadata")
def create_environment(environment_metadata):
    """
    Call the setup and execute functions for a given environment.
    """
    schema = prefect.serialization.environment.EnvironmentSchema()
    environment = schema.load(json.loads(environment_metadata))

    environment.setup()
    environment.execute()

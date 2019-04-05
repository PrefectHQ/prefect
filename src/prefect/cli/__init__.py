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

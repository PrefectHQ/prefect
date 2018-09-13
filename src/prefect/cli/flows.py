# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import json
import os
from pathlib import Path
import sys

import click
import docker
import requests
import toml

import prefect
from prefect.client import RunFlow
from prefect.core import registry
from prefect.utilities import json as prefect_json


@click.group()
def flows():
    """
    Interact with Prefect flows
    """
    pass


@flows.command()
def info():
    """
    Prints a JSON string of information about all registered flows.
    """
    print(prefect_json.dumps([f.serialize() for f in registry.REGISTRY.values()]))


@flows.command()
def ids():
    """
    Prints all the flows in the registry.
    """
    output = {id: f.key() for id, f in registry.REGISTRY.items()}
    print(prefect_json.dumps(output, sort_keys=True))


@flows.command()
@click.argument("id")
def run(id):
    """
    Runs a registered flow.
    """
    flow = prefect.core.registry.load_flow(id)
    flow_runner = prefect.engine.FlowRunner(flow=flow)
    return flow_runner.run()


@flows.command()
@click.argument("id")
def build(id):
    """
    Build a flow's environment
    """
    flow = prefect.core.registry.load_flow(id)
    return flow.environment.build(flow=flow)


@flows.command()
@click.argument("id")
@click.argument("path", required=False)
def push(id, path):
    """
    Push a flow's container environment to a registry
    """
    if not path:
        path = "{}/.prefect/config.toml".format(os.getenv("HOME"))

    if Path(path).is_file():
        config_data = toml.load(path)

    if not config_data:
        click.echo("CLI not configured. Run 'prefect configure init'")
        return

    flow = prefect.core.registry.load_flow(id)

    # Check if login access was provided for registry
    if config_data.get("REGISTRY_USERNAME", None) and config_data.get(
        "REGISTRY_PASSWORD", None
    ):
        flow.environment.client.login(
            username=config_data["REGISTRY_USERNAME"],
            password=config_data["REGISTRY_PASSWORD"],
        )

    # Push to registry
    return flow.environment.client.images.push(
        "{}/{}".format(config_data["REGISTRY_URL"], flow.environment.image),
        tag=flow.environment.tag,
    )


@flows.command()
@click.argument("id")
@click.argument("path", required=False)
@click.option("--run", "-r", multiple=True)
def exec(id, path, run):
    """
    Send flow command
    """
    if not path:
        path = "{}/.prefect/config.toml".format(os.getenv("HOME"))

    if Path(path).is_file():
        config_data = toml.load(path)

    if not config_data:
        click.echo("CLI not configured. Run 'prefect configure init'")
        return

    flow = prefect.core.registry.load_flow(id)

    if run:
        RunFlow().run_flow(
            image_name=flow.environment.image,
            image_tag=flow.environment.tag,
            flow_id=id,
        )
    else:
        click.echo("No command specified")

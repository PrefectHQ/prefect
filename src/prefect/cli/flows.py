# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import json
import os
from pathlib import Path
import sys
from subprocess import Popen, PIPE, STDOUT

from IPython import get_ipython

import click
import docker
import requests
import toml

import prefect
from prefect.client import Client, RunFlow
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
    click.echo(prefect_json.dumps([f.serialize() for f in registry.REGISTRY.values()]))


@flows.command()
def ids():
    """
    Prints all the flows in the registry.
    """
    output = {id: f.key() for id, f in registry.REGISTRY.items()}
    click.echo(prefect_json.dumps(output, sort_keys=True))


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
@click.argument("project")
@click.argument("name")
@click.argument("version")
@click.option(
    "--file",
    required=False,
    help="Path to a file which contains the flow.",
    type=click.Path(exists=True),
)
def build(project, name, version, file):
    """
    Build a flow's environment
    """

    if file:
        # Load the registry from the file into the current process's environment
        exec(open(file).read())

    # Load the user specified flow
    for flow_id, registry_flow in registry.REGISTRY.items():
        if (
            registry_flow.project == project
            and registry_flow.name == name
            and registry_flow.version == version
        ):
            flow = prefect.core.registry.load_flow(flow_id)


    path = "{}/.prefect/config.toml".format(os.getenv("HOME"))

    if Path(path).is_file():
        config_data = toml.load(path)

    client = Client(
        config_data["API_URL"], os.path.join(config_data["API_URL"], "graphql/")
    )

    client.login(email=config_data["EMAIL"], password=config_data["PASSWORD"])

    print(client._token)

    # flow = prefect.core.registry.load_flow(id)
    # flow.environment.build(flow=flow)


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
@click.argument("image_name")
@click.argument("image_tag")
@click.argument("flow_id")
@click.argument("path", required=False)
def exec_command(image_name, image_tag, flow_id, path):
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

    client = Client(
        config_data["API_URL"], os.path.join(config_data["API_URL"], "graphql/")
    )

    client.login(email=config_data["EMAIL"], password=config_data["PASSWORD"])

    image_name = os.path.join(config_data["REGISTRY_URL"], image_name)

    rf = RunFlow(client=client)
    rf.run_flow(image_name=image_name, image_tag=image_tag, flow_id=flow_id)

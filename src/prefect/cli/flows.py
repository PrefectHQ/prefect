import click
import requests

import prefect
from prefect.build import registry
from prefect.utilities import json


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
    print(json.dumps([f.serialize() for f in registry.REGISTRY.values()]))


@flows.command()
def keys():
    """
    Prints all the flows in the registry.
    """
    output = [
        dict(zip(["project", "name", "version"], key)) for key in registry.REGISTRY
    ]
    print(json.dumps(output, sort_keys=True))


@flows.command()
@click.argument("project")
@click.argument("name")
@click.argument("version")
def run(project, name, version):
    """
    Runs a registered flow.
    """
    flow = prefect.build.registry.load_flow(project, name, version)
    flow_runner = prefect.engine.FlowRunner(flow=flow)
    return flow_runner.run()

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
@click.option('--registry_path')
def info(registry_path=None):
    """
    Prints a JSON string of information about all registered flows.
    """
    if registry_path:
        registry.load_serialized_registry_from_path(registry_path)
    print(json.dumps([f.serialize() for f in registry.REGISTRY.values()]))

@flows.command()
@click.option('--registry_path')
def keys(registry_path=None):
    """
    Prints all the flows in the registry.
    """
    if registry_path:
        registry.load_serialized_registry_from_path(registry_path)
    print(dict(zip(['project', 'name', 'version'], registry.REGISTRY)))

@flows.command()
@click.argument('project')
@click.argument('name')
@click.argument('version')
@click.option('--registry_path', default=None)
def run(project, name, version, registry_path=None):
    """
    Runs a registered flow.
    """
    if registry_path:
        prefect.build.registry.load_serialized_registry_from_path(registry_path)
    flow = prefect.build.registry.load_flow(project, name, version)
    return flow.run()

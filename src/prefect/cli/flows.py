# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import os
from pathlib import Path

import click
import toml

import prefect
from prefect.client import Client, RunFlow, Flows, FlowRuns
from prefect import config
from prefect.core import registry
from prefect.environments import ContainerEnvironment
from prefect.utilities import json as prefect_json


def load_prefect_config():
    path = "{}/.prefect/config.toml".format(os.getenv("HOME"))

    if Path(path).is_file():
        config_data = toml.load(path)

    if not config_data:
        raise click.ClickException("CLI not configured. Run 'prefect configure init'")

    return config_data


def load_flow(project, name, version, file):
    if file:
        # Load the registry from the file into the current process's environment
        exec(open(file).read(), locals())

    # Load the user specified flow
    flow = None
    for flow_id, registry_flow in registry.REGISTRY.items():
        if (
            registry_flow.project == project
            and registry_flow.name == name
            and registry_flow.version == version
        ):
            flow = prefect.core.registry.load_flow(flow_id)

    if not flow:
        raise click.ClickException("{} not found in {}".format(name, file))

    return flow


@click.group()
def flows():
    """
    Interact with Prefect flows.
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

    # Load optional parameters
    parameters = None
    flow_run_id = None
    if hasattr(config, "flow_run_id"):
        flow_run_id = config.flow_run_id

    if flow_run_id:
        client = Client(config.API_URL, os.path.join(config.API_URL, "graphql/"))
        client.login(email=config.EMAIL, password=config.PASSWORD)

        flow_runs_gql = FlowRuns(client=client)
        stored_parameters = flow_runs_gql.query(flow_run_id=flow_run_id)

        # TODO: This will change after updated flowruns create function
        if stored_parameters.flowRuns[0].parameters != "<DotDict>":
            parameters = prefect_json.loads(parameters.flowRuns[0].parameters)

    return flow_runner.run(parameters=parameters)


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
    Build a flow's environment.
    """
    flow = load_flow(project, name, version, file)

    # Store output from building environment
    # Use metadata instead of environment object to avoid storing client secrets
    environment_metadata = {
        type(flow.environment).__name__: flow.environment.build(flow=flow)
    }

    return environment_metadata


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
def push(project, name, version, file):
    """
    Push a flow's container environment to a registry.
    """
    config_data = load_prefect_config()
    flow = load_flow(project, name, version, file)

    if not isinstance(flow.environment, ContainerEnvironment):
        raise click.ClickException(
            "{} does not have a ContainerEnvironment".format(name)
        )

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
@click.argument("project")
@click.argument("name")
@click.argument("version")
@click.option(
    "--file",
    required=False,
    help="Path to a file which contains the flow.",
    type=click.Path(exists=True),
)
@click.argument("parameters", required=False)
def deploy(project, name, version, file, parameters):
    """
    Deploy a flow to Prefect Cloud.
    """
    config_data = load_prefect_config()
    flow = load_flow(project, name, version, file)

    client = Client(
        config_data["API_URL"], os.path.join(config_data["API_URL"], "graphql/")
    )
    client.login(email=config_data["EMAIL"], password=config_data["PASSWORD"])

    # Store output from building environment
    # Use metadata instead of environment object to avoid storing client secrets
    environment_metadata = {
        type(flow.environment).__name__: flow.environment.build(flow=flow)
    }
    serialized_flow = flow.serialize()
    serialized_flow["environment"] = prefect_json.dumps(environment_metadata)

    # Create the flow in the database
    try:
        flows_gql = Flows(client=client)
        flow_create_output = flows_gql.create(serialized_flow=serialized_flow)
    except ValueError as value_error:
        if "No project found for" in str(value_error):
            raise click.ClickException("No project found for {}".format(project))
        else:
            raise click.ClickException(str(value_error))

    flow_db_id = flow_create_output.createFlow.flow.id

    # Create Flow Run
    flow_runs_gql = FlowRuns(client=client)
    flow_run_output = flow_runs_gql.create(flow_id=flow_db_id, parameters=parameters)
    flow_run_id = flow_run_output.createFlowRun.flowRun.id

    # Run Flow
    run_flow_gql = RunFlow(client=client)
    run_flow_gql.run_flow(flow_run_id=flow_run_id)

    click.echo("{} deployed.".format(name))

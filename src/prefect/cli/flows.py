# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import json
import os

import click
import pendulum

import prefect
from prefect import config
from prefect.client import Client, FlowRuns, Flows
from prefect.core import registry
from prefect.environments import ContainerEnvironment


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
    click.echo(json.dumps([f.serialize() for f in registry.REGISTRY.values()]))


@flows.command()
def ids():
    """
    Prints all the flows in the registry.
    """
    output = {id: f.key() for id, f in registry.REGISTRY.items()}
    click.echo(json.dumps(output, sort_keys=True))


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
    flow_run_id = config.get("flow_run_id", None)

    if flow_run_id:
        client = Client(config.api_url, os.path.join(config.api_url, "graphql/"))
        client.login(email=config.email, password=config.password)

        flow_runs_gql = FlowRuns(client=client)
        stored_parameters = flow_runs_gql.query(flow_run_id=flow_run_id)

        parameters = stored_parameters.flowRuns[0].parameters

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
    flow = load_flow(project, name, version, file)

    if not isinstance(flow.environment, ContainerEnvironment):
        raise click.ClickException(
            "{} does not have a ContainerEnvironment".format(name)
        )

    # Check if login access was provided for registry
    if config.get("registry_username", None) and config.get("registry_password", None):
        flow.environment.client.login(
            username=config["registry_username"], password=config["registry_password"]
        )

    # Push to registry
    return flow.environment.client.images.push(
        "{}/{}".format(config["registry_url"], flow.environment.image),
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
@click.option(
    "--testing", required=False, is_flag=True, help="Deploy flow in testing mode."
)
@click.argument("parameters", required=False)
def deploy(project, name, version, file, testing, parameters):
    """
    Deploy a flow to Prefect Cloud.
    """
    flow = load_flow(project, name, version, file)

    client = Client()
    client.login(email=config["email"], password=config["password"])

    # Store output from building environment
    # Use metadata instead of environment object to avoid storing client secrets
    environment_metadata = {
        type(flow.environment).__name__: flow.environment.build(flow=flow)
    }
    serialized_flow = flow.serialize()
    serialized_flow["environment"] = json.dumps(environment_metadata)

    flows_gql = Flows(client=client)

    if testing:
        click.echo(
            "Warning: Testing mode overwrites flows with similar project/name/version."
        )
        flow_id = flows_gql.query(
            project_name=project, flow_name=name, flow_version=version
        )

        if flow_id.flows:
            flows_gql.delete(flow_id=flow_id.flows[0].id)

    # Create the flow in the database
    try:
        flow_create_output = flows_gql.create(flow=flow)
    except ValueError as value_error:
        if "No project found for" in str(value_error):
            raise click.ClickException("No project found for {}".format(project))
        else:
            raise click.ClickException(str(value_error))

    flow_db_id = flow_create_output.createFlow.flow.id

    if flow.schedule:
        next_scheduled_run = None
        if flow.schedule.next(1):
            next_scheduled_run = flow.schedule.next(1)[0]

        # Create Flow Run
        flow_runs_gql = FlowRuns(client=client)
        flow_runs_gql.create(
            flow_id=flow_db_id,
            parameters=parameters or {},
            start_time=next_scheduled_run,
        )

    click.echo("{} deployed.".format(name))

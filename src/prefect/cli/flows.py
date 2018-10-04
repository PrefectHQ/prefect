# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import json
import os
from pathlib import Path

import click
import toml

import prefect
from prefect.client import Client, RunFlow, Projects, Flows, FlowRuns, TaskRuns
from prefect.core import registry
from prefect.environments import ContainerEnvironment
from prefect.utilities import json as prefect_json
from prefect.engine.state import Failed, Pending, Retrying, Running, State, Success

def load_prefect_config(path):
    if not path:
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
@click.argument("path", required=False)
def build(project, name, version, file, path):
    """
    Build a flow's environment and push it to a registry.
    """
    config_data = load_prefect_config(path)
    flow = load_flow(project, name, version, file)

    client = Client(
        config_data["API_URL"], os.path.join(config_data["API_URL"], "graphql/")
    )

    client.login(email=config_data["EMAIL"], password=config_data["PASSWORD"])

    # Environment is built and pushed to the registry
    environment_metadata = flow.environment.build(flow=flow)

    # Create the flow in the database
    flows_gql = Flows(client=client)

    try:
        # Store metadata of environment to avoid storing client secrets
        serialized_flow = flow.serialize()
        serialized_flow["environment"] = prefect_json.dumps(environment_metadata)
        flows_gql.create(serialized_flow=serialized_flow)
    except ValueError as value_error:
        if "No project found for" in str(value_error):
            raise click.ClickException("No project found for {}".format(project))
        else:
            raise click.ClickException(str(value_error))


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
@click.argument("path", required=False)
def push(project, name, version, file, path):
    """
    Push a flow's container environment to a registry.
    """
    config_data = load_prefect_config(path)
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
@click.argument("path", required=False)
def deploy(project, name, version, file, path):
    """
    Deploy a running flow.
    """
    config_data = load_prefect_config(path)
    flow = load_flow(project, name, version, file)

    client = Client(
        config_data["API_URL"], os.path.join(config_data["API_URL"], "graphql/")
    )

    client.login(email=config_data["EMAIL"], password=config_data["PASSWORD"])

    # Create the flow in the database
    flows_gql = Flows(client=client)
    environment = flows_gql.query_environment_metadata(
        flow.project, flow.name, flow.version
    )

    # Load flow id and environment metadata
    flow_db_id = environment.flows[0].id
    environment = prefect_json.loads(environment.flows[0].environment)
    image_name = os.path.join(config_data["REGISTRY_URL"], environment["image_name"])

    # Create Flow Run
    flow_runs_gql = FlowRuns(client=client)
    flow_run_output = flow_runs_gql.create(
        flow_id=flow_db_id, parameters=flow.parameters()
    )
    flow_run_id = flow_run_output.createFlowRun.flow_run.id

    # Run Flow
    run_flow_gql = RunFlow(client=client)
    run_flow_gql.run_flow(
        image_name=image_name,
        image_tag=environment["image_tag"],
        flow_id=environment["flow_id"],
        flow_run_id=flow_run_id,
    )

    click.echo("{} deployed.".format(name))

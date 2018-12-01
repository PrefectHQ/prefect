# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import json

import click

import prefect
from prefect import config
from prefect.client import Client
from prefect.core import registry


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
        client = Client()
        client.login(email=config.email, password=config.password)

        flow_run_info = client.get_flow_run_info(flow_run_id=flow_run_id)
        parameters = flow_run_info.parameters

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

    return flow.serialize(build=True)


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

    flow.environment = flow.environment.build(flow=flow)

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

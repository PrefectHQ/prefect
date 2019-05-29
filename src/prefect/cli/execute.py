import click

import prefect
from prefect.client import Client
from prefect.utilities.graphql import with_args


@click.group(hidden=True)
def execute():
    """
    Execute flow environments.

    \b
    Usage:
        $ prefect execute [OBJECT]

    \b
    Arguments:
        local-flow  Execute a local flow's environment
        cloud-flow  Execute a cloud flow's environment (during deployment)

    \b
    Examples:
        $ prefect execute cloud-flow

    \b
        $ prefect execute local-flow ~/.prefect/flows/my_flow.prefect
    """
    pass


@execute.command(hidden=True)
def local_flow():
    """
    Execute a flow's environment locally.
    """
    pass


@execute.command(hidden=True)
def cloud_flow():
    """
    Execute a flow's environment in the context of Prefect Cloud.

    Note: this is a command that runs during Cloud execution of flows and is not meant
    for local use.
    """
    flow_run_id = prefect.context.get("flow_run_id")
    if not flow_run_id:
        click.echo("Not currently executing a flow within a cloud context.")
        return

    query = {
        "query": {
            with_args("flow_run", {"where": {"id": {"_eq": flow_run_id}}}): {
                "flow": {"name": True, "storage": True, "environment": True}
            }
        }
    }

    result = Client().graphql(query)

    flow_data = result.data.flow_run[0].flow

    storage_schema = prefect.serialization.storage.StorageSchema()
    storage = storage_schema.load(flow_data.storage)

    environment_schema = prefect.serialization.environment.EnvironmentSchema()
    environment = environment_schema.load(flow_data.environment)

    environment.setup(storage=storage)
    environment.execute(storage=storage, flow_location=storage.flows[flow_data.name])

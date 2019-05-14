import time

import click

from prefect.client import Client
from prefect.utilities.graphql import with_args, EnumValue


@click.group(hidden=True)
def run():
    """
    Run Prefect flows.

    \b
    Usage:
        $ prefect run [STORAGE/PLATFORM]

    \b
    Arguments:
        cloud   Run flows in Prefect Cloud
        docker  Run flows from Docker storage
        local   Run flows from Local storage

    \b
    Examples:
        $ prefect run cloud --name Test-Flow --project My-Project
        Flow Run ID: 2ba3rrfd-411c-4d99-bb2a-f64a6dea78f9

    \b
        $ prefect run cloud --name Test-Flow --project My-Project --watch
        Flow Run ID: 2ba3rrfd-411c-4d99-bb2a-f64a6dea78f9
        Scheduled -> Submitted -> Running -> Success
    """
    pass


@run.command(hidden=True)
@click.option("--name", "-n", required=True, help="The name of a flow to run.")
@click.option(
    "--project", "-p", required=True, help="The project that contains the flow."
)
@click.option("--version", "-v", type=int, help="A flow version to run.")
@click.option(
    "--watch", "-w", is_flag=True, help="Watch current state of the flow run."
)
def cloud(name, project, version, watch):
    """
    Run a deployed flow in Prefect Cloud.
    """

    query = {
        "query": {
            with_args(
                "flow",
                {
                    "where": {
                        "_and": {
                            "name": {"_eq": name},
                            "version": {"_eq": version},
                            "project": {"name": {"_eq": project}},
                        }
                    },
                    "order_by": {
                        "name": EnumValue("asc"),
                        "version": EnumValue("desc"),
                    },
                    "distinct_on": EnumValue("name"),
                },
            ): {"id": True}
        }
    }

    client = Client()
    result = client.graphql(query)

    flow_data = result.data.flow

    if flow_data:
        flow_id = flow_data[0].id
    else:
        click.secho("{} not found".format(name), fg="red")
        return

    flow_run_id = client.create_flow_run(flow_id=flow_id)
    click.echo("Flow Run ID: {}".format(flow_run_id))

    # TODO: Convert to using a subscription and make output prettier
    if watch:
        current_state = ""
        while True:
            query = {
                "query": {
                    with_args("flow_run_by_pk", {"id": flow_run_id}): {"state": True}
                }
            }

            result = client.graphql(query)

            if result.data.flow_run_by_pk.state != current_state:
                current_state = result.data.flow_run_by_pk.state
                if current_state != "Success" and current_state != "Failed":
                    click.echo("{} -> ".format(current_state), nl=False)
                else:
                    click.echo(current_state)
                    break
            time.sleep(3)


@run.command(hidden=True)
def local():
    """
    Run a local Prefect flow.
    """
    pass


@run.command(hidden=True)
def docker():
    """
    Run a Prefect flow using a Docker storage
    """
    pass

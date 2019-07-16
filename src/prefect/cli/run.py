import time

import click
from tabulate import tabulate

from prefect.client import Client
from prefect.utilities.graphql import EnumValue, with_args


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
@click.option(
    "--name", "-n", required=True, help="The name of a flow to run.", hidden=True
)
@click.option(
    "--project",
    "-p",
    required=True,
    help="The project that contains the flow.",
    hidden=True,
)
@click.option("--version", "-v", type=int, help="A flow version to run.", hidden=True)
@click.option(
    "--watch",
    "-w",
    is_flag=True,
    help="Watch current state of the flow run.",
    hidden=True,
)
@click.option(
    "--logs", "-l", is_flag=True, help="Live logs of the flow run.", hidden=True
)
def cloud(name, project, version, watch, logs):
    """
    Run a deployed flow in Prefect Cloud.

    \b
    Options:
        --name, -n      TEXT    The name of a flow to run                                       [required]
        --project, -p   TEXT    The name of a project that contains the flow                    [required]
        --version, -v   INTEGER A flow version to run
        --watch, -w             Watch current state of the flow run, stream output to stdout
        --logs, -l              Get logs of the flow run, stream output to stdout
    """

    if watch and logs:
        click.secho(
            "Streaming state and logs not currently supported together.", fg="red"
        )
        return

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

    if logs:
        all_logs = []

        log_query = {
            with_args(
                "logs", {"order_by": {EnumValue("timestamp"): EnumValue("asc")}}
            ): {"timestamp": True, "message": True, "level": True},
            "start_time": True,
        }

        query = {
            "query": {
                with_args(
                    "flow_run",
                    {
                        "where": {"id": {"_eq": flow_run_id}},
                        "order_by": {EnumValue("start_time"): EnumValue("desc")},
                    },
                ): log_query
            }
        }

        while True:
            result = Client().graphql(query)

            flow_run = result.data.flow_run
            if not flow_run:
                click.secho("{} not found".format(flow_run_id), fg="red")
                return

            new_run = flow_run[0]
            logs = new_run.logs
            output = []

            for i in logs:
                if [i.timestamp, i.level, i.message] not in all_logs:

                    if not len(all_logs):
                        click.echo(
                            tabulate(
                                [[i.timestamp, i.level, i.message]],
                                headers=["TIMESTAMP", "LEVEL", "MESSAGE"],
                                tablefmt="plain",
                                numalign="left",
                                stralign="left",
                            )
                        )
                        all_logs.append([i.timestamp, i.level, i.message])
                        continue

                    output.append([i.timestamp, i.level, i.message])
                    all_logs.append([i.timestamp, i.level, i.message])

            if output:
                click.echo(
                    tabulate(output, tablefmt="plain", numalign="left", stralign="left")
                )

            time.sleep(3)

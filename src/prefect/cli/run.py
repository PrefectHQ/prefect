import json
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
        flow    Run a flow with a backend API

    \b
    Examples:
        $ prefect run flow --name Test-Flow --project My-Project -ps '{"my_param": 42}'
        Flow Run: https://cloud.prefect.io/myslug/flow-run/2ba3rrfd-411c-4d99-bb2a-f64a6dea78f9

    \b
        $ prefect run flow --name Test-Flow --project My-Project --watch
        Flow Run: https://localhost:8080/flow-run/2ba3rrfd-411c-4d99-bb2a-f64a6dea78f9
        Scheduled -> Submitted -> Running -> Success
    """


@run.command(hidden=True)
@click.option(
    "--id", "-i", required=False, help="The id of a flow to run.", hidden=True
)
@click.option(
    "--version-group-id",
    required=False,
    help="The id of a flow version group to run.",
    hidden=True,
)
@click.option(
    "--name", "-n", required=False, help="The name of a flow to run.", hidden=True
)
@click.option(
    "--project",
    "-p",
    required=False,
    help="The project that contains the flow.",
    hidden=True,
)
@click.option("--version", "-v", type=int, help="A flow version to run.", hidden=True)
@click.option(
    "--parameters-file",
    "-pf",
    help="A parameters JSON file.",
    hidden=True,
    type=click.Path(exists=True),
)
@click.option(
    "--parameters-string", "-ps", help="A parameters JSON string.", hidden=True
)
@click.option("--run-name", "-rn", help="A name to assign for this run.", hidden=True)
@click.option("--context", "-c", help="A context JSON string.", hidden=True)
@click.option(
    "--watch",
    "-w",
    is_flag=True,
    help="Watch current state of the flow run.",
    hidden=True,
)
@click.option(
    "--label",
    "labels",
    help="A list of labels to apply to the flow run",
    hidden=True,
    multiple=True,
)
@click.option(
    "--logs", "-l", is_flag=True, help="Live logs of the flow run.", hidden=True
)
@click.option(
    "--no-url",
    is_flag=True,
    help="Only output flow run id instead of link.",
    hidden=True,
)
def flow(
    id,
    version_group_id,
    name,
    project,
    version,
    parameters_file,
    parameters_string,
    run_name,
    context,
    watch,
    labels,
    logs,
    no_url,
):
    """
    Run a flow that is registered to the Prefect API

    \b
    Options:
        --id, -i                    TEXT        The ID of a flow to run
        --version-group-id          TEXT        The ID of a flow version group to run
        --name, -n                  TEXT        The name of a flow to run
        --project, -p               TEXT        The name of a project that contains the flow
        --version, -v               INTEGER     A flow version to run
        --parameters-file, -pf      FILE PATH   A filepath of a JSON file containing
                                                parameters
        --parameters-string, -ps    TEXT        A string of JSON parameters (note: to ensure these are
                                                parsed correctly, it is best to include the full payload
                                                within single quotes)
        --run-name, -rn             TEXT        A name to assign for this run
        --context, -c               TEXT        A string of JSON key / value pairs to include in context
                                                (note: to ensure these are parsed correctly, it is best
                                                to include the full payload within single quotes)
        --watch, -w                             Watch current state of the flow run, stream
                                                output to stdout
        --label                     TEXT        Set labels on the flow run; use multiple times to set
                                                multiple labels.
        --logs, -l                              Get logs of the flow run, stream output to
                                                stdout
        --no-url                                Only output the flow run id instead of a
                                                link

    \b
    Either `id`, `version-group-id`, or both `name` and `project` must be provided to run a flow.

    \b
    If both `--parameters-file` and `--parameters-string` are provided then the values
    passed in through the string will override the values provided from the file.

    \b
    e.g.
    File contains:  {"a": 1, "b": 2}
    String:         '{"a": 3}'
    Parameters passed to the flow run: {"a": 3, "b": 2}

    \b
    Example:
        $ prefect run flow -n "Test-Flow" -p "My Project" -ps '{"my_param": 42}'
        Flow Run: https://cloud.prefect.io/myslug/flow-run/2ba3rrfd-411c-4d99-bb2a-f64a6dea78f9
    """
    if not id and not (name and project) and not version_group_id:
        click.secho(
            "A flow ID, version group ID, or a combination of flow name and project must be provided.",
            fg="red",
        )
        return

    if sum(map(bool, (id, version_group_id, name))) != 1:
        click.secho(
            "Only one of flow ID, version group ID, or a name/project combination can be provided.",
            fg="red",
        )
        return

    if watch and logs:
        click.secho(
            "Streaming state and logs not currently supported together.", fg="red"
        )
        return

    if labels == ():
        labels = None

    client = Client()
    flow_id = id
    if not flow_id and not version_group_id:
        where_clause = {
            "_and": {
                "name": {"_eq": name},
                "version": {"_eq": version},
                "project": {"name": {"_eq": project}},
            }
        }

        query = {
            "query": {
                with_args(
                    "flow",
                    {
                        "where": where_clause,
                        "order_by": {
                            "name": EnumValue("asc"),
                            "version": EnumValue("desc"),
                        },
                        "distinct_on": EnumValue("name"),
                    },
                ): {"id": True}
            }
        }

        result = client.graphql(query)

        flow_data = result.data.flow

        if flow_data:
            flow_id = flow_data[0].id
        else:
            click.secho("{} not found".format(name), fg="red")
            return

    # Load parameters from file if provided
    file_params = {}
    if parameters_file:
        with open(parameters_file) as params_file:
            file_params = json.load(params_file)

    # Load parameters from string if provided
    string_params = {}
    if parameters_string:
        string_params = json.loads(parameters_string)

    if context:
        context = json.loads(context)
    flow_run_id = client.create_flow_run(
        flow_id=flow_id,
        version_group_id=version_group_id,
        context=context,
        labels=labels,
        parameters={**file_params, **string_params},
        run_name=run_name,
    )

    if no_url:
        click.echo("Flow Run ID: {}".format(flow_run_id))
    else:
        flow_run_url = client.get_cloud_url("flow-run", flow_run_id)
        click.echo("Flow Run: {}".format(flow_run_url))

    if watch:
        current_states = []
        while True:
            query = {
                "query": {
                    with_args("flow_run_by_pk", {"id": flow_run_id}): {
                        with_args(
                            "states",
                            {"order_by": {EnumValue("timestamp"): EnumValue("asc")}},
                        ): {"state": True, "timestamp": True}
                    }
                }
            }

            result = client.graphql(query)

            # Filter through retrieved states and output in order
            for state_index in result.data.flow_run_by_pk.states:
                state = state_index.state
                if state not in current_states:
                    if state != "Success" and state != "Failed":
                        click.echo("{} -> ".format(state), nl=False)
                    else:
                        click.echo(state)
                        return flow_run_id

                    current_states.append(state)

            time.sleep(3)

    if logs:
        all_logs = []

        log_query = {
            with_args(
                "logs", {"order_by": {EnumValue("timestamp"): EnumValue("asc")}}
            ): {"timestamp": True, "message": True, "level": True},
            "start_time": True,
            "state": True,
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
            result = client.graphql(query)

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

            if new_run.state == "Success" or new_run.state == "Failed":
                return flow_run_id

            time.sleep(3)

    return flow_run_id

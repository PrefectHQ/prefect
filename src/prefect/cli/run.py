import json
import textwrap
import time
import os

import click
from click import ClickException
from tabulate import tabulate

from prefect.client import Client
from prefect.utilities.graphql import EnumValue, with_args
from prefect.cli.build_register import load_flows_from_script, load_flows_from_module
from prefect.backend.flow import FlowView


def get_flow_id_by_flow_group(flow_group_id: str) -> str:
    """
    Get the UUID of the newest flow in a flow group

    Args:
        flow_group_id:

    Returns:
        A flow id
    """
    return ""


def get_flow_id_by_name(flow_name: str, project_name: str = None) -> str:
    """
    Get the UUID of a flow by name (and project). An error will be thrown if a project
    is not provided and the flow name exists across projects.

    Args:
        flow_name:
        project_name:

    Returns:

    """
    return ""


def get_flow_id_by_flow_object(flow: "prefect.Flow") -> str:
    return ""


def get_flow(
    flow_id: str, flow_group_id: str, project: str, path: str, module: str, name: str
) -> "FlowView":
    # Ensure that the user has not passed conflicting options
    given_lookup_options = {
        key
        for key, option in {
            "--flow-id": flow_id,
            "--flow-group-id": flow_group_id,
            "--project": project,
            "--path": path,
            "--module": module,
        }.items()
        if option is not None
    }
    if not given_lookup_options:
        raise ClickException(
            "Received no options to look up the flow." + FLOW_LOOKUP_MSG
        )
    if len(given_lookup_options) > 1:
        raise ClickException(
            "Received too many options to look up the flow: "
            f"{', '.join(given_lookup_options)}" + FLOW_LOOKUP_MSG
        )

    if flow_id:
        return FlowView.from_flow_id(flow_id)

    if flow_group_id:
        return FlowView.from_flow_group_id(flow_group_id)

    if project:
        if not name:
            raise ClickException(
                "Missing required option `--name`. Cannot look up a flow by project "
                "without also passing a name."
            )
        return FlowView.from_flow_name(flow_name=name, project_name=project)

    if path or module:
        location = path if path is not None else module
        flows = load_flows_from_script(path) if path else load_flows_from_module(module)
        flows_by_name = {flow.name: flow for flow in flows}
        flow_names = ", ".join(map(repr, flows_by_name.keys()))

        if not flows:
            raise ClickException(f"Found no flows at {location}.")

        if len(flows) > 1 and not name:
            raise ClickException(
                f"Found multiple flows at {location}: {flow_names}\n\n"
                f"Specify a flow name to run."
            )
        if name:
            if name not in flows_by_name:
                raise ClickException(
                    f"Did not find {name!r} in flows at {location}. Found {flow_names}"
                )
            flow = flows_by_name[name]
        else:
            flow = list(flows_by_name.values())[0]
            click.echo(f"Found flow {flow.name} at {location}")

        return FlowView.from_flow_obj(flow)

    if name and not flow_id:
        # If name wasn't provided for use with another lookup, try a global name search
        return FlowView.from_flow_name(flow_name=name)

    # This line should not be reached
    raise RuntimeError("Failed to find matching case for flow lookup.")


RUN_EPILOG = """
\bExamples:

\b  Register all flows found in a directory.

\b    $ prefect register --project my-project -p myflows/
"""


FLOW_LOOKUP_MSG = """

Look up a flow to run with one of the following option combinations:
    --flow-id
    --flow-group-id
    --project and --name
    --path (--name if there are multiple flows)
    --module (and --name if there are multiple flows)
    
See `prefect run --help` for more details on the options.
"""


@click.group(invoke_without_command=True, epilog=RUN_EPILOG)
@click.pass_context
# Flow lookup settings -----------------------------------------------------------------
@click.option("--flow-id", help="The UUID of a flow to run.", default=None)
@click.option(
    "--flow-group-id",
    help="The UUID of a flow group to run the latest flow from.",
    default=None,
)
@click.option(
    "--project",
    help="The name of the Prefect project containing the flow to run.",
    default=None,
)
@click.option(
    "--path",
    "-p",
    help="The path to a file or a directory containing the flow to run.",
)
@click.option(
    "--module",
    "-m",
    help="The python module name containing the flow to run.",
)
@click.option(
    "--name",
    "-n",
    help=(
        "The name of a flow to run from the specified path/module/project. If the "
        "source contains multiple flows, this must be provided. "
    ),
)
# Flow run settings --------------------------------------------------------------------
@click.option(
    "--label",
    "-l",
    "labels",
    help=(
        "A label to add to the flow run. May be passed multiple times to specify "
        "multiple labels."
    ),
    multiple=True,
)
@click.option("--run-name", help="A name to assign to the flow run.", default=None)
@click.option(
    "--context",
    help="A JSON string specifying a Prefect context to set for the flow run.",
    default=None,
)
@click.option(
    "--param",
    "-p",
    "params",
    help=(
        "A key, value pair specifying a value for a parameter. The value will be "
        "interpreted as JSON. May be passed multiple times to specify multiple "
        "parameter values."
    ),
    multiple=True,
    type=(str, str),
)
@click.option(
    "--param-file",
    help=(
        "The path to a JSON file containing parameter keys and values. Any parameters "
        "passed with `--param` will take precedence over these values."
    ),
    default=None,
)
@click.option(
    "--no-backend",
    help=(
        "Run the flow locally using `flow.run()` instead of creating a flow run using "
        "the Prefect backend API. Implies `--wait`."
    ),
    default=False,
)
@click.option(
    "--no-agent",
    help=(
        "Run the flow inline instead of using an agent. This allows the flow run to "
        "be inspected with breakpoints during execution. Implies `--wait`."
    ),
    default=False,
)
# Display settings ---------------------------------------------------------------------
@click.option(
    "--quiet",
    "-q",
    help="Disable verbose messaging about the flow run and just print the flow run id",
    default=False,
)
@click.option(
    "--stream-logs",
    "-l",
    help="Stream logs from the flow run to this terminal. Implies `--wait`.",
    default=False,
)
@click.option(
    "--wait",
    "-w",
    help="Wait for the flow run to finish executing, displaying status information.",
    default=False,
)
def run(
    ctx,
    flow_id,
    flow_group_id,
    project,
    path,
    module,
    name,
    labels,
    context,
    params,
    param_file,
    no_backend,
    no_agent,
    run_name,
    quiet,
    stream_logs,
    wait,
):
    """Run a flow"""
    # Since the old command was a subcommand of this, we have to do some
    # mucking to smoothly deprecate it. Can be removed with `prefect run flow`
    # is removed.
    if ctx.invoked_subcommand is not None:
        if any([params, stream_logs, quiet, wait, no_agent, no_backend, flow_id]):
            # These options are not supported by `prefect run flow`
            raise ClickException(
                "Got unexpected extra argument (%s)" % ctx.invoked_subcommand
            )
        return

    # Validate the flow look up options we've been given and get a flow id
    if not no_backend:
        flow_id = get_flow_id(
            flow_id=flow_id,
            flow_group_id=flow_group_id,
            project=project,
            path=path,
            module=module,
            name=name,
        )


@run.command(hidden=True)
@click.option("--flow-id", help="The UUID of a flow to run.", default=None)
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

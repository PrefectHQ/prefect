from typing import Optional

import json
import textwrap
import time
import uuid
import logging
import sys
from functools import partial

import click
from click import ClickException
from tabulate import tabulate

import prefect
from prefect.client import Client
from prefect.utilities.graphql import EnumValue, with_args
from prefect.cli.build_register import (
    load_flows_from_script,
    load_flows_from_module,
    log_exception,
)
from prefect.run_configs import RunConfig
from prefect.serialization.run_config import RunConfigSchema
from prefect.backend.flow import FlowView
from prefect.backend.flow_run import execute_flow_run, watch_flow_run, FlowRunView
from prefect.utilities.logging import get_logger


def echo_with_log_color(log_level: int, message: str, prefix: str = ""):
    extra = {}
    if log_level >= logging.ERROR:
        color = "red"
    elif log_level >= logging.WARNING:
        color = "yellow"
    elif log_level <= logging.DEBUG:
        color = "white"
        extra["dim"] = True
    else:
        color = "white"

    click.secho(prefix + message, fg=color, **extra)


def get_flow_from_path_or_module(
    path: str = None, module: str = None, name: str = None
):
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

    return flow


def get_flow_view(
    flow_or_group_id: str = None,
    project: str = None,
    path: str = None,
    module: str = None,
    name: str = None,
) -> "FlowView":
    if flow_or_group_id:
        # Lookup by flow id then flow group id if that fails
        try:
            flow_view = FlowView.from_flow_id(flow_or_group_id)
        except ValueError:
            pass
        else:
            return flow_view

        try:
            flow_view = FlowView.from_flow_group_id(flow_or_group_id)
        except ValueError:
            pass
        else:
            return flow_view

        # Fall through to failure
        raise ClickException(
            f"Failed to find flow id or flow group id matching {flow_or_group_id}"
        )

    if project:
        if not name:
            raise ClickException(
                "Missing required option `--name`. Cannot look up a flow by project "
                "without also passing a name."
            )
        return FlowView.from_flow_name(flow_name=name, project_name=project)

    if path or module:
        flow = get_flow_from_path_or_module(path=path, module=module, name=name)
        return FlowView.from_flow_obj(flow)

    if name:
        # If name wasn't provided for use with another lookup, try a global name search
        return FlowView.from_flow_name(flow_name=name)

    # This line should not be reached
    raise RuntimeError("Failed to find matching case for flow lookup.")


RUN_EPILOG = """
\bExamples:

\b  Run flow in a script locally

\b    $ prefect run -p hello-world.py --local

\b  Run flow in a module locally

\b    $ prefect run -m prefect.hello_world --local

\b  Run registered flow with the backend by flow name and watch execution

\b    $ prefect run -n "hello-world" --watch

\b  Run registered flow with the backend by flow id and exit after creation

\b    $ prefect run -i "9a1cd70c-37d7-4cd4-ab91-d41c2700300d"

\b  Run registered flow with backend reporting in-process instead of with an agent

\b    $ prefect run -n "hello-world" --no-agent

\b  Run registered flow with the backend and pipe flow run id to another program

\b    $ prefect run -n "hello-world" -q | post_run.sh
"""

FLOW_LOOKUP_MSG = """

Look up a flow to run with one of the following option combinations:
    --id
    --name
    --project and --name
    --path (and --name if there are multiple flows in the script)
    --module (and --name if there are multiple flows in the module)
    
See `prefect run --help` for more details on the options.
"""


@click.group(invoke_without_command=True, epilog=RUN_EPILOG)
@click.pass_context
# Flow lookup settings -----------------------------------------------------------------
@click.option(
    "--id",
    "-i",
    "flow_or_group_id",
    help=(
        "The UUID of a flow or flow group to run. If a flow group id is given, "
        "the latest flow id will be used for the run."
    ),
)
@click.option(
    "--project",
    help="The name of the Prefect project containing the flow to run.",
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
        "multiple labels. If not passed, the labels from the flow group will be used."
    ),
    multiple=True,
)
@click.option("--run-name", help="A name to assign to the flow run.", default=None)
@click.option(
    "--context",
    help="A JSON string specifying a Prefect context to set for the flow run.",
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
    "--log-level",
    help=(
        "The log level to set for the flow run. "
        "If not set, the default level will be used."
    ),
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    default=None,
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
        "the Prefect backend API. Implies `--watch`."
    ),
    is_flag=True,
)
@click.option(
    "--no-agent",
    help=(
        "Run the flow inline instead of using an agent. This allows the flow run to "
        "be inspected with breakpoints during execution. Implies `--watch`."
    ),
    is_flag=True,
)
# Display settings ---------------------------------------------------------------------
@click.option(
    "--quiet",
    "-q",
    help=(
        "Disable verbose messaging about the flow run and just print the flow run id. "
        "Not applicable when `--watch` is not set."
    ),
    is_flag=True,
)
@click.option(
    "--no-logs",
    help=(
        "Disable streaming logs from the flow run to this terminal. Only state changes "
        "will be displayed. Not applicable when `--watch` is not set."
    ),
    is_flag=True,
)
@click.option(
    "--watch",
    "-w",
    help="Wait for the flow run to finish executing and display status information.",
    is_flag=True,
)
def run(
    ctx,
    flow_or_group_id,
    project,
    path,
    module,
    name,
    labels,
    context,
    params,
    log_level,
    param_file,
    no_backend,
    no_agent,
    run_name,
    quiet,
    no_logs,
    watch,
):
    """Run a flow"""
    # Since the old command was a subcommand of this, we have to do some
    # mucking to smoothly deprecate it. Can be removed with `prefect run flow`
    # is removed.
    if ctx.invoked_subcommand is not None:
        if any([params, no_logs, quiet, no_agent, no_backend, flow_id]):
            # These options are not supported by `prefect run flow`
            raise ClickException(
                "Got unexpected extra argument (%s)" % ctx.invoked_subcommand
            )
        return

    # Define a simple function so we don't have to have a lot of `if not quiet` logic
    def quiet_echo(*args, **kwargs):
        if not quiet:
            click.secho(*args, **kwargs)

    # Cast labels to a list instead of a tuple so we can extend it
    labels = list(labels)

    # We will wait for flow completion if any of these are set
    wait = watch or no_agent or no_backend

    # Ensure that the user has not passed conflicting options
    given_lookup_options = {
        key
        for key, option in {
            "--id": flow_or_group_id,
            "--project": project,
            "--path": path,
            "--module": module,
        }.items()
        if option is not None
    }
    # Since `name` can be passed in conjunction with several options and also alone
    # it requires a special case here
    if not given_lookup_options and not name:
        raise ClickException(
            "Received no options to look up the flow." + FLOW_LOOKUP_MSG
        )
    if len(given_lookup_options) > 1:
        raise ClickException(
            "Received too many options to look up the flow: "
            f"{', '.join(given_lookup_options)}" + FLOW_LOOKUP_MSG
        )

    # Load parameters and context ------------------------------------------------------

    # TODO: Wrap exceptions for a nicer message
    # TODO: Consider loading context like params
    context_dict = json.loads(context) if context is not None else {}

    params_dict = {}
    if param_file:
        # TODO: Wrap exceptions for a nicer message
        with open(param_file) as fp:
            params_dict = json.load(fp)
    for key, value in params:  # List[str, str]
        if key in params_dict:
            quiet_echo(
                f"Warning: Parameter {key!r} was set twice. Overriding with CLI value.",
            )
        # TODO: Wrap exceptions for a nicer message
        params_dict[key] = json.loads(value)

    # Run the flow (cloud) -------------------------------------------------------------

    if not no_backend:

        client = Client()

        # Validate the flow look up options we've been given and get the flow from the
        # backend
        quiet_echo(f"Looking up flow metadata...", nl=False)
        try:
            flow = get_flow_view(
                flow_or_group_id=flow_or_group_id,
                project=project,
                path=path,
                module=module,
                name=name,
            )
        except Exception as exc:
            quiet_echo(" Error", fg="red")
            quiet_echo(f"{exc}")
            sys.exit(1)
        else:
            quiet_echo(" Done", fg="green")

        if no_agent:
            # Add a random label to prevent an agent from picking up this run
            labels.append(f"no-agent-run-{str(uuid.uuid4())[:8]}")

        if log_level:
            run_config: Optional[RunConfig] = RunConfigSchema().load(flow.run_config)
            if not run_config.env:
                run_config.env = {}
            run_config.env["PREFECT__LOGGING__LEVEL"] = log_level
        else:
            run_config = None

        # Create a flow run in the backend
        quiet_echo(f"Creating run for flow {flow.name!r}...", nl=False)
        try:
            flow_run_id = client.create_flow_run(
                flow_id=flow.flow_id,
                parameters=params_dict,
                context=context_dict,
                # If labels is an empty list pass `None` to get defaults
                labels=labels or None,
                run_name=run_name,
                # We only use the run config for setting logging levels right now
                run_config=run_config,
            )
        except Exception as exc:
            quiet_echo(" Error", fg="red")
            log_exception(exc, indent=2)
            sys.exit(1)

        if quiet:
            # Just display the flow run id in quiet mode
            click.echo(flow_run_id)
        else:
            # Grab information about the flow run (if quiet we can skip this query)
            flow_run = FlowRunView.from_flow_run_id(flow_run_id)
            run_url = client.get_cloud_url("flow-run", flow_run_id)

            # Display "Done" for creating flow run after pulling the info so there
            # isn't a lag
            quiet_echo(" Done", fg="green")
            quiet_echo(
                textwrap.dedent(
                    f"""
                    └── Name: {flow_run.name}
                    └── UUID: {flow_run.flow_run_id}
                    └── Labels: {flow_run.labels}
                    └── Parameters: {flow_run.parameters}
                    └── Context: {flow_run.context}
                    └── URL: {run_url}
                    """
                ).strip()
            )

        # Exit now if we're not waiting for execution to finish
        if not wait:
            return

        # Execute it here if they've specified `--no-agent`
        if no_agent:
            # TODO: Check for compatibility with run types? Something like a
            #       DockerRun may not behave well and we should probably warn
            quiet_echo("Running flow in-process...")
            execute_flow_run(flow_run_id=flow_run_id)

        # Otherwise, we'll watch for state changes
        else:
            result = None
            try:
                quiet_echo("Watching flow run execution...")
                result = watch_flow_run(
                    flow_run_id=flow_run_id,
                    stream_logs=not no_logs,
                    output_fn=partial(echo_with_log_color, prefix="└── "),  # type: ignore
                )
            except KeyboardInterrupt:
                quiet_echo("Keyboard interrupt detected!", fg="yellow")
                try:
                    # TODO: Improve and clarify this messaging, consider having this
                    #       apply from flow run creation -> now
                    cancel = click.confirm(
                        "Do you want to cancel this flow run?", default=True
                    )
                except click.Abort:
                    # A second keyboard interrupt will exit without cancellation
                    pass
                else:
                    if cancel:
                        client.cancel_flow_run(flow_run_id=flow_run_id)
                        quiet_echo("Cancelled flow run successfully.")
                        return

                quiet_echo("Exiting without cancelling flow run!", fg="yellow")
                raise

            if result.state.is_failed():
                quiet_echo("Flow run failed!", fg="red")
            else:
                quiet_echo("Flow run succeeded!", fg="green")

    # Run the flow (local) -------------------------------------------------------------

    else:
        flow = get_flow_from_path_or_module(path=path, module=module, name=name)

        # Set the desired log level
        if log_level:
            logger = get_logger()
            logger.setLevel(log_level)

        with prefect.context(**context_dict):
            flow.run(parameters=params_dict)


# DEPRECATED: prefect run flow ---------------------------------------------------------


@run.command("flow", hidden=True)
@click.option("--id", help="The UUID of a flow to run.", default=None)
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
def run_flow(
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

    DEPRECATED: Use `prefect run` instead of `prefect run flow`

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

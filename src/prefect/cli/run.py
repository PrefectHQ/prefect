import click
import json
import os
import logging
import textwrap
import time
import uuid
from click import ClickException
from contextlib import contextmanager
from functools import partial
from tabulate import tabulate
from typing import Optional, Callable, List, Dict, Union

import prefect
from prefect.backend.flow import FlowView
from prefect.backend.flow_run import execute_flow_run, watch_flow_run, FlowRunView
from prefect.cli.build_register import (
    load_flows_from_script,
    load_flows_from_module,
    log_exception,
    TerminalError,
    handle_terminal_error,
)
from prefect.client import Client
from prefect.run_configs import RunConfig
from prefect.serialization.run_config import RunConfigSchema
from prefect.utilities.graphql import EnumValue, with_args
from prefect.utilities.logging import get_logger
from prefect.utilities.configuration import set_temporary_config


@contextmanager
def temporary_environ(environ):
    """
    Temporarily add environment variables to the current os.environ
    The original environment will be restored at context exit
    """
    old_environ = os.environ.copy()
    os.environ.update(environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


@contextmanager
def try_error_done(
    message: str,
    echo: Callable = click.secho,
    traceback: bool = False,
    skip_done: bool = False,
):
    """
    Try to run the code in the context block. On error print "Error" and raise a
    terminal error with the exception string. On succecss, print "Done".

    Args:
        message: The first message to display
        echo: The function to use to echo. Must support `click.secho` arguments
        traceback: Display the exception traceback instead of a short message
        skip_done: Do not display 'Done', the user of the context should instead

    Example:
        >>> with try_error_done("Setting up foo..."):
        >>>    pass
        Setting up foo... Done
        >>> with try_error_done("Setting up bar..."):
        >>>    raise ValueError("no!")
        Setting up bar... Error
        no!
    """
    echo(message, nl=False)
    try:
        yield

    except Exception as exc:
        echo(" Error", fg="red")

        if traceback:
            log_exception(exc, indent=2)
            raise TerminalError
        else:
            raise TerminalError(str(exc))

    else:
        if not skip_done:
            echo(" Done", fg="green")


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

    if name:
        # If name wasn't provided for use with another lookup, try a global name search
        return FlowView.from_flow_name(flow_name=name)

    # This line should not be reached
    raise RuntimeError("Failed to find matching case for flow lookup.")


def load_json_key_values(
    cli_input: List[str], display_name: str
) -> Dict[str, Union[dict, str, int]]:
    """
    Parse a list of strings formatted as "key=value" where the value is loaded as JSON.

    We do the best here to display a helpful JSON parsing message, e.g.
    ```
    Error: Failed to parse JSON for parameter 'name' with value

        foo

    JSON Error: Expecting value: line 1 column 1 (char 0)
    Did you forget to include quotes? You may need to escape so your shell does not remove them, e.g. \"
    ```

    Args:
        cli_input: A list of "key=value" strings to parse
        display_name: A name to display in exceptions

    Returns:
        A mapping of keys -> parsed values
    """
    parsed = {}
    for spec in cli_input:
        try:
            key, value = spec.split("=")
        except ValueError:
            raise ClickException(
                f"Invalid {display_name} option {spec!r}. Expected format 'key=value'."
            )
        try:
            parsed[key] = json.loads(value)
        except ValueError as exc:
            indented_value = textwrap.indent(value, prefix="\t")
            extra_help = ""
            if "Expecting value" in str(exc) and '"' not in value:
                extra_help += (
                    "\nDid you forget to include quotes? You may need to escape so your"
                    ' shell does not remove them, e.g. \\"'
                )
            raise ClickException(
                f"Failed to parse JSON for {display_name} {key!r} with value"
                f"\n\n{indented_value}\n\n"
                f"JSON Error: {exc}{extra_help}"
            )

    return parsed


RUN_EPILOG = """
\bExamples:

\b  Run flow in a script locally

\b    $ prefect run -f hello-world.py --local

\b  Run flow in a module locally

\b    $ prefect run -m prefect.hello_world --local

\b  Run flow with a non-default parameter

\b    $ prefect run -m prefect.hello_world -p name='"Marvin"'

\b  Run flow with custom labels

\b    $ prefect run -m prefect.hello_world -l example -l hello

\b  Run registered flow with the backend by flow name and watch execution

\b    $ prefect run -n "hello-world" --watch

\b  Run registered flow with the backend by flow id and exit after creation

\b    $ prefect run -i "9a1cd70c-37d7-4cd4-ab91-d41c2700300d"

\b  Run registered flow with backend in-process instead of with an agent

\b    $ prefect run -n "hello-world" --execute

\b  Run registered flow with the backend and pipe flow run id to another program

\b    $ prefect run -n "hello-world" --quiet | post_run.sh
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
    help="The path to a file containing the flow to run.",
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
        "The name of a flow to run from the specified file/module/project. If the "
        "source contains multiple flows, this must be provided. "
    ),
)
# Flow run settings --------------------------------------------------------------------
@click.option(
    "--label",
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
    "context_vars",
    help=(
        "A key, value pair (key=value) specifying a flow context variable. The value "
        "will be interpreted as JSON. May be passed multiple times to specify multiple "
        "context values. Nested values may be set by passing a dict."
    ),
    multiple=True,
)
@click.option(
    "--param",
    "params",
    help=(
        "A key, value pair (key=value) specifying a flow parameter. The value will be "
        "interpreted as JSON. May be passed multiple times to specify multiple "
        "parameter values."
    ),
    multiple=True,
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
# Display settings ---------------------------------------------------------------------
@click.option(
    "--quiet",
    "-q",
    help=(
        "Disable verbose messaging about the flow run and just print the flow run id."
    ),
    is_flag=True,
)
@click.option(
    "--no-logs",
    help=(
        "Disable streaming logs from the flow run to this terminal. Only state changes "
        "will be displayed. Only applicable when `--watch` is set."
    ),
    is_flag=True,
)
@click.option(
    "--watch",
    "-w",
    help="Wait for the flow run to finish executing and display status information.",
    is_flag=True,
)
@handle_terminal_error
def run(
    ctx,
    flow_or_group_id,
    project,
    path,
    module,
    name,
    labels,
    context_vars,
    params,
    log_level,
    param_file,
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
        if any([params, no_logs, quiet, execute, local, flow_or_group_id]):
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
    context_dict = load_json_key_values(context_vars, "context")

    file_params = {}
    if param_file:
        # TODO: Wrap exceptions for a nicer message
        with open(param_file) as fp:
            file_params = json.load(fp)

    cli_params = load_json_key_values(params, "parameter")
    conflicting_keys = set(cli_params.keys()).intersection(file_params.keys())
    if conflicting_keys:
        quiet_echo(
            "The following parameters were specified by file and CLI, the CLI value "
            f"will be used: {conflicting_keys}"
        )
    params_dict = {**file_params, **cli_params}

    # Local flow run -------------------------------------------------------------------

    if path or module:
        # We can load a flow for local execution immediately if given a path or module,
        # otherwise, we'll lookup the flow then pull from storage for a local run
        with try_error_done("Retrieving local flow...", quiet_echo):
            flow = get_flow_from_path_or_module(path=path, module=module, name=name)

        # Set the desired log level
        if log_level:
            logger = get_logger()
            logger.setLevel(log_level)

        run_info = ""
        if params_dict:
            run_info += f"└── Parameters: {params_dict}"
        if context_dict:
            run_info += "\n"
            run_info += f"└── Context: {context_dict}"

        if run_info:
            quiet_echo("Configured local flow run")
            quiet_echo(run_info)

        quiet_echo("Running flow locally...")
        with prefect.context(**context_dict):
            try:
                result_state = flow.run(parameters=params_dict)
            except Exception as exc:
                quiet_echo()
                log_exception(exc, indent=2)
                raise TerminalError("Flow run failed!")

        if result_state.is_failed():
            quiet_echo("Flow run failed!", fg="red")
        else:
            quiet_echo("Flow run succeeded!", fg="green")

        return

    # Backend flow run -----------------------------------------------------------------

    client = Client()

    # Validate the flow look up options we've been given and get the flow from the
    # backend
    with try_error_done("Looking up flow metadata...", quiet_echo):
        flow_view = get_flow_view(
            flow_or_group_id=flow_or_group_id,
            project=project,
            name=name,
        )

    if log_level:
        run_config: Optional[RunConfig] = RunConfigSchema().load(flow_view.run_config)
        if not run_config.env:
            run_config.env = {}
        run_config.env["PREFECT__LOGGING__LEVEL"] = log_level
    else:
        run_config = None

    # Create a flow run in the backend
    with try_error_done(
        f"Creating run for flow {flow_view.name!r}...",
        quiet_echo,
        traceback=True,
        skip_done=True,  # Display 'Done' after querying for data to display
    ):
        flow_run_id = client.create_flow_run(
            flow_id=flow_view.flow_id,
            parameters=params_dict,
            context=context_dict,
            # If labels is an empty list pass `None` to get defaults
            # https://github.com/PrefectHQ/server/blob/77c301ce0c8deda4f8771f7e9991b25e7911224a/src/prefect_server/api/runs.py#L136
            labels=labels or None,
            run_name=run_name,
            # We only use the run config for setting logging levels right now
            run_config=run_config,
        )

    if quiet:
        # Just display the flow run id in quiet mode
        click.echo(flow_run_id)
        flow_run = None
    else:
        # Grab information about the flow run (if quiet we can skip this query)
        flow_run = FlowRunView.from_flow_run_id(flow_run_id)
        run_url = client.get_cloud_url("flow-run", flow_run_id)

        # Display "Done" for creating flow run after pulling the info so there
        # isn't a weird lag
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
    if not watch:
        return

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
                "On exit, we can leave your flow run executing or cancel it.\n"
                "Do you want to cancel this flow run?",
                default=True,
            )
        except click.Abort:
            # A second keyboard interrupt will exit without cancellation
            pass
        else:
            if cancel:
                client.cancel_flow_run(flow_run_id=flow_run_id)
                quiet_echo("Cancelled flow run.", fg="green")
                return

        quiet_echo("Exiting without cancelling flow run!", fg="yellow")
        raise  # Re-raise the interrupt

    if result.state.is_failed():
        quiet_echo("Flow run failed!", fg="red")
    else:
        quiet_echo("Flow run succeeded!", fg="green")


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

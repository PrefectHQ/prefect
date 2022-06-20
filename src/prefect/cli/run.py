import json
import logging
import os
import runpy
import sys
import textwrap
import uuid
import time
from contextlib import contextmanager
from types import ModuleType
from typing import Callable, Dict, List, Union, Any

import click
from click import ClickException

import prefect
from prefect.backend.flow import FlowView
from prefect.backend.flow_run import FlowRunView, watch_flow_run
from prefect.backend.execution import execute_flow_run_in_subprocess
from prefect.cli.build_register import (
    TerminalError,
    handle_terminal_error,
    log_exception,
)
from prefect.client import Client
from prefect.utilities.importtools import import_object
from prefect.utilities.logging import temporary_logger_config


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
    except TerminalError:
        echo(" Error", fg="red")
        raise
    except Exception as exc:
        echo(" Error", fg="red")

        if traceback and not isinstance(exc, TerminalError):
            log_exception(exc, indent=2)
            raise TerminalError
        else:
            raise TerminalError(f"{type(exc).__name__}: {exc}")

    else:
        if not skip_done:
            echo(" Done", fg="green")


def echo_with_log_color(log_level: int, message: str, **kwargs: Any):
    if log_level >= logging.ERROR:
        kwargs.setdefault("fg", "red")
    elif log_level >= logging.WARNING:
        kwargs.setdefault("fg", "yellow")
    elif log_level <= logging.DEBUG:
        kwargs.setdefault("fg", "white")
        kwargs.setdefault("dim", True)
    else:
        kwargs.setdefault("fg", "white")

    click.secho(
        message,
        **kwargs,
    )


def load_flows_from_script(path: str) -> "List[prefect.Flow]":
    """Given a file path, load all flows found in the file"""
    # TODO: This is copied and slightly modified from `prefect.cli.build_register`
    #       we should probably abstract this in the future
    # Temporarily add the flow's local directory to `sys.path` so that local
    # imports work. This ensures that `sys.path` is the same as it would be if
    # the flow script was run directly (i.e. `python path/to/flow.py`).
    orig_sys_path = sys.path.copy()
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    try:
        with prefect.context({"loading_flow": True, "local_script_path": path}):
            namespace = runpy.run_path(path, run_name="<flow>")
    except FileNotFoundError as exc:
        if path in str(exc):  # Only capture it if it's about our file
            raise TerminalError(f"File does not exist: {os.path.abspath(path)!r}")
        raise
    finally:
        sys.path[:] = orig_sys_path

    flows = [f for f in namespace.values() if isinstance(f, prefect.Flow)]
    return flows


def load_flows_from_module(name: str) -> "List[prefect.Flow]":
    """
    Given a module name (or full import path to a flow), load all flows found in the
    module
    """
    # TODO: This is copied and slightly modified from `prefect.cli.build_register`
    #       we should probably abstract this in the future
    try:
        with prefect.context({"loading_flow": True}):
            mod_or_obj = import_object(name)
    except Exception as exc:
        # If the requested module isn't found, log without a traceback
        # otherwise log a general message with the traceback.
        if isinstance(exc, ModuleNotFoundError) and (
            name == exc.name
            or (name.startswith(exc.name) and name[len(exc.name)] == ".")
        ):
            raise TerminalError(str(exc).capitalize())
        elif isinstance(exc, AttributeError):
            raise TerminalError(str(exc).capitalize())
        else:
            raise

    if isinstance(mod_or_obj, ModuleType):
        flows = [f for f in vars(mod_or_obj).values() if isinstance(f, prefect.Flow)]
    elif isinstance(mod_or_obj, prefect.Flow):
        flows = [mod_or_obj]
    else:
        raise TerminalError(
            f"Invalid object of type {type(mod_or_obj).__name__!r} found at {name!r}. "
            f"Expected Module or Flow."
        )

    return flows


def get_flow_from_path_or_module(
    path: str = None, module: str = None, name: str = None
):
    location = path if path is not None else module
    flows = load_flows_from_script(path) if path else load_flows_from_module(module)
    flows_by_name = {flow.name: flow for flow in flows}
    flow_names = ", ".join(map(repr, flows_by_name.keys()))

    if not flows:
        raise TerminalError(f"Found no flows at {location}.")

    if len(flows) > 1 and not name:
        raise TerminalError(
            f"Found multiple flows at {location!r}: {flow_names}\n\n"
            f"Specify a flow name to run."
        )
    if name:
        if name not in flows_by_name:
            raise TerminalError(
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
        raise TerminalError(
            f"Failed to find flow id or flow group id matching {flow_or_group_id!r}"
        )

    if project:
        if not name:
            raise TerminalError(
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

    def cast_value(value: str) -> Any:
        """Cast the value from a string to a valid JSON type; add quotes for the user
        if necessary
        """
        try:
            return json.loads(value)
        except ValueError as exc:
            if (
                "Extra data" in str(exc) or "Expecting value" in str(exc)
            ) and '"' not in value:
                return cast_value(f'"{value}"')
            raise exc

    for spec in cli_input:
        try:
            key, _, value = spec.partition("=")
        except ValueError:
            raise TerminalError(
                f"Invalid {display_name} option {spec!r}. Expected format 'key=value'."
            )

        try:
            parsed[key] = cast_value(value)
        except ValueError as exc:
            indented_value = textwrap.indent(value, prefix="\t")
            raise TerminalError(
                f"Failed to parse JSON for {display_name} {key!r} with value"
                f"\n\n{indented_value}\n\n"
                f"JSON Error: {exc}"
            )

    return parsed


RUN_EPILOG = """
\bExamples:

\b  Run flow in a script locally

\b    $ prefect run -p hello-world.py

\b  Run flow in a module locally

\b    $ prefect run -m prefect.hello_world

\b  Run flow with a non-default parameter locally

\b    $ prefect run -m prefect.hello_world --param name=Marvin

\b  Run registered flow with the backend by flow name and watch execution

\b    $ prefect run -n "hello-world" --watch

\b  Run registered flow with the backend with custom labels

\b    $ prefect run -n "hello-world" --label example --label hello

\b  Run registered flow with the backend by flow id and exit after creation

\b    $ prefect run -i "9a1cd70c-37d7-4cd4-ab91-d41c2700300d"

\b  Run registered flow and pipe flow run id to another program

\b    $ prefect run -n "hello-world" --quiet | post_run.sh

\b  Run registered flow and execute locally without an agent

\b    $ prefect run -n "hello-world" --execute
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
        "The log level to set for the flow run. If passed, the level must be a valid "
        "Python logging level name. If this option is not passed, the default level "
        "for the flow will be used."
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
    "--idempotency-key",
    help=(
        "A key to prevent duplicate flow runs. If a flow run has already been started "
        "with the provided value, the command will display information for the "
        "existing run. If using `--execute`, duplicate flow runs will exit with an "
        "error. If not using the backing API, this flag has no effect."
    ),
    default=None,
)
@click.option(
    "--execute",
    help=(
        "Execute the flow run in-process without an agent. If this process exits, the "
        "flow run will be marked as 'Failed'."
    ),
    is_flag=True,
)
@click.option(
    "--schedule",
    "-s",
    help=(
        "Execute the flow run according to the schedule attached to the flow. If this "
        "flag is set, this command will wait between scheduled flow runs. If the flow "
        "has no schedule, this flag will be ignored. If used with a non-local run, an "
        "exception will be thrown."
    ),
    is_flag=True,
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
    flow_or_group_id,
    project,
    path,
    module,
    name,
    labels,
    context_vars,
    params,
    execute,
    idempotency_key,
    schedule,
    log_level,
    param_file,
    run_name,
    quiet,
    no_logs,
    watch,
):
    """Run a flow"""
    # Define a simple function so we don't have to have a lot of `if not quiet` logic
    quiet_echo = (
        (lambda *_, **__: None)
        if quiet
        else lambda *args, **kwargs: click.secho(*args, **kwargs)
    )

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
    if "--id" in given_lookup_options and name:
        raise ClickException(
            "Received too many options to look up the flow; "
            "cannot specifiy both `--name` and `--id`" + FLOW_LOOKUP_MSG
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

        try:
            with open(param_file) as fp:
                file_params = json.load(fp)
        except FileNotFoundError:
            raise TerminalError(
                f"Parameter file does not exist: {os.path.abspath(param_file)!r}"
            )
        except ValueError as exc:
            raise TerminalError(
                f"Failed to parse JSON at {os.path.abspath(param_file)!r}: {exc}"
            )

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
        with try_error_done("Retrieving local flow...", quiet_echo, traceback=True):
            flow = get_flow_from_path_or_module(path=path, module=module, name=name)

        # Set the desired log level
        if no_logs:
            log_level = 100  # CRITICAL is 50 so this should do it

        run_info = ""
        if params_dict:
            run_info += f"└── Parameters: {params_dict}\n"
        if context_dict:
            run_info += f"└── Context: {context_dict}\n"

        if run_info:
            quiet_echo("Configured local flow run")
            quiet_echo(run_info, nl=False)

        quiet_echo("Running flow locally...")
        with temporary_logger_config(
            level=log_level,
            stream_fmt="└── %(asctime)s | %(levelname)-7s | %(message)s",
            stream_datefmt="%H:%M:%S",
        ):
            with prefect.context(**context_dict):
                try:
                    result_state = flow.run(
                        parameters=params_dict, run_on_schedule=schedule
                    )
                except Exception as exc:
                    quiet_echo("Flow runner encountered an exception!")
                    log_exception(exc, indent=2)
                    raise TerminalError("Flow run failed!")

        if result_state.is_failed():
            quiet_echo("Flow run failed!", fg="red")
            sys.exit(1)
        else:
            quiet_echo("Flow run succeeded!", fg="green")

        return

    # Backend flow run -----------------------------------------------------------------

    if schedule:
        raise ClickException("`--schedule` can only be specified for local flow runs")

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
        run_config = flow_view.run_config
        if not run_config.env:
            run_config.env = {}
        run_config.env["PREFECT__LOGGING__LEVEL"] = log_level
    else:
        run_config = None

    if execute:
        # Add a random label to prevent an agent from picking up this run
        labels.append(f"agentless-run-{str(uuid.uuid4())[:8]}")

    try:  # Handle keyboard interrupts during creation
        flow_run_id = None

        # Create a flow run in the backend
        with try_error_done(
            f"Creating run for flow {flow_view.name!r}...",
            quiet_echo,
            traceback=True,
            # Display 'Done' manually after querying for data to display so there is not
            # a lag
            skip_done=True,
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
                idempotency_key=idempotency_key,
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

    except KeyboardInterrupt:
        # If the user interrupts here, they will expect the flow run to be cancelled
        quiet_echo("\nKeyboard interrupt detected! Aborting...", fg="yellow")
        if flow_run_id:
            client.cancel_flow_run(flow_run_id=flow_run_id)
            quiet_echo("Cancelled flow run.")
        else:
            # The flow run was not created so we can just exit
            quiet_echo("Aborted.")
        return

    # Handle agentless execution
    if execute:
        quiet_echo("Executing flow run...")
        try:
            with temporary_logger_config(
                level=(
                    100 if no_logs or quiet else log_level
                ),  # Disable logging if asked
                stream_fmt="└── %(asctime)s | %(levelname)-7s | %(message)s",
                stream_datefmt="%H:%M:%S",
            ):
                execute_flow_run_in_subprocess(flow_run_id)
        except KeyboardInterrupt:
            quiet_echo("Keyboard interrupt detected! Aborting...", fg="yellow")
            pass

    elif watch:
        try:
            quiet_echo("Watching flow run execution...")
            for log in watch_flow_run(
                flow_run_id=flow_run_id,
                stream_logs=not no_logs,
            ):
                level_name = logging.getLevelName(log.level)
                timestamp = log.timestamp.in_tz(tz="local")
                echo_with_log_color(
                    log.level,
                    f"└── {timestamp:%H:%M:%S} | {level_name:<7} | {log.message}",
                )

        except KeyboardInterrupt:
            quiet_echo("Keyboard interrupt detected!", fg="yellow")
            try:
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

    else:
        # If not watching or executing, exit without checking state
        return

    # Get the final flow run state
    flow_run = FlowRunView.from_flow_run_id(flow_run_id)

    # Wait for the flow run to be done up to 3 seconds
    elapsed_time = 0
    while not flow_run.state.is_finished() and elapsed_time < 3:
        time.sleep(1)
        elapsed_time += 1
        flow_run = flow_run.get_latest()

    # Display the final state
    if flow_run.state.is_failed():
        quiet_echo("Flow run failed!", fg="red")
        sys.exit(1)
    elif flow_run.state.is_successful():
        quiet_echo("Flow run succeeded!", fg="green")
    else:
        quiet_echo(f"Flow run is in unexpected state: {flow_run.state}", fg="yellow")
        sys.exit(1)

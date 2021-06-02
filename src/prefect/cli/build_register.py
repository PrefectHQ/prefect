import functools
import hashlib
import importlib
import json
import multiprocessing
import os
import runpy
import sys
import time
import traceback
from collections import Counter, defaultdict
from types import ModuleType
from typing import Union, NamedTuple, List, Dict, Iterator, Tuple

import marshmallow
import click
import box
from click.exceptions import ClickException

import prefect
from prefect.utilities.storage import extract_flow_from_file
from prefect.utilities.filesystems import read_bytes_from_path, parse_path
from prefect.utilities.graphql import with_args, EnumValue, compress
from prefect.utilities.importtools import import_object
from prefect.storage import Local, Module
from prefect.run_configs import UniversalRun


FlowLike = Union[box.Box, "prefect.Flow"]


class SimpleFlowSchema(marshmallow.Schema):
    """A simple flow schema, only checks the `name` field"""

    class Meta:
        unknown = marshmallow.INCLUDE

    name = marshmallow.fields.Str()

    @marshmallow.post_load
    def post_load_hook(self, data, **kwargs):
        return box.Box(**data)


class FlowsJSONSchema(marshmallow.Schema):
    """Schema for a `flows.json` file"""

    version = marshmallow.fields.Integer()
    flows = marshmallow.fields.List(marshmallow.fields.Nested(SimpleFlowSchema))


class TerminalError(Exception):
    """An error indicating the CLI should exit with a non-zero exit code"""

    pass


def handle_terminal_error(func):
    """Wrap a command to handle a `TerminalError`"""

    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TerminalError as exc:
            msg = str(exc)
            if msg:
                click.secho(msg, fg="red")
            sys.exit(1)

    return inner


def log_exception(exc: Exception, indent: int = 0) -> None:
    """Log an exception with traceback"""
    prefix = " " * indent
    lines = traceback.format_exception(
        type(exc), exc, getattr(exc, "__traceback__", None)
    )
    click.echo("".join(prefix + l for l in lines))


def get_module_paths(modules: List[str]) -> List[str]:
    """Given a list of modules, return their file paths."""
    out = []
    for name in modules:
        try:
            spec = importlib.util.find_spec(name)
        except Exception as exc:
            click.secho(f"Error loading module {name}:", fg="red")
            log_exception(exc, indent=2)
            raise TerminalError
        if spec is None:
            raise TerminalError(f"No module named {name!r}")
        else:
            out.append(spec.origin)
    return out


def expand_paths(paths: List[str]) -> List[str]:
    """Given a list of paths, expand any directories to find all contained
    python files."""
    out = []
    for path in paths:
        if not os.path.exists(path):
            raise TerminalError(f"Path {path!r} doesn't exist")
        elif os.path.isdir(path):
            with os.scandir(path) as directory:
                out.extend(
                    e.path for e in directory if e.is_file() and e.path.endswith(".py")
                )
        else:
            out.append(path)
    return out


def load_flows_from_script(path: str) -> "List[prefect.Flow]":
    """Given a file path, load all flows found in the file"""
    # We use abs_path for everything but logging (logging the original
    # user-specified path provides a clearer message).
    abs_path = os.path.abspath(path)
    # Temporarily add the flow's local directory to `sys.path` so that local
    # imports work. This ensures that `sys.path` is the same as it would be if
    # the flow script was run directly (i.e. `python path/to/flow.py`).
    orig_sys_path = sys.path.copy()
    sys.path.insert(0, os.path.dirname(abs_path))
    try:
        with prefect.context({"loading_flow": True, "local_script_path": abs_path}):
            namespace = runpy.run_path(abs_path, run_name="<flow>")
    except Exception as exc:
        click.secho(f"Error loading {path!r}:", fg="red")
        log_exception(exc, 2)
        raise TerminalError
    finally:
        sys.path[:] = orig_sys_path

    flows = [f for f in namespace.values() if isinstance(f, prefect.Flow)]
    if flows:
        for f in flows:
            if f.storage is None:
                f.storage = Local(path=abs_path, stored_as_script=True)
    return flows


def load_flows_from_module(name: str) -> "List[prefect.Flow]":
    """
    Given a module name (or full import path to a flow), load all flows found in the
    module
    """
    try:
        with prefect.context({"loading_flow": True}):
            mod_or_obj = import_object(name)
    except Exception as exc:
        # If the requested module (or any parent module) isn't found, log
        # without a traceback, otherwise log a general message with the
        # traceback.
        if isinstance(exc, ModuleNotFoundError) and (
            name == exc.name
            or (name.startswith(exc.name) and name[len(exc.name)] == ".")
        ):
            raise TerminalError(str(exc))
        elif isinstance(exc, AttributeError):
            raise TerminalError(str(exc))
        else:
            click.secho(f"Error loading {name!r}:", fg="red")
            log_exception(exc, 2)
            raise TerminalError

    if isinstance(mod_or_obj, ModuleType):
        flows = [f for f in vars(mod_or_obj).values() if isinstance(f, prefect.Flow)]
    elif isinstance(mod_or_obj, prefect.Flow):
        flows = [mod_or_obj]
        # Get a valid module name for f.storage
        name, _ = name.rsplit(".", 1)
    else:
        click.secho(
            f"Invalid object of type {type(mod_or_obj).__name__!r} found at {name!r}. "
            f"Expected Module or Flow."
        )
        raise TerminalError

    if flows:
        for f in flows:
            if f.storage is None:
                f.storage = Module(name)
    return flows


def load_flows_from_json(path: str) -> "List[dict]":
    """Given a path to a JSON file containing flows, load all flows.

    Note that since `FlowSchema` doesn't roundtrip without mutation, we keep
    the flow objects as dicts.
    """
    try:
        contents = read_bytes_from_path(path)
    except FileNotFoundError:
        raise TerminalError(f"Path {path!r} doesn't exist")
    except Exception as exc:
        click.secho(f"Error loading {path!r}:", fg="red")
        log_exception(exc, indent=2)
        raise TerminalError from exc
    try:
        flows_json = FlowsJSONSchema().load(json.loads(contents))
    except Exception:
        raise TerminalError(f"{path!r} is not a valid Prefect flows `json` file.")

    if flows_json["version"] != 1:
        raise TerminalError(
            f"{path!r} is version {flows_json['version']}, only version 1 is supported"
        )

    return flows_json["flows"]


class Source(NamedTuple):
    location: str
    kind: str


def collect_flows(
    paths: List[str],
    modules: List[str],
    json_paths: List[str],
    names: List[str] = None,
    in_watch: bool = False,
) -> "Dict[Source, List[FlowLike]]":
    """Load all flows found in `paths` & `modules`.

    Args:
        - paths (List[str]): file paths to load flows from.
        - modules (List[str]): modules to load flows from.
        - json_paths (List[str]): file paths to JSON files to load flows from.
        - names (List[str], optional): a list of flow names to collect.
            If not provided, all flows found will be returned.
        - in_watch (bool): If true, any errors in loading the flows will be
            logged but won't abort execution. Default is False.
    """
    sources = [Source(p, "script") for p in paths]
    sources.extend(Source(m, "module") for m in modules)
    sources.extend(Source(m, "json") for m in json_paths)

    out = {}
    for s in sources:
        try:
            if s.kind == "module":
                flows = load_flows_from_module(s.location)
            elif s.kind == "json":
                flows = load_flows_from_json(s.location)
            else:
                flows = load_flows_from_script(s.location)
        except TerminalError:
            # If we're running with --watch, bad files are logged and skipped
            # rather than aborting early
            if not in_watch:
                raise
        out[s] = flows

    # Filter flows by name if requested
    if names:
        names = set(names)
        out = {
            source: [f for f in flows if f.name in names]
            for source, flows in out.items()
        }
        missing = names.difference(f.name for flows in out.values() for f in flows)
        if missing:
            missing_flows = "\n".join(f"- {n}" for n in sorted(missing))
            click.secho(
                f"Failed to find the following flows:\n{missing_flows}", fg="red"
            )
            if not in_watch:
                raise TerminalError

    # Drop empty sources
    out = {source: flows for source, flows in out.items() if flows}

    return out


def prepare_flows(flows: "List[FlowLike]", labels: List[str] = None) -> None:
    """Finish preparing flows.

    Shared code between `register` and `build` for any flow modifications
    required before building the flow's storage. Modifies the flows in-place.
    """
    labels = set(labels or ())

    # Finish setting up all flows before building, to ensure a stable hash
    # for flows sharing storage instances
    for flow in flows:
        if isinstance(flow, dict):
            # Add any extra labels to the flow
            if flow.get("environment"):
                new_labels = set(flow["environment"].get("labels") or []).union(labels)
                flow["environment"]["labels"] = sorted(new_labels)
            else:
                new_labels = set(flow["run_config"].get("labels") or []).union(labels)
                flow["run_config"]["labels"] = sorted(new_labels)
        else:
            # Set the default flow result if not specified
            if not flow.result:
                flow.result = flow.storage.result

            # Add a `run_config` if not configured explicitly
            if flow.run_config is None and flow.environment is None:
                flow.run_config = UniversalRun()
            # Add any extra labels to the flow (either specified via the CLI,
            # or from the storage object).
            obj = flow.run_config or flow.environment
            obj.labels.update(labels)
            obj.labels.update(flow.storage.labels)

            # Add the flow to storage
            flow.storage.add_flow(flow)


def get_project_id(client: "prefect.Client", project: str) -> str:
    """Get a project id given a project name.

    Args:
        - project (str): the project name

    Returns:
        - str: the project id
    """
    resp = client.graphql(
        {"query": {with_args("project", {"where": {"name": {"_eq": project}}}): {"id"}}}
    )
    if resp.data.project:
        return resp.data.project[0].id
    else:
        raise TerminalError(f"Project {project!r} does not exist")


def register_serialized_flow(
    client: "prefect.Client",
    serialized_flow: dict,
    project_id: str,
    force: bool = False,
) -> Tuple[str, int, bool]:
    """Register a pre-serialized flow.

    Args:
        - client (prefect.Client): the prefect client
        - serialized_flow (dict): the serialized flow
        - project_id (str): the project id
        - force (bool, optional): If `False` (default), an idempotency key will
            be generated to avoid unnecessary re-registration. Set to `True` to
            force re-registration.

    Returns:
        - flow_id (str): the flow id
        - flow_version (int): the flow version
        - is_new (bool): True if this is a new flow version, false if
            re-registration was skipped.
    """
    # Get most recent flow id for this flow. This can be removed once
    # the registration graphql routes return more information
    flow_name = serialized_flow["name"]
    resp = client.graphql(
        {
            "query": {
                with_args(
                    "flow",
                    {
                        "where": {
                            "_and": {
                                "name": {"_eq": flow_name},
                                "project": {"id": {"_eq": project_id}},
                            }
                        },
                        "order_by": {"version": EnumValue("desc")},
                        "limit": 1,
                    },
                ): {"id", "version"}
            }
        }
    )
    if resp.data.flow:
        prev_id = resp.data.flow[0].id
        prev_version = resp.data.flow[0].version
    else:
        prev_id = None
        prev_version = 0

    inputs = dict(
        project_id=project_id,
        serialized_flow=compress(serialized_flow),
    )
    if not force:
        inputs["idempotency_key"] = hashlib.sha256(
            json.dumps(serialized_flow, sort_keys=True).encode()
        ).hexdigest()

    res = client.graphql(
        {
            "mutation($input: create_flow_from_compressed_string_input!)": {
                "create_flow_from_compressed_string(input: $input)": {"id"}
            }
        },
        variables=dict(input=inputs),
        retry_on_api_error=False,
    )

    new_id = res.data.create_flow_from_compressed_string.id

    if new_id == prev_id:
        return new_id, prev_version, False
    else:
        return new_id, prev_version + 1, True


def build_and_register(
    client: "prefect.Client",
    flows: "List[FlowLike]",
    project_id: str,
    labels: List[str] = None,
    force: bool = False,
) -> Counter:
    """Build and register all flows.

    Args:
        - client (prefect.Client): the prefect client to use
        - flows (List[FlowLike]): the flows to register
        - project_id (str): the project id in which to register the flows
        - labels (List[str], optional): Any extra labels to set on all flows
        - force (bool, optional): If false (default), an idempotency key will
            be used to avoid unnecessary register calls.

    Returns:
        - Counter: stats about the number of successful, failed, and skipped flows.
    """
    # Finish preparing flows to ensure a stable hash later
    prepare_flows(flows, labels)

    # Group flows by storage instance.
    storage_to_flows = defaultdict(list)
    for flow in flows:
        storage = flow.storage if isinstance(flow, prefect.Flow) else None
        storage_to_flows[storage].append(flow)

    # Register each flow, building storage as needed.
    # Stats on success/fail/skip rates are kept for later display
    stats = Counter(registered=0, errored=0, skipped=0)
    for storage, flows in storage_to_flows.items():
        # Build storage if needed
        if storage is not None:
            click.echo(f"  Building `{type(storage).__name__}` storage...")
            try:
                storage.build()
            except Exception as exc:
                click.secho("    Error building storage:", fg="red")
                log_exception(exc, indent=6)
                red_error = click.style("Error", fg="red")
                for flow in flows:
                    click.echo(f"  Registering {flow.name!r}... {red_error}")
                    stats["errored"] += 1
                continue

        for flow in flows:
            click.echo(f"  Registering {flow.name!r}...", nl=False)
            try:
                if isinstance(flow, box.Box):
                    serialized_flow = flow
                else:
                    serialized_flow = flow.serialize(build=False)

                flow_id, flow_version, is_new = register_serialized_flow(
                    client=client,
                    serialized_flow=serialized_flow,
                    project_id=project_id,
                    force=force,
                )
            except Exception as exc:
                click.secho(" Error", fg="red")
                log_exception(exc, indent=4)
                stats["errored"] += 1
            else:
                if is_new:
                    click.secho(" Done", fg="green")
                    click.echo(f"  └── ID: {flow_id}")
                    click.echo(f"  └── Version: {flow_version}")
                    stats["registered"] += 1
                else:
                    click.secho(" Skipped (metadata unchanged)", fg="yellow")
                    stats["skipped"] += 1
    return stats


def register_internal(
    project: str,
    paths: List[str],
    modules: List[str],
    json_paths: List[str] = None,
    names: List[str] = None,
    labels: List[str] = None,
    force: bool = False,
    in_watch: bool = False,
) -> None:
    """Do a single registration pass, loading, building, and registering the
    requested flows.

    Args:
        - project (str): the project in which to register the flows.
        - paths (List[str]): a list of file paths containing flows.
        - modules (List[str]): a list of python modules containing flows.
        - json_paths (List[str]): a list of file paths containing serialied
            flows produced by `prefect build`.
        - names (List[str], optional): a list of flow names that should be
            registered. If not provided, all flows found will be registered.
        - labels (List[str], optional): a list of extra labels to set on all
            flows.
        - force (bool, optional): If false (default), an idempotency key will
            be used to avoid unnecessary register calls.
        - in_watch (bool, optional): Whether this call resulted from a
            `register --watch` call.
    """
    client = prefect.Client()

    # Determine the project id
    project_id = get_project_id(client, project)

    # Load flows from all files/modules requested
    click.echo("Collecting flows...")
    source_to_flows = collect_flows(
        paths, modules, json_paths, names=names, in_watch=in_watch
    )

    # Iterate through each file, building all storage and registering all flows
    # Log errors as they happen, but only exit once all files have been processed
    stats = Counter(registered=0, errored=0, skipped=0)
    for source, flows in source_to_flows.items():
        click.echo(f"Processing {source.location!r}:")
        stats += build_and_register(
            client, flows, project_id, labels=labels, force=force
        )

    # Output summary message
    registered = stats["registered"]
    skipped = stats["skipped"]
    errored = stats["errored"]
    parts = [click.style(f"{registered} registered", fg="green")]
    if skipped:
        parts.append(click.style(f"{skipped} skipped", fg="yellow"))
    if errored:
        parts.append(click.style(f"{errored} errored", fg="red"))

    msg = ", ".join(parts)
    bar_length = max(60 - len(click.unstyle(msg)), 4) // 2
    bar = "=" * bar_length
    click.echo(f"{bar} {msg} {bar}")

    # If not in a watch call, exit with appropriate exit code
    if not in_watch and stats["errored"]:
        raise TerminalError


def watch_for_changes(
    paths: List[str] = None,
    modules: List[str] = None,
    period: float = 0.5,
) -> "Iterator[Tuple[List[str], List[str]]]":
    """Watch a list of paths and modules for changes.

    Yields tuples of `(paths, modules)` whenever changes are detected, where
    `paths` is a list of paths that changed and `modules` is a list of modules
    that changed.
    """
    paths = list(paths or ())
    modules = list(modules or ())

    for path in paths:
        if not os.path.exists(path):
            raise TerminalError(f"Path {path!r} doesn't exist")

    if modules:
        # If modules are provided, we need to convert these to paths to watch.
        # There's no way in Python to do this without possibly importing the
        # defining module. As such, we run the command in a temporary process
        # pool.
        with multiprocessing.get_context("spawn").Pool(1) as pool:
            module_paths = pool.apply(get_module_paths, (modules,))
            path_to_module = dict(zip(module_paths, modules))
    else:
        path_to_module = {}

    tracked = paths + list(path_to_module)
    cache = dict.fromkeys(path_to_module)
    while True:
        cache2 = {}
        for path in tracked:
            try:
                try:
                    with os.scandir(path) as directory:
                        for entry in directory:
                            if entry.is_file() and entry.path.endswith(".py"):
                                old_mtime = cache.get(entry.path)
                                mtime = entry.stat().st_mtime
                                if mtime != old_mtime:
                                    cache2[entry.path] = mtime
                except NotADirectoryError:
                    old_mtime = cache.get(path)
                    mtime = os.stat(path).st_mtime
                    if mtime != old_mtime:
                        cache2[path] = mtime
            except FileNotFoundError:
                cache.pop(path, None)

        if cache2:
            change_paths = []
            change_mods = []
            for path in cache2:
                module = path_to_module.get(path)
                if module is not None:
                    change_mods.append(module)
                else:
                    change_paths.append(path)
            if change_paths or change_mods:
                yield change_paths, change_mods
                cache.update(cache2)

        time.sleep(period)


REGISTER_EPILOG = """
\bExamples:

\b  Register all flows found in a directory.

\b    $ prefect register --project my-project -p myflows/

\b  Register a flow named "example" found in `flow.py`.

\b    $ prefect register --project my-project -p flow.py -n "example"

\b  Register all flows found in a module named `myproject.flows`.

\b    $ prefect register --project my-project -m "myproject.flows"

\b  Register a flow in variable `flow_x` in a module `myproject.flows`.

\b    $ prefect register --project my-project -m "myproject.flows.flow_x"

\b  Register all pre-built flows from a remote JSON file.

\b    $ prefect register --project my-project --json https://some-url/flows.json

\b  Watch a directory of flows for changes, and re-register flows upon change.

\b    $ prefect register --project my-project -p myflows/ --watch
"""


@click.group(invoke_without_command=True, epilog=REGISTER_EPILOG)
@click.option(
    "--project",
    help="The name of the Prefect project to register this flow in. Required.",
    default=None,
)
@click.option(
    "--path",
    "-p",
    "paths",
    help=(
        "A path to a file or a directory containing the flow(s) to register. "
        "May be passed multiple times to specify multiple paths."
    ),
    multiple=True,
)
@click.option(
    "--module",
    "-m",
    "modules",
    help=(
        "A python module name containing the flow(s) to register. May be the full "
        "import path to a flow. May be passed multiple times to specify multiple "
        "modules. "
    ),
    multiple=True,
)
@click.option(
    "--json",
    "-j",
    "json_paths",
    help=(
        "A path or URL to a JSON file created by `prefect build` containing the flow(s) "
        "to register. May be passed multiple times to specify multiple paths. "
        "Note that this path may be a remote url (e.g. https://some-url/flows.json)."
    ),
    multiple=True,
)
@click.option(
    "--name",
    "-n",
    "names",
    help=(
        "The name of a flow to register from the specified paths/modules. If "
        "provided, only flows with a matching name will be registered. May be "
        "passed multiple times to specify multiple flows. If not provided, all "
        "flows found on all paths/modules will be registered."
    ),
    multiple=True,
)
@click.option(
    "--label",
    "-l",
    "labels",
    help=(
        "A label to add on all registered flow(s). May be passed multiple "
        "times to specify multiple labels."
    ),
    multiple=True,
)
@click.option(
    "--force",
    "-f",
    help="Force flow registration, even if the flow's metadata is unchanged.",
    default=False,
    is_flag=True,
)
@click.option(
    "--watch",
    help=(
        "If set, the specified paths and modules will be monitored and "
        "registration re-run upon changes."
    ),
    default=False,
    is_flag=True,
)
@click.pass_context
@handle_terminal_error
def register(ctx, project, paths, modules, json_paths, names, labels, force, watch):
    """Register one or more flows into a project.

    Flows with unchanged metadata will be skipped as registering again will only
    change the version number.
    """
    # Since the old command was a subcommand of this, we have to do some
    # mucking to smoothly deprecate it. Can be removed with `prefect register
    # flow` is removed.
    if ctx.invoked_subcommand is not None:
        if any([project, paths, modules, names, labels, force]):
            raise ClickException(
                "Got unexpected extra argument (%s)" % ctx.invoked_subcommand
            )
        return

    if project is None:
        raise ClickException("Missing required option '--project'")

    if watch:
        if any(parse_path(j).scheme != "file" for j in json_paths):
            raise ClickException("--watch is not supported for remote paths")
        json_paths = set(json_paths)

        ctx = multiprocessing.get_context("spawn")

        for change_paths_temp, change_mods in watch_for_changes(
            paths=paths, modules=modules
        ):
            change_paths = []
            change_json_paths = []
            for p in change_paths_temp:
                if p in json_paths:
                    change_json_paths.append(p)
                else:
                    change_paths.append(p)
            proc = ctx.Process(
                target=register_internal,
                name="prefect-register",
                args=(project,),
                kwargs=dict(
                    paths=change_paths,
                    modules=change_mods,
                    json_paths=change_json_paths,
                    names=names,
                    labels=labels,
                    force=force,
                    in_watch=True,
                ),
                daemon=True,
            )
            proc.start()
            proc.join()
    else:
        paths = expand_paths(list(paths or ()))
        modules = list(modules or ())
        register_internal(project, paths, modules, json_paths, names, labels, force)


BUILD_EPILOG = """
\bExamples:

\b  Build all flows found in a directory.

\b    $ prefect build -p myflows/

\b  Build a flow named "example" found in `flow.py`.

\b    $ prefect build -p flow.py -n "example"

\b  Build all flows found in a module named `myproject.flows`.

\b    $ prefect build -m "myproject.flows"
"""


@click.command(epilog=BUILD_EPILOG)
@click.option(
    "--path",
    "-p",
    "paths",
    help=(
        "A path to a file or a directory containing the flow(s) to build. "
        "May be passed multiple times to specify multiple paths."
    ),
    multiple=True,
)
@click.option(
    "--module",
    "-m",
    "modules",
    help=(
        "A python module name containing the flow(s) to build. May be "
        "passed multiple times to specify multiple modules."
    ),
    multiple=True,
)
@click.option(
    "--name",
    "-n",
    "names",
    help=(
        "The name of a flow to build from the specified paths/modules. If "
        "provided, only flows with a matching name will be built. May be "
        "passed multiple times to specify multiple flows. If not provided, "
        "all flows found on all paths/modules will be built."
    ),
    multiple=True,
)
@click.option(
    "--label",
    "-l",
    "labels",
    help=(
        "A label to add on all built flow(s). May be passed multiple "
        "times to specify multiple labels."
    ),
    multiple=True,
)
@click.option(
    "--output",
    "-o",
    default="flows.json",
    help="The output path. Defaults to `flows.json`.",
)
@click.option(
    "--update",
    "-u",
    is_flag=True,
    default=False,
    help="Updates an existing `json` file rather than overwriting it.",
)
@handle_terminal_error
def build(paths, modules, names, labels, output, update):
    """Build one or more flows.

    This command builds all specified flows and writes their metadata to a JSON
    file. These flows can then be registered without building later by passing
    the `--json` flag to `prefect register`.
    """
    succeeded = 0
    errored = 0

    # If updating, load all previously written flows first
    if update and os.path.exists(output):
        serialized_flows = {f["name"]: f for f in load_flows_from_json(output)}
    else:
        serialized_flows = {}

    # Collect flows from specified paths & modules
    paths = expand_paths(list(paths or ()))
    modules = list(modules or ())
    click.echo("Collecting flows...")
    source_to_flows = collect_flows(paths, modules, [], names=names)

    for source, flows in source_to_flows.items():
        click.echo(f"Processing {source.location!r}:")

        # Finish preparing flows to ensure a stable hash later
        prepare_flows(flows, labels)

        # Group flows by storage instance.
        storage_to_flows = defaultdict(list)
        for flow in flows:
            storage_to_flows[flow.storage].append(flow)

        for storage, flows in storage_to_flows.items():
            # Build storage
            click.echo(f"  Building `{type(storage).__name__}` storage...")
            try:
                storage.build()
            except Exception as exc:
                click.secho("    Error building storage:", fg="red")
                log_exception(exc, indent=6)
                red_error = click.style("Error", fg="red")
                for flow in flows:
                    click.echo(f"  Building {flow.name!r}... {red_error}")
                    errored += 1
                continue

            # Serialize flows
            for flow in flows:
                click.echo(f"  Building {flow.name!r}...", nl=False)
                try:
                    serialized_flows[flow.name] = flow.serialize(build=False)
                except Exception as exc:
                    click.secho(" Error", fg="red")
                    log_exception(exc, indent=4)
                    errored += 1
                else:
                    click.secho(" Done", fg="green")
                    succeeded += 1

    # Write output file
    click.echo(f"Writing output to {output!r}")
    flows = [serialized_flows[name] for name in sorted(serialized_flows)]
    obj = {"version": 1, "flows": flows}
    with open(output, "w") as fil:
        json.dump(obj, fil, sort_keys=True)

    # Output summary message
    parts = [click.style(f"{succeeded} built", fg="green")]
    if errored:
        parts.append(click.style(f"{errored} errored", fg="red"))

    msg = ", ".join(parts)
    bar_length = max(60 - len(click.unstyle(msg)), 4) // 2
    bar = "=" * bar_length
    click.echo(f"{bar} {msg} {bar}")

    # Exit with appropriate status code
    if errored:
        raise TerminalError


@register.command(hidden=True)
@click.option(
    "--file",
    "-f",
    required=True,
    help="A file that contains a flow",
    hidden=True,
    default=None,
    type=click.Path(exists=True),
)
@click.option(
    "--name",
    "-n",
    required=False,
    help="The `flow.name` to pull out of the file provided",
    hidden=True,
    default=None,
)
@click.option(
    "--project",
    "-p",
    required=False,
    help="The name of a Prefect project to register this flow",
    hidden=True,
    default=None,
)
@click.option(
    "--label",
    "-l",
    required=False,
    help="A label to set on the flow, extending any existing labels.",
    hidden=True,
    multiple=True,
)
@click.option(
    "--skip-if-flow-metadata-unchanged",
    is_flag=True,
    help="Skips registration if flow metadata is unchanged",
    hidden=True,
)
def flow(file, name, project, label, skip_if_flow_metadata_unchanged):
    """Register a flow (DEPRECATED)"""
    # Deprecated in 0.14.13
    click.secho(
        (
            "Warning: `prefect register flow` is deprecated, please transition to "
            "using `prefect register` instead."
        ),
        fg="yellow",
    )
    # Don't run extra `run` and `register` functions inside file
    file_path = os.path.abspath(file)
    with prefect.context({"loading_flow": True, "local_script_path": file_path}):
        flow = extract_flow_from_file(file_path=file_path, flow_name=name)

    idempotency_key = (
        flow.serialized_hash() if skip_if_flow_metadata_unchanged else None
    )

    flow.register(project_name=project, labels=label, idempotency_key=idempotency_key)

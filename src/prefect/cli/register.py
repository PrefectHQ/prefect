import os
import importlib
import multiprocessing
import sys
import time
import traceback
from typing import NamedTuple

import click
from click.exceptions import ClickException

import prefect
from prefect.utilities.storage import extract_flow_from_file


class Source(NamedTuple):
    location: str
    is_module: bool = False


def get_module_paths(modules):
    out = []
    for name in modules:
        try:
            spec = importlib.util.find_spec(name)
        except Exception as exc:
            click.secho(f"Error loading module {name}:", fg="yellow")
            log_exception(exc, indent=2)
            return None
        if spec is None:
            click.secho(f"No module named {name!r}", fg="yellow")
            return None
        else:
            out.append(spec.origin)


def expand_paths(paths):
    paths = list(paths)
    out = []
    for path in paths:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            click.secho(f"Path {path!r} doesn't exist", fg="yellow")
            sys.exit(1)
        elif os.path.isdir(path):
            with os.scandir(path) as directory:
                out.extend(
                    e.path for e in directory if e.is_file() and e.path.endswith(".py")
                )
        else:
            out.append(path)
    return out


def load_flows_from_path(path):
    from prefect.storage import Local

    with open(path, "rb") as fil:
        contents = fil.read()

    ns = {}
    try:
        with prefect.context({"loading_flow": True, "local_script_path": path}):
            exec(contents, ns)
    except Exception as exc:
        click.secho(f"Error loading {path!r}:", fg="yellow")
        log_exception(exc, 2)
        return None

    flows = [f for f in ns.values() if isinstance(f, prefect.Flow)]
    if flows:
        storage = Local(path=path, stored_as_script=True)
        for f in flows:
            if f.storage is None:
                f.storage = storage
    return flows


def load_flows_from_module(name):
    from prefect.storage import Module

    try:
        with prefect.context({"loading_flow": True}):
            mod = importlib.import_module(name)
    except Exception as exc:
        if isinstance(exc, ImportError) and repr(name) in str(exc):
            click.secho(str(exc), fg="yellow")
        else:
            click.secho(f"Error loading {name!r}:", fg="yellow")
            log_exception(exc, 2)
        return None

    flows = [f for f in vars(mod).values() if isinstance(f, prefect.Flow)]
    if flows:
        storage = Module(name)
        for f in flows:
            if f.storage is None:
                f.storage = storage
    return flows


def collect_flows(paths, modules, in_watch=False):
    sources = [Source(p, False) for p in paths]
    sources.extend(Source(m, True) for m in modules)

    out = {}
    for s in sources:
        if s.is_module:
            flows = load_flows_from_module(s.location)
        else:
            flows = load_flows_from_path(s.location)
        if flows is None:
            if not in_watch:
                sys.exit(1)
        else:
            out[s] = flows
    return out


def log_exception(exc, indent=0):
    prefix = " " * indent
    lines = traceback.format_exception(
        type(exc), exc, getattr(exc, "__traceback__", None)
    )
    click.echo("\n".join(prefix + l for l in lines))


def add_labels(flows, labels=None):
    from prefect.run_configs import UniversalRun

    labels = set(labels or ())

    for flow in flows:
        if flow.run_config is None:
            if flow.environment is not None:
                flow.environment.labels.update(labels)
            else:
                flow.run_config = UniversalRun(labels=labels)
        else:
            flow.run_config.labels.update(labels)


def build_storage(flows):
    for flow in flows:
        flow.storage.add_flow(flow)
    built = set()
    for flow in flows:
        if flow.storage not in built:
            click.echo(
                f"  Building `{type(flow.storage).__name__}` storage...", nl=False
            )
            try:
                flow.storage.build()
                built.add(flow.storage)
            except Exception as exc:
                click.secho(" Error", fg="red")
                log_exception(exc, indent=4)
                return False
            else:
                click.secho(" Done", fg="green")
    return True


def register_flows(flows, project, force=False):
    for flow in flows:
        click.echo(f"  Registering {flow.name!r}...", nl=False)
        try:
            flow.register(
                project_name=project,
                build=False,
                no_url=True,
                idempotency_key=(None if force else flow.serialized_hash()),
            )
        except Exception as exc:
            click.secho(" Error", fg="red")
            log_exception(exc, indent=4)
            return False
        else:
            click.secho(" Done", fg="green")
    return True


def register_flows_once(
    project,
    paths=None,
    modules=None,
    names=None,
    labels=None,
    force=False,
    in_watch=False,
):
    click.echo("Collecting flows...")
    source_to_flows = collect_flows(paths, modules, in_watch)

    # Filter flows by name if requested
    if names:
        source_to_flows = {
            source: [f for f in flows if f.name in names]
            for source, flows in source_to_flows.items()
        }
        missing = names.difference(
            f.name for flows in source_to_flows.values() for f in flows
        )
        if missing:
            missing_flows = "\n".join(f"- {n}" for n in sorted(missing))
            click.secho(
                f"Failed to find the following flows:\n{missing_flows}", fg="yellow"
            )
            if not in_watch:
                sys.exit(1)

    # Iterate through each file, building all storage and registering all flows
    # Log errors as they happen, but only exit once all files have been processed
    ok = True
    for source, flows in source_to_flows.items():
        if flows:
            click.echo(f"Processing {source.location!r}:")

            add_labels(flows, labels)

            if not build_storage(flows):
                ok = False
                continue

            if not register_flows(flows, project, force=True):
                ok = False
                continue

    if not in_watch and not ok:
        sys.exit(1)


def register_flows_watch(
    project,
    paths=None,
    modules=None,
    names=None,
    labels=None,
    force=False,
):
    paths = list(paths or ())
    modules = list(modules or ())

    for path in paths:
        if not os.path.exists(path):
            click.secho(f"Path {path!r} doesn't exist", fg="yellow")
            sys.exit(1)

    ctx = multiprocessing.get_context("spawn")

    if modules:
        # If modules are provided, we need to convert these to paths to watch.
        # There's no way in Python to do this without possibly importing the
        # defining module. As such, we run the command in a temporary process
        # pool.
        with ctx.Pool(1) as pool:
            module_paths = pool.apply(get_module_paths, (modules,))
            if module_paths is None:
                sys.exit(1)
    else:
        module_paths = []

    tracked = paths + module_paths
    cache = {p: (m, None) for p, m in zip(module_paths, modules)}
    while True:
        cache2 = {}
        for path in tracked:
            try:
                try:
                    with os.scandir(path) as directory:
                        for entry in directory:
                            if entry.is_file() and entry.path.endswith(".py"):
                                module, old_mtime = cache.get(entry.path, (None, None))
                                mtime = entry.stat().st_mtime
                                if mtime != old_mtime:
                                    cache2[entry.path] = (module, mtime)
                except NotADirectoryError:
                    module, old_mtime = cache.get(path, (None, None))
                    mtime = os.stat(path).st_mtime
                    if mtime != old_mtime:
                        cache2[path] = (module, mtime)
            except FileNotFoundError:
                cache.pop(path)

        if cache2:
            change_paths = []
            change_mods = []
            for p, (m, _) in cache2.items():
                if m is None:
                    change_paths.append(p)
                else:
                    change_mods.append(m)

            if change_paths or change_mods:
                proc = ctx.Process(
                    target=register_flows_once,
                    name="prefect-register",
                    args=(project,),
                    kwargs=dict(
                        paths=change_paths,
                        modules=change_mods,
                        names=names,
                        labels=labels,
                        force=force,
                        in_watch=True,
                    ),
                    daemon=True,
                )
                proc.start()
                proc.join()
                cache.update(cache2)

        time.sleep(0.5)


@click.group(invoke_without_command=True)
@click.option(
    "--project",
    help="The name of the Prefect project to register this flow in. Required.",
    default=None,
    hidden=True,
)
@click.option(
    "--path",
    "-p",
    "paths",
    help=(
        "A path to a file or a directory containing the flow(s) to register. "
        "May be passed multiple times to specify multiple paths to register."
    ),
    default=None,
    multiple=True,
)
@click.option(
    "--module",
    "-m",
    "modules",
    help=(
        "A python module name containing the flow(s) to register. May be "
        "passed multiple times to specify multiple modules to register."
    ),
    default=None,
    multiple=True,
)
@click.option(
    "--name",
    "-n",
    "names",
    help=(
        "The name of a flow to register from the specified paths/modules. If "
        "provided, only flows with a matching name will be registered. May be "
        "passed multiple times to specify multiple flows to register. If not "
        "provided, all flows found on all paths/modules will be registered."
    ),
    default=None,
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
    default=None,
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
def register(ctx, project, paths, modules, names, labels, force, watch):
    """Register one or more flows into a project"""
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

    paths = list(paths or ())
    modules = list(modules or ())
    names = set(names or ())

    if watch:
        register_flows_watch(project, paths, modules, names, labels, force)
    else:
        paths = expand_paths(paths)
        register_flows_once(project, paths, modules, names, labels, force)


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

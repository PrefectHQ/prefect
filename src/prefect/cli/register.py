import os
import importlib
import sys
from typing import NamedTuple

import click
from click.exceptions import ClickException

import prefect
from prefect.utilities.storage import extract_flow_from_file


class Source(NamedTuple):
    location: str
    is_module: bool = False


def collect_flows_from_paths(paths):
    from prefect.storage import Local

    paths = list(paths)
    files = []
    flows = {}
    for path in paths:
        if not os.path.exists(path):
            raise ValueError(f"Path {path!r} doesn't exist")
        elif os.path.isdir(path):
            with os.scandir(path) as directory:
                files.extend(
                    e.path for e in directory if e.is_file() and e.path.endswith(".py")
                )
        else:
            files.append(path)

    for path in files:
        with open(path, "rb") as fil:
            contents = fil.read()

        ns = {}
        with prefect.context(
            {"loading_flow": True, "local_script_path": os.path.abspath(path)}
        ):
            exec(contents, ns)

        new_flows = [f for f in ns.values() if isinstance(f, prefect.Flow)]
        if new_flows:
            storage = Local(path=os.path.abspath(path), stored_as_script=True)
            for f in new_flows:
                if f.storage is None:
                    f.storage = storage
        flows[Source(path)] = new_flows

    return flows


def collect_flows_from_modules(modules):
    from prefect.storage import Module

    flows = {}
    for name in modules:
        with prefect.context({"loading_flow": True}):
            mod = importlib.import_module(name)
        new_flows = [f for f in vars(mod).values() if isinstance(f, prefect.Flow)]
        if new_flows:
            storage = Module(name)
            for f in new_flows:
                if f.storage is None:
                    f.storage = storage
        flows[Source(name, True)] = new_flows
    return flows


def register_flows(
    project, paths=None, modules=None, names=None, labels=None, force=False
):
    from prefect.run_configs import UniversalRun

    names = set(names or ())

    click.echo("Collecting flows...")
    source_to_flows = {}
    if paths:
        source_to_flows.update(collect_flows_from_paths(paths))
    if modules:
        source_to_flows.update(collect_flows_from_modules(modules))

    # Ensure names are all unique
    seen = set()
    for flows in source_to_flows.values():
        for flow in flows:
            if flow.name in seen:
                click.secho(
                    f"Error: Multiple flows named {flow.name} found", fg="yellow"
                )
                sys.exit(1)
            seen.add(flow.name)

    if names:
        # Filter by name
        source_to_flows = {
            source: [f for f in flows if f.name in names]
            for source, flows in source_to_flows.items()
        }
        missing = names.difference(
            f.name for flows in source_to_flows.values() for f in flows
        )
        if missing:
            missing_flows = "\n".join(f"- {n}" for n in sorted(missing))
            click.secho(f"Failed to find the following flows:\n{missing_flows}")
            sys.exit(1)

    n_flows = sum(map(len, source_to_flows.values()))
    click.echo(f"Found {n_flows} flows to register")

    for source, flows in source_to_flows.items():
        if not flows:
            continue

        click.echo(f"Processing {source.location!r}:")

        for flow in flows:
            # Add labels and add flow to storage
            if flow.run_config is None:
                if flow.environment is not None:
                    flow.environment.labels.update(labels)
                else:
                    flow.run_config = UniversalRun(labels=labels)
            else:
                flow.run_config.labels.update(labels)

            flow.storage.add_flow(flow)

        built = set()
        for flow in flows:
            if flow.storage not in built:
                click.echo(
                    f"  Building `{type(flow.storage).__name__}` storage...", nl=False
                )
                flow.storage.build()
                built.add(flow.storage)
                click.secho(" Done", fg="green")
            click.echo(f"  Registering {flow.name!r}...", nl=False)
            flow.register(
                project_name=project,
                build=False,
                no_url=True,
                idempotency_key=(None if force else flow.serialized_hash()),
            )
            click.secho(" Done", fg="green")


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
@click.pass_context
def register(ctx, project, paths, modules, names, labels, force):
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

    register_flows(project, paths, modules, names, labels, force)


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
        err=True,
    )
    # Don't run extra `run` and `register` functions inside file
    file_path = os.path.abspath(file)
    with prefect.context({"loading_flow": True, "local_script_path": file_path}):
        flow = extract_flow_from_file(file_path=file_path, flow_name=name)

    idempotency_key = (
        flow.serialized_hash() if skip_if_flow_metadata_unchanged else None
    )

    flow.register(project_name=project, labels=label, idempotency_key=idempotency_key)

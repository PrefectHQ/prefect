import os

import click
from click.exceptions import ClickException

import prefect
from prefect.utilities.storage import extract_flow_from_file


def register_flows(
    project, paths=None, modules=None, names=None, labels=None, force=False
):
    # TODO
    pass


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

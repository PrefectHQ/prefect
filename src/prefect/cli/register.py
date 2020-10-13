import os

import click

import prefect
from prefect.utilities.storage import extract_flow_from_file


@click.group(hidden=True)
def register():
    """
    Register flows

    \b
    Usage:
        $ prefect register [OBJECT]

    \b
    Arguments:
        flow    Register flows with a backend API

    \b
    Examples:
        $ prefect register flow --file my_flow.py --name My-Flow
    """


@register.command(
    hidden=True,
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
)
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
    help="The `flow.name` to pull out of the file provided.",
    hidden=True,
    default=None,
)
@click.option(
    "--project",
    "-p",
    required=False,
    help="The name of a Prefect project to register this flow.",
    hidden=True,
    default=None,
)
@click.option(
    "--label",
    "-l",
    required=False,
    hidden=True,
    multiple=True,
)
def flow(file, name, project, label):
    """
    Register a flow from a file. This call will pull a Flow object out of a `.py` file
    and call `flow.register` on it.

    \b
    Options:
        --file, -f      TEXT    The path to a local file which contains a flow  [required]
        --name, -n      TEXT    The `flow.name` to pull out of the file provided. If a name
                                is not provided then the first flow object found will be registered.
        --project, -p   TEXT    The name of a Prefect project to register this flow
        --label, -l     TEXT    A label to set on the flow, extending any existing labels.
                                Multiple labels are supported, eg. `-l label1 -l label2`.

    \b
    Examples:
        $ prefect register flow --file my_flow.py --name My-Flow -l label1 -l label2
    """

    # Don't run extra `run` and `register` functions inside file
    file_path = os.path.abspath(file)
    with prefect.context({"loading_flow": True, "local_script_path": file_path}):
        flow = extract_flow_from_file(file_path=file_path, flow_name=name)

    if getattr(flow, "run_config", None) is not None:
        flow.run_config.labels.update(label)
    else:
        flow.environment.labels.update(label)

    flow.register(project_name=project)

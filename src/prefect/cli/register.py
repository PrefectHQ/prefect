import os

import click

import prefect
from prefect.utilities.storage import extract_flow_from_file

@click.group(hidden=True)
def register():
    """
    Register flows
    """


@register.command(
    hidden=True,
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
)
@click.option(
    "--file",
    "-f",
    required=False,
    help="A file that contains a flow",
    hidden=True,
    default=None,
    type=click.Path(exists=True)
)
def flow(file):
    """
    Register a flow
    """

    file_path = os.path.abspath(file)
    flow_obj = extract_flow_from_file(file_path=file_path)

    # Allow a path to be set here
    # Maybe we can overload the add_flow to take both flow and flow.name
    # OR keep passing in the flow object and then pull the name off of it in there
    # which is probably the best option
    flow_obj.storage.add_flow(flow_name=flow_obj.name)

    # Replace with register
    # Should have a build option here
    flow_obj.register()

    # print("Registered!")
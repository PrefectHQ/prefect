import os

import click

import prefect

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

    # Grab contents of file
    with open(file_path, "r") as f:
        contents = f.read()

    # Exec the file to get the flow name
    # when giving dict to exec, contents are not run with main
    exec_vals = {}
    exec(contents, exec_vals)

    # Grab flow name from values loaded via exec
    # This will only work with one flow per file, could add name option
    for i in exec_vals:
        if isinstance(exec_vals[i], prefect.Flow):
            flow_name = exec_vals[i].name
            flow = exec_vals[i]
            break


    # print(flow.storage.flows)
    # return
    # Add to storage (will replace with add_flow)
    # Temp until Local is updated to move write to build
    # flow.storage.flows[flow_name] = file_path
    # flow.storage._flows[flow_name] = flow
    flow.storage.add_flow(file=file, file_path=file_path)

    # Replace with register
    flow.storage.build()
    # flow.serialize(build=True)

    print("Registered!")
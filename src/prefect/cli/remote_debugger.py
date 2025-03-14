from uuid import UUID

import typer

from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.debugger import PDBInput, PDBResponse

remote_debugger_app: PrefectTyper = PrefectTyper(
    name="remote-debugger", help="Remotely debug running flows."
)
app.add_typer(remote_debugger_app, aliases=["remote-debugger"])


@remote_debugger_app.command()
async def debug(
    flow_run_id: UUID = typer.Argument(
        ...,
        help="The ID of the flow run to debug.",
    ),
):
    """
    Debug a running flow.
    """

    print("Waiting for remote debugger to start...")

    receiver = PDBResponse.receive(
        flow_run_id=flow_run_id,
        poll_interval=1.0,
        key_prefix="prefect-remote-debugger-response",
    )
    response = await receiver.next()

    print(response.response)

    while True:
        command = input("(Pdb) ")
        await PDBInput(command=command).send_to(
            flow_run_id, key_prefix="prefect-remote-debugger-command"
        )
        response = await receiver.next()
        print(response.response)

        if command in ("q", "quit", "exit"):
            break

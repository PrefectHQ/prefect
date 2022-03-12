import time

import click

import prefect
from prefect import config
from prefect.client import Client
from prefect.utilities.logging import get_logger


@click.group(hidden=True)
def heartbeat():
    """
    Send heartbeats back to the Prefect API.

    \b
    Usage:
        $ prefect heartbeat [task-run/flow-run] -i ID

    \b
    Arguments:
        task-run   Send heartbeat for a given task run ID
        flow-run   Send heartbeat for a given flow run ID
    """


@heartbeat.command(hidden=True)
@click.option(
    "--id",
    "-i",
    required=True,
    help="The ID of the flow run to heartbeat.",
    hidden=True,
)
@click.option(
    "--num",
    "-n",
    type=int,
    help="The number of times to heartbeat; if not provided, will heartbeat for forever.",
    hidden=True,
)
def flow_run(id, num):
    """
    Send heartbeats back to the Prefect API for a given flow run ID.

    \b
    Options:
        --id, -i                TEXT        The id of a flow run to send heartbeats for [required]
        --num, -n               TEXT        The number of times to send a heartbeat [required]

    \b
    If num is not provided, the heartbeat will be sent indefinitely.
    """

    client = Client()
    logger = get_logger("subprocess_heartbeat")
    iter_count = 0

    # Ensure that logs are sent to the backend since this is typically called without
    # console stdout/err
    with prefect.context({"flow_run_id": id, "running_with_backend": True}):

        try:  # Log signal-like exceptions that cannot be ignored

            while iter_count < (num or 1):

                try:  # Ignore (but log) client exceptions
                    client.update_flow_run_heartbeat(id)
                except Exception as exc:
                    logger.error(
                        f"Failed to send heartbeat with exception: {exc!r}",
                        exc_info=True,
                    )

                if num:
                    iter_count += 1
                time.sleep(config.cloud.heartbeat_interval)

        except BaseException as exc:
            logger.error(
                f"Heartbeat process encountered terminal exception: {exc!r}",
                exc_info=True,
            )
            raise

import time

import click

from prefect import config
from prefect.client import Client


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
    help="The ID of the task run to heartbeat.",
    hidden=True,
)
@click.option(
    "--num",
    "-n",
    type=int,
    help="The number of times to heartbeat; if not provided, will heartbeat for forever.",
    hidden=True,
)
def task_run(id, num):
    """
    Send heartbeats back to the Prefect API for a given task run ID.

    \b
    Options:
        --id, -i                TEXT        The id of a task run to send heartbeats for [required]
        --num, -n               TEXT        The number of times to send a heartbeat [required]

    \b
    If num is not provided, the heartbeat will be sent indefinitely.
    """

    client = Client()
    iter_count = 0

    while iter_count < (num or 1):
        client.update_task_run_heartbeat(id)  # type: ignore
        if num:
            iter_count += 1
        time.sleep(config.cloud.heartbeat_interval)


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
    iter_count = 0

    while iter_count < (num or 1):
        client.update_flow_run_heartbeat(id)  # type: ignore
        if num:
            iter_count += 1
        time.sleep(config.cloud.heartbeat_interval)

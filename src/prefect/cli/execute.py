import click

import prefect
from prefect.client import Client
from prefect.engine import get_default_flow_runner_class
from prefect.tasks.secrets import PrefectSecret
from prefect.utilities.graphql import with_args


@click.group(hidden=True)
def execute():
    """
    Execute flow runs.

    \b
    Usage:
        $ prefect execute [OBJECT]

    \b
    Arguments:
        flow-run  Execute a flow run with a backend API

    \b
    Examples:
        $ prefect execute flow-run
    """


@execute.command(hidden=True)
def flow_run():
    """
    Execute a flow run in the context of a backend API.
    """
    return _execute_flow_run()


@execute.command(hidden=True)
def cloud_flow():
    """
    Execute a flow's environment in the context of Prefect Cloud.

    DEPRECATED: This command is deprecated, please use `prefect execute flow-run` instead.

    Note: this is a command that runs during Cloud execution of flows and is not meant
    for local use.
    """
    return _execute_flow_run()


def _execute_flow_run():
    flow_run_id = prefect.context.get("flow_run_id")
    if not flow_run_id:
        click.echo("Not currently executing a flow within a Cloud context.")
        raise Exception("Not currently executing a flow within a Cloud context.")

    query = {
        "query": {
            with_args("flow_run", {"where": {"id": {"_eq": flow_run_id}}}): {
                "flow": {"name": True, "storage": True},
                "version": True,
            }
        }
    }

    client = Client()
    result = client.graphql(query)
    flow_run = result.data.flow_run

    if not flow_run:
        click.echo("Flow run {} not found".format(flow_run_id))
        raise ValueError("Flow run {} not found".format(flow_run_id))

    try:
        flow_data = flow_run[0].flow
        storage_schema = prefect.serialization.storage.StorageSchema()
        storage = storage_schema.load(flow_data.storage)

        # populate global secrets
        secrets = prefect.context.get("secrets", {})
        for secret in storage.secrets:
            secrets[secret] = PrefectSecret(name=secret).run()

        with prefect.context(secrets=secrets, loading_flow=True):
            flow = storage.get_flow(storage.flows[flow_data.name])

        with prefect.context(secrets=secrets):
            if getattr(flow, "run_config", None) is not None:
                runner_cls = get_default_flow_runner_class()
                runner_cls(flow=flow).run()
            else:
                environment = flow.environment
                environment.setup(flow)
                environment.execute(flow)
    except Exception as exc:
        msg = "Failed to load and execute Flow's environment: {}".format(repr(exc))
        state = prefect.engine.state.Failed(message=msg)
        client.set_flow_run_state(flow_run_id=flow_run_id, state=state)
        click.echo(str(exc))
        raise exc

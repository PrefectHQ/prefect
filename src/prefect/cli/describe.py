import click
import pendulum
from tabulate import tabulate

from prefect.client import Client
from prefect.utilities.cli import open_in_playground
from prefect.utilities.graphql import with_args, EnumValue


@click.group(hidden=True)
def describe():
    """
    Describe commands that render JSON output of Prefect object metadata.
    """
    pass


@describe.command()
@click.option("--name", "-n", required=True, help="A flow name to query.")
@click.option("--version", "-v", type=int, help="A flow version to query.")
@click.option("--project", "-p", help="The name of a project to query.")
@click.option("--playground", is_flag=True, help="Open this query in the playground.")
def flows(name, version, project, playground):
    """
    Describe your Prefect flow.
    """

    query = {
        "query": {
            with_args(
                "flow",
                {
                    "where": {
                        "_and": {
                            "name": {"_eq": name},
                            "version": {"_eq": version},
                            "project": {"name": {"_eq": project}},
                        }
                    },
                    "order_by": {
                        "name": EnumValue("asc"),
                        "version": EnumValue("desc"),
                    },
                    "distinct_on": EnumValue("name"),
                },
            ): {
                "name": True,
                "version": True,
                "project": {"name": True},
                "created": True,
                "description": True,
                "parameters": True,
                "archived": True,
                "storage": True,
                "environment": True,
            }
        }
    }

    if playground:
        open_in_playground(query)
        return

    result = Client().graphql(query)

    flow_data = result.data.flow

    if flow_data:
        click.echo(flow_data[0])
    else:
        click.secho("{} not found".format(name), fg="red")


@describe.command()
@click.option("--name", "-n", required=True, help="A flow name to query.")
@click.option("--version", "-v", type=int, help="A flow version to query.")
@click.option("--project", "-p", help="The name of a project to query.")
@click.option("--playground", is_flag=True, help="Open this query in the playground.")
def tasks(name, version, project, playground):
    """
    Describe your Prefect flow.
    """

    query = {
        "query": {
            with_args(
                "flow",
                {
                    "where": {
                        "_and": {
                            "name": {"_eq": name},
                            "version": {"_eq": version},
                            "project": {"name": {"_eq": project}},
                        }
                    },
                    "order_by": {
                        "name": EnumValue("asc"),
                        "version": EnumValue("desc"),
                    },
                    "distinct_on": EnumValue("name"),
                },
            ): {
                "tasks": {
                    "name": True,
                    "created": True,
                    "slug": True,
                    "description": True,
                    "type": True,
                    "max_retries": True,
                    "retry_delay": True,
                    "mapped": True,
                }
            }
        }
    }

    if playground:
        open_in_playground(query)
        return

    result = Client().graphql(query)

    flow_data = result.data.flow
    if not flow_data:
        click.secho("{} not found".format(name), fg="red")
        return

    task_data = flow_data[0].tasks

    if task_data:
        for item in task_data:
            click.echo(item)
    else:
        click.secho("No tasks found for flow {}".format(name), fg="red")


@describe.command()
@click.option("--name", "-n", required=True, help="A flow run name to query")
@click.option("--flow-name", "-fn", help="A flow name to query")
@click.option("--playground", is_flag=True, help="Open this query in the playground.")
def flow_runs(name, flow_name, playground):
    """
    Describe a Prefect flow run.
    """
    query = {
        "query": {
            with_args(
                "flow_run",
                {
                    "where": {
                        "_and": {
                            "name": {"_eq": name},
                            "flow": {"name": {"_eq": flow_name}},
                        }
                    }
                },
            ): {
                "name": True,
                "flow": {"name": True},
                "created": True,
                "parameters": True,
                "auto_scheduled": True,
                "scheduled_start_time": True,
                "start_time": True,
                "end_time": True,
                "duration": True,
                "heartbeat": True,
                "serialized_state": True,
            }
        }
    }

    if playground:
        open_in_playground(query)
        return

    result = Client().graphql(query)

    flow_run_data = result.data.flow_run

    if flow_run_data:
        click.echo(flow_run_data[0])
    else:
        click.secho("{} not found".format(name), fg="red")

import json

import click

from prefect.client import Client
from prefect.utilities.graphql import EnumValue, with_args


@click.group(hidden=True)
def describe():
    """
    Describe commands that render JSON output of Prefect object metadata.

    \b
    Usage:
        $ prefect describe [OBJECT]

    \b
    Arguments:
        flow-runs   Describe flow runs
        flows       Describe flows
        tasks       Describe tasks

    \b
    Examples:
        $ prefect describe flows --name My-Flow --version 2 -o json
        {
            "name": "My-Flow",
            "version": 2,
            "project": {
                "name": "Test-Project"
            },
            "created": "2019-05-08T23:04:58.984132+00:00",
            "description": null,
            "parameters": [],
            "archived": false,
            "storage": {
                "type": "Docker",
                "flows": {
                    "My-Flow": "/root/.prefect/My-Flow.prefect"
                },
                "image_tag": "944444e8-8862-4d04-9e36-b81ab15dcaf6",
                "image_name": "z4f0bb62-8cc1-49d9-bda3-6rf53b865ea5",
                "__version__": "0.5.3",
                "registry_url": "myregistry.io/flows/"
            },
            "environment": {
                "type": "CloudEnvironment",
                "__version__": "0.5.3"
            }
        }
    """


@describe.command(hidden=True)
@click.option("--name", "-n", required=True, help="A flow name to query.", hidden=True)
@click.option("--version", "-v", type=int, help="A flow version to query.", hidden=True)
@click.option("--project", "-p", help="The name of a project to query.", hidden=True)
@click.option("--output", "-o", type=click.Choice(["json"]), hidden=True)
def flows(name, version, project, output):
    """
    Describe a Prefect flow.

    \b
    Options:
        --name, -n      TEXT    A flow name to query                [required]
        --version, -v   INTEGER A flow version to query
        --project, -p   TEXT    The name of a project to query
        --output, -o    TEXT    Output style, currently supports `json`.
                                Defaults to Python dictionary format.
    """

    where_clause = {"_and": {"name": {"_eq": name}, "version": {"_eq": version},}}
    query_results = {
        "name": True,
        "version": True,
        "created": True,
        "description": True,
        "parameters": True,
        "archived": True,
        "storage": True,
        "environment": True,
    }

    if project:
        where_clause["_and"]["project"] = {"name": {"_eq": project}}
        query_results["project"] = {"name": True}

    query = {
        "query": {
            with_args(
                "flow",
                {
                    "where": where_clause,
                    "order_by": {
                        "name": EnumValue("asc"),
                        "version": EnumValue("desc"),
                    },
                    "distinct_on": EnumValue("name"),
                },
            ): query_results
        }
    }

    result = Client().graphql(query)

    flow_data = result.data.flow
    if flow_data:
        if output == "json":
            click.echo(json.dumps(flow_data[0]))
        else:
            click.echo(flow_data[0])
    else:
        click.secho("{} not found".format(name), fg="red")


@describe.command(hidden=True)
@click.option("--name", "-n", required=True, help="A flow name to query.", hidden=True)
@click.option("--version", "-v", type=int, help="A flow version to query.", hidden=True)
@click.option("--project", "-p", help="The name of a project to query.", hidden=True)
@click.option("--output", "-o", type=click.Choice(["json"]), hidden=True)
def tasks(name, version, project, output):
    """
    Describe tasks from a Prefect flow. This command is similar to `prefect describe flow`
    but instead of flow metadata it outputs task metadata.

    \b
    Options:
        --name, -n      TEXT    A flow name to query                [required]
        --version, -v   INTEGER A flow version to query
        --project, -p   TEXT    The name of a project to query
        --output, -o    TEXT    Output style, currently supports `json`.
                                Defaults to Python dictionary format.
    """

    where_clause = {"_and": {"name": {"_eq": name}, "version": {"_eq": version},}}

    if project:
        where_clause["_and"]["project"] = {"name": {"_eq": project}}

    query = {
        "query": {
            with_args(
                "flow",
                {
                    "where": where_clause,
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

    result = Client().graphql(query)

    flow_data = result.data.flow
    if not flow_data:
        click.secho("{} not found".format(name), fg="red")
        return

    task_data = flow_data[0].tasks

    if task_data:
        for item in task_data:
            if output == "json":
                click.echo(json.dumps(item))
            else:
                click.echo(item)
    else:
        click.secho("No tasks found for flow {}".format(name), fg="red")


@describe.command(hidden=True)
@click.option(
    "--name", "-n", required=True, help="A flow run name to query", hidden=True
)
@click.option("--flow-name", "-fn", help="A flow name to query", hidden=True)
@click.option("--output", "-o", type=click.Choice(["json"]), hidden=True)
def flow_runs(name, flow_name, output):
    """
    Describe a Prefect flow run.

    \b
    Options:
        --name, -n          TEXT    A flow run name to query            [required]
        --flow-name, -fn    TEXT    A flow name to query
        --output, -o    TEXT    Output style, currently supports `json`.
                                Defaults to Python dictionary format.
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

    result = Client().graphql(query)

    flow_run_data = result.data.flow_run

    if flow_run_data:
        if output == "json":
            click.echo(json.dumps(flow_run_data[0]))
        else:
            click.echo(flow_run_data[0])
    else:
        click.secho("{} not found".format(name), fg="red")

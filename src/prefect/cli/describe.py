import click
import pendulum
from tabulate import tabulate

from prefect.client import Client
from prefect.utilities.graphql import with_args, EnumValue


@click.group()
def describe():
    """
    Get commands that refer to querying Prefect Cloud metadata.
    """
    pass


@describe.command()
@click.option("--name", "-n", required=True, help="A flow name to query.")
@click.option("--version", "-v", type=int, help="A flow version to query.")
@click.option("--project", "-p", help="The name of a project to query.")
def flow(name, version, project):
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
                "schedule": True,
                "schedule_is_active": True,
                "archived": True,
                # "storage": True,
                "environment": True,
            }
        }
    }

    result = Client().graphql(query)

    flow_data = result.data.flow

    if flow_data:
        click.echo(flow_data[0])
    else:
        click.secho("{} not found".format(name), fg="red")

import click
import pendulum
from tabulate import tabulate

from prefect.client import Client
from prefect.utilities.graphql import with_args, EnumValue


@click.group()
def get():
    """
    Get commands
    """
    pass


@get.command()
@click.option("--name", "-n")
def flows(name):
    """
    Get flows
    """
    query = {
        "query": {
            with_args(
                "flow",
                {
                    "where": {"name": {"_eq": name}},
                    "order_by": {
                        "name": EnumValue("asc"),
                        "version": EnumValue("desc"),
                    },
                },
            ): {"name": True, "version": True, "created": True}
        }
    }

    # where_clause = {"where": {"name": {"_eq": name}}}
    # query = {"query": {with_args("flow", where_clause): "id"}}

    result = Client().graphql(query)

    flow_data = result.data.flow

    output = []

    for item in flow_data:
        output.append(
            [item.name, item.version, pendulum.parse(item.created).diff_for_humans()]
        )

    click.echo(tabulate(output, headers=["name", "version", "age"]))

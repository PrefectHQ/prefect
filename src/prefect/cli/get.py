import click
import pendulum
from tabulate import tabulate

from prefect.client import Client
from prefect.utilities.graphql import with_args, EnumValue


@click.group()
def get():
    """
    Get commands that refer to querying Prefect Cloud metadata.
    """
    pass


@get.command()
@click.option("--name", "-n", help="A flow name to query.")
@click.option("--version", "-v", type=int, help="A flow version to query.")
@click.option("--project", "-p", help="The name of a project to query.")
@click.option("--all-versions", is_flag=True, help="Query all flow versions.")
def flows(name, version, project, all_versions):
    """
    Query information regarding your Prefect flows.
    """

    distinct_on = EnumValue("name")
    if all_versions:
        distinct_on = None

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
                    "distinct_on": distinct_on,
                },
            ): {
                "name": True,
                "version": True,
                "project": {"name": True},
                "created": True,
            }
        }
    }

    result = Client().graphql(query)

    flow_data = result.data.flow

    output = []

    for item in flow_data:
        output.append(
            [
                item.name,
                item.version,
                item.project.name,
                pendulum.parse(item.created).diff_for_humans(),
            ]
        )

    click.echo(
        tabulate(
            output,
            headers=["NAME", "VERSION", "PROJECT NAME", "AGE"],
            tablefmt="plain",
            numalign="left",
            stralign="left",
        )
    )

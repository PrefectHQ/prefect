import click

from prefect.client import Client
from prefect.utilities.graphql import with_args, EnumValue


# TODO: `--watch` option
@click.group(hidden=True)
def run():
    """
    Run a Prefect flow.
    """
    pass


@run.command()
@click.option("--name", "-n", required=True, help="The name of a flow to run.")
@click.option(
    "--project", "-p", required=True, help="The project that contains the flow."
)
@click.option("--version", "-v", type=int, help="A flow version to run.")
def cloud(name, project, version):
    """
    Run a deployed flow in Prefect Cloud.
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
            ): {"id": True}
        }
    }

    client = Client()
    result = client.graphql(query)

    flow_data = result.data.flow

    if flow_data:
        flow_id = flow_data[0].id
    else:
        click.secho("{} not found".format(name), fg="red")
        return

    flow_run_id = client.create_flow_run(flow_id=flow_id)
    click.echo(flow_run_id)

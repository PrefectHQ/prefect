import click
import pendulum
from tabulate import tabulate

from prefect.client import Client
from prefect.utilities.graphql import with_args, EnumValue


# May not need to be a group.
# Option: could be both starting a flow run on cloud and locally running a flow
# TODO: `--watch` option
@click.group()
def run():
    """
    Run a Prefect flow.
    """
    pass

import click
import pendulum
from tabulate import tabulate

from prefect.client import Client
from prefect.utilities.graphql import with_args, EnumValue


# Can take full flow metadata or maybe parse from a file
@click.group()
def deploy():
    """
    Deploy flows to Prefect Cloud.
    """
    pass

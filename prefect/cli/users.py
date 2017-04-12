import click
import requests
from prefect import config
from .auth import token_header


@click.group()
def users():
    """
    Interact with Prefect users
    """
    pass

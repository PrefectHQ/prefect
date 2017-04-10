import click
import requests
from prefect import config
from .auth import token_header
server = config.get('prefect', 'server_address')
api_url = server + '/user'


@click.group()
def users():
    """
    Interact with Prefect users
    """
    pass

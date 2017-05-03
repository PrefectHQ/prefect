#!/usr/bin/env python

import click
import logging
import os
import requests
import sys
from prefect import config
from .auth import token_header

from .users import users
from .namespaces import namespaces
# from .data import data
# from .run import run


server = config.get('server', 'address')

@click.group()
def cli():
    """
    The Prefect CLI
    """
    pass

cli.add_command(users)
cli.add_command(namespaces)

try:
    from prefect.server.cli import database, server
    cli.add_command(database)
    cli.add_command(server)
except ImportError:
    raise

try:
    from prefect.engine.cli import cluster
    cli.add_command(cluster)
except ImportError:
    raise
@cli.command()
@click.argument('email')
@click.argument('password')
def login(email, password):
    """
    Log in to the Prefect CLI
    """
    response = requests.post(server + '/user/login', auth=(email, password))
    if response.ok:
        auth.save_token(response.json()['token'])
        click.echo(click.style('Logged in succesfully!', fg='green'))
    else:
        click.echo(click.style('Invalid credentials.', fg='red'))

# check if credentials are valid and show a warning
# response = requests.get(server + '/user/login', headers=token_header())
# if not response.ok:
#     click.echo(click.style(
#         '\nYou are not logged in to the Prefect CLI!'
#         '\nRun `prefect login <email> <password>` to continue.\n',
#         fg='red', bold=True))

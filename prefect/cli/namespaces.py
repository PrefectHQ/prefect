import click
import requests
import prefect
# server = prefect.config.get('prefect', 'server_address')
# api_url = server + '/namespace'

@click.group()
def namespaces():
    """
    Interact with Prefect namespaces
    """
    pass


@namespaces.command()
def list():
    response = requests.get(api_url, headers=prefect.cli.auth.token_header())
    click.echo({'status': response.status_code, 'result': response.json()})

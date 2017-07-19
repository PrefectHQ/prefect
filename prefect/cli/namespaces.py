import click
import requests
import prefect
# server = prefect.config.get('prefect', 'server_address')
# api_url = server + '/project'

@click.group()
def projects():
    """
    Interact with Prefect projects
    """
    pass


@projects.command()
def list():
    response = requests.get(api_url, headers=prefect.cli.auth.token_header())
    click.echo({'status': response.status_code, 'result': response.json()})

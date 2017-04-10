import os


def token_header():
    cli_credentials = os.path.expanduser('~/.prefect/cli_credentials')

    if os.path.isfile(cli_credentials):
        with open(cli_credentials, 'r') as f:
            credentials = f.read()
    else:
        credentials = ''
    return {'Authorization': credentials}


def save_token(token):
    cli_credentials = os.path.expanduser('~/.prefect/cli_credentials')
    with open(cli_credentials, 'w') as f:
        f.write(token)

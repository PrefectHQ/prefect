import click
from click.exceptions import Abort
from tabulate import tabulate
import warnings

from prefect import Client, config
from prefect.utilities.exceptions import AuthorizationError, ClientError


def check_override_auth_token():
    if config.cloud.get("auth_token"):
        click.secho("Auth token already present in config.", fg="red")
        raise Abort


def warn_deprecated_api_tokens():
    warnings.warn(
        """
        API Tokens have been deprecated in favor of API Keys.
        Visit https://docs.prefect.io/orchestration/concepts/api_keys.html
        for information on how to use API Keys.
        """
    )


@click.group(hidden=True)
def auth():
    """
    Manage Prefect Cloud API Keys.

    \b
    Usage:
        $ prefect auth [COMMAND]

    \b
    Arguments:
        create-api-key   Print a new API Token for a User or Service Account
        revoke-api-key   Revokes an API Key for a User or Service Account
        list-api-keys    List API Key ids for User and Service Accounts (if Administrator)

    \b
    Examples:
        $ prefect auth create-api-key --user-id $USER_ID --name $KEY_NAME
        API_KEY

    \b
        $ prefect auth list-api-keys
        NAME         ID         USER_ID
        $KEY_NAME    $KEY_ID    $USER_ID

    \b
        $ prefect auth revoke-api-key --id $KEY_ID
        Token successfully revoked
    """
    if config.backend == "server":
        raise click.UsageError("Auth commands with server are not currently supported.")


@auth.command(hidden=True)
@click.option("--name", "-n", required=True, help="A token name.", hidden=True)
@click.option("--user-id", "-u", required=True, help="a user id.", hidden=True)
def create_api_key(name, user_id):
    """
    Create a Prefect Cloud API Key for a user (must be active user or,
    if active user is an Administrator, a Service Account in the active tenant).
    Visit https://docs.prefect.io/orchestration/concepts/api_keys.html
    for information on how to use API Keys.

    \b
    Options:
        --name, -n      TEXT    A name to give the generated Key
        --user-id, -u   TEXT    User ID with whom to associate the API Key
    """

    client = Client()

    output = client.graphql(
        query={
            "mutation($input: create_api_key_input!)": {
                "create_api_key(input: $input)": {"key"}
            }
        },
        variables=dict(input=dict(name=name, user_id=user_id)),
    )

    if not output.get("data", None):
        click.secho("Issue creating API token", fg="red")
        return

    click.echo(output.data.create_api_key.key)


@auth.command(hidden=True)
@click.option("--id", "-i", required=True, help="An API Key ID.", hidden=True)
def revoke_api_key(id):
    """
    Revoke a Prefect Cloud API Key
    Visit https://docs.prefect.io/orchestration/concepts/api_keys.html
    for information on how to use API Keys.

    \b
    Options:
        --id, -i    TEXT    The id of a key to revoke
    """

    client = Client()

    output = client.graphql(
        query={
            "mutation($input: delete_api_key_input!)": {
                "delete_api_key(input: $input)": {"success"}
            }
        },
        variables=dict(input=dict(key_id=id)),
    )

    if not output.get("data", None) or not output.data.delete_api_key.success:
        click.secho("Unable to revoke token with ID {}".format(id), fg="red")
        return

    click.secho("Token successfully revoked", fg="green")


@auth.command(hidden=True)
def list_api_keys():
    """
    List available Prefect Cloud API keys for client's User.
    If client's User has Administrator role, will also return API Keys
    for Service Accounts in the client's tenant
    """

    client = Client()

    output = client.graphql(
        query={"query": {"auth_api_key": {"id", "name", "user_id"}}}
    )

    if not output.get("data", None):
        click.secho("Unable to list API Keys", fg="red")
        return

    api_keys = []
    for item in output.data.auth_api_key:
        api_keys.append([item.name, item.id, item.user_id])

    click.echo(
        tabulate(
            api_keys,
            headers=["NAME", "ID", "USER_ID"],
            tablefmt="plain",
            numalign="left",
            stralign="left",
        )
    )


@auth.command(hidden=True)
@click.option(
    "--token", "-t", required=True, help="A Prefect Cloud API token.", hidden=True
)
def login(token):
    """
    Log in to Prefect Cloud with an api token to use for Cloud communication. (DEPRECATED)
    Visit https://docs.prefect.io/orchestration/concepts/api_keys.html
    for information on how to use API Keys.

    \b
    Options:
        --token, -t         TEXT    A Prefect Cloud api token  [required]
    """
    warn_deprecated_api_tokens()
    check_override_auth_token()

    client = Client(api_token=token)

    # Verify login obtained a valid api token
    try:
        output = client.graphql(
            query={"query": {"user": {"default_membership": "tenant_id"}}}
        )

        # Log into default membership
        success_login = client.login_to_tenant(
            tenant_id=output.data.user[0].default_membership.tenant_id
        )

        if not success_login:
            raise AuthorizationError

    except AuthorizationError:
        click.secho(
            f"Error attempting to use Prefect API token {token}. "
            "Please check that you are providing a USER scoped Personal Access Token.\n"
            "For more information visit the documentation for USER tokens at "
            "https://docs.prefect.io/orchestration/concepts/tokens.html#user",
            fg="red",
        )
        return
    except ClientError:
        click.secho(
            "Error attempting to communicate with Prefect Cloud. "
            "Please check that you are providing a USER scoped Personal Access Token.\n"
            "For more information visit the documentation for USER tokens at "
            "https://docs.prefect.io/orchestration/concepts/tokens.html#user",
            fg="red",
        )
        return

    # save token
    client.save_api_token()

    click.secho("Login successful!", fg="green")


@auth.command(hidden=True)
def logout():
    """
    Log out of Prefect Cloud (DEPRECATED)
    Visit https://docs.prefect.io/orchestration/concepts/api_keys.html
    for information on how to use API Keys.
    """
    warn_deprecated_api_tokens()
    check_override_auth_token()

    click.confirm(
        "Are you sure you want to log out of Prefect Cloud?", default=False, abort=True
    )

    client = Client()
    tenant_id = client.active_tenant_id

    if not tenant_id:
        click.secho("No tenant currently active", fg="red")
        return

    client.logout_from_tenant()

    click.secho("Logged out from tenant {}".format(tenant_id), fg="green")


@auth.command(hidden=True)
def list_tenants():
    """
    List available tenants
    """
    warn_deprecated_api_tokens()
    check_override_auth_token()

    client = Client()

    tenants = client.get_available_tenants()
    active_tenant_id = client.active_tenant_id

    output = []
    for item in tenants:
        active = None
        if item.id == active_tenant_id:
            active = "*"
        output.append([item.name, item.slug, item.id, active])

    click.echo(
        tabulate(
            output,
            headers=["NAME", "SLUG", "ID", ""],
            tablefmt="plain",
            numalign="left",
            stralign="left",
        )
    )


@auth.command(hidden=True)
@click.option(
    "--id", "-i", required=False, help="A Prefect Cloud tenant id.", hidden=True
)
@click.option(
    "--slug", "-s", required=False, help="A Prefect Cloud tenant slug.", hidden=True
)
def switch_tenants(id, slug):
    """
    Switch active tenant

    \b
    Options:
        --id, -i    TEXT    A Prefect Cloud tenant id
        --slug, -s  TEXT    A Prefect Cloud tenant slug
    """
    warn_deprecated_api_tokens()
    check_override_auth_token()

    client = Client()

    login_success = client.login_to_tenant(tenant_slug=slug, tenant_id=id)
    if not login_success:
        click.secho("Unable to switch tenant", fg="red")
        return

    click.secho("Tenant switched", fg="green")


@auth.command(hidden=True)
@click.option("--name", "-n", required=True, help="A token name.", hidden=True)
@click.option("--scope", "-s", required=True, help="A token scopre.", hidden=True)
def create_token(name, scope):
    """
    Create a Prefect Cloud API token. (DEPRECATED)
    Visit https://docs.prefect.io/orchestration/concepts/api_keys.html
    for information on how to use API Keys.

    \b
    Options:
        --name, -n      TEXT    A name to give the generated token
        --scope, -s     TEXT    A scope for the token
    """
    warn_deprecated_api_tokens()

    client = Client()

    output = client.graphql(
        query={
            "mutation($input: create_api_token_input!)": {
                "create_api_token(input: $input)": {"token"}
            }
        },
        variables=dict(input=dict(name=name, scope=scope)),
    )

    if not output.get("data", None):
        click.secho("Issue creating API token", fg="red")
        return

    click.echo(output.data.create_api_token.token)


@auth.command(hidden=True)
@click.option("--id", "-i", required=True, help="A token ID.", hidden=True)
def revoke_token(id):
    """
    Revoke a Prefect Cloud API token (DEPRECATED)
    Visit https://docs.prefect.io/orchestration/concepts/api_keys.html
    for information on how to use API Keys.

    \b
    Options:
        --id, -i    TEXT    The id of a token to revoke
    """
    warn_deprecated_api_tokens()
    check_override_auth_token()

    client = Client()

    output = client.graphql(
        query={
            "mutation($input: delete_api_token_input!)": {
                "delete_api_token(input: $input)": {"success"}
            }
        },
        variables=dict(input=dict(token_id=id)),
    )

    if not output.get("data", None) or not output.data.delete_api_token.success:
        click.secho("Unable to revoke token with ID {}".format(id), fg="red")
        return

    click.secho("Token successfully revoked", fg="green")


@auth.command(hidden=True)
def list_tokens():
    """
    List your available Prefect Cloud API tokens. (DEPRECATED)
    Visit https://docs.prefect.io/orchestration/concepts/api_keys.html
    for information on how to use API Keys.
    """
    warn_deprecated_api_tokens()
    check_override_auth_token()

    client = Client()

    output = client.graphql(query={"query": {"api_token": {"id", "name"}}})

    if not output.get("data", None):
        click.secho("Unable to list API tokens", fg="red")
        return

    tokens = []
    for item in output.data.api_token:
        tokens.append([item.name, item.id])

    click.echo(
        tabulate(
            tokens,
            headers=["NAME", "ID"],
            tablefmt="plain",
            numalign="left",
            stralign="left",
        )
    )

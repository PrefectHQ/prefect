import click
from tabulate import tabulate

from prefect import Client, config
from prefect.utilities.exceptions import AuthorizationError, ClientError


@click.group(hidden=True)
def auth():
    """
    Handle Prefect Cloud authorization.

    \b
    Usage:
        $ prefect auth [COMMAND]

    \b
    Arguments:
        login           Log in to Prefect Cloud
        logout          Log out of Prefect Cloud
        list-tenants    List your available tenants
        switch-tenants  Switch to a different tenant
        create-token    Create an API token

    \b
    Examples:
        $ prefect auth login --token MY_TOKEN
        Log in successful

    \b
        $ prefect auth logout
        Logged out from tenant TENANT_ID

    \b
        $ prefect auth list-tenants
        NAME                        SLUG                        ID
        Test Person                 test-person                 816sghf2-4d51-4338-a333-1771gns7614d
        test@prefect.io's Account   test-prefect-io-s-account   1971hs9f-e8ha-4a33-8c33-64512gds86g1  *

    \b
        $ prefect auth switch-tenants --slug test-person
        Tenant switched

    \b
        $ prefect auth create-token -n MyToken -r RUNNER
        ...token output...
    """
    pass


@auth.command(hidden=True)
@click.option(
    "--token", "-t", required=True, help="A Prefect Cloud API token.", hidden=True
)
def login(token):
    """
    Log in to Prefect Cloud with an api token to use for Cloud communication.

    \b
    Options:
        --token, -t         TEXT    A Prefect Cloud api token  [required]
    """

    if config.cloud.get("auth_token"):
        click.confirm(
            "Prefect Cloud API token already set in config. Do you want to override?",
            default=True,
            abort=True,
        )

    client = Client(api_token=token)

    # Verify login obtained a valid api token
    try:
        client.graphql(query={"query": {"tenant": "id"}})
    except AuthorizationError:
        click.secho(
            "Error attempting to use Prefect API token {}".format(token), fg="red"
        )
        return
    except ClientError:
        click.secho("Error attempting to communicate with Prefect Cloud", fg="red")
        return

    # save token
    client.save_api_token()

    click.secho("Log in successful", fg="green")


@auth.command(hidden=True)
def logout():
    """
    Log out of Prefect Cloud
    """
    click.confirm(
        "Are you sure you want to log out of Prefect Cloud?", default=False, abort=True
    )

    client = Client()
    tenant_id = client._active_tenant_id

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

    client = Client()

    tenants = client.get_available_tenants()
    active_tenant_id = client._active_tenant_id

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

    client = Client()

    login_success = client.login_to_tenant(tenant_slug=slug, tenant_id=id)
    if not login_success:
        click.secho("Unable to switch tenant", fg="red")
        return

    click.secho("Tenant switched", fg="green")


@auth.command(hidden=True)
@click.option("--name", "-n", required=True, help="A token name.", hidden=True)
@click.option("--role", "-r", required=True, help="A token role.", hidden=True)
def create_token(name, role):
    """
    Create a Prefect Cloud API token.

    For more info on API tokens visit https://docs.prefect.io/cloud/cloud_concepts/api.html

    \b
    Options:
        --name, -n      TEXT    A name to give the generated token
        --role, -r      TEXT    A role for the token
    """
    client = Client()

    output = client.graphql(
        query={
            "mutation($input: createAPITokenInput!)": {
                "createAPIToken(input: $input)": {"token"}
            }
        },
        variables=dict(input=dict(name=name, role=role)),
    )

    if not output.get("data", None):
        click.secho("Issue creating API token", fg="red")
        return

    click.echo(output.data.createAPIToken.token)

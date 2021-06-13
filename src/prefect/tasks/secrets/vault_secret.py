import hvac
import re
import json
import os

import prefect
from prefect.tasks.secrets import SecretBase, PrefectSecret
from prefect.utilities.tasks import defaults_from_attrs


class VaultSecret(SecretBase):
    """
    Vault Secrets Task.  This task retrieves the underlying secret through
    the Vault API.  Local secrets are checked before querying the Vault service.
    Client configuration:
        - vault_addr: set via env var.  Both VAULT_ADDR and vault_addr supported
    Parameters:
        - vault.credentials: parameter of a Prefect Secret containing vault credentials
                Supported vault client authentication methods:
                - token:  { 'VAULT_TOKEN': '<token>' }
                - appRole: { 'VAULT_ROLE_ID': '<role-id>',
                             'VAULT_SECRET_ID': '<secret-id>' }

    Args:
        - name (str): The secret name defined by the Vault secret path "<mount-point>/<path>"
        - **kwargs (Any, optional): additional keyword args passed to the Task constructor
    Raises:
        - ValueError: if a `result` keyword is passed
    """

    def __init__(self, name, **kwargs):
        kwargs["name"] = name
        super().__init__(**kwargs)

    def _get_vault_secret(self, name):
        """
        Connect to vault service and retrieve a secret value
        Parameters:
            - vault.credentials: Prefect Parameter with Prefect Secret containing vault
                auth credentials
        Arguments:
            - name (str): name of the secret to be retrieved
        Returns:
            - secret (str): the value of the secret retrieved
        Raises:
            - KeyError: unable to find VAULT_ADDR or vault_addr
            - PermissionError: unable to authenticate or attempting an unsupported auth method
            - KeyError: unable to lookup secret in vault
            - PermissionError: provided token/role not authorised to access the secret
        """
        self.logger.debug(f"looking up vault path: {name}")
        client = hvac.Client()
        # get vault address url
        vault_url = os.getenv("VAULT_ADDR", default=None)
        if vault_url is None:
            vault_url = os.getenv("vault_addr", default=None)
            if vault_url is None:
                raise KeyError(
                    "VAULT_ADDR url var not found. "
                    'Either "VAULT_ADDR" or "vault_addr" env var required.'
                )
        client.url = vault_url
        self.logger.debug(f"vault addr set to: {client.url}")

        # get vault auth credentials from the indicated secret
        sk_vault_creds = prefect.context.parameters["vault.credentials"]
        vault_creds = PrefectSecret(sk_vault_creds).run()
        if "VAULT_TOKEN" in vault_creds.keys():
            client.token = vault_creds["VAULT_TOKEN"]
        elif (
            "VAULT_ROLE_ID" in vault_creds.keys()
            and "VAULT_SECRET_ID" in vault_creds.keys()
        ):
            client.auth_approle(
                vault_creds["VAULT_ROLE_ID"], vault_creds["VAULT_SECRET_ID"]
            )
        else:
            raise PermissionError(
                "Unable to authenticate with vault service.  "
                "Supported methods: token, appRole"
            )
        if not client.is_authenticated():
            raise PermissionError(
                "Unable to autheticate with vault using supplied credentials"
            )
        self.logger.debug("passed vault authentication check")
        # regex to parse path into 2 named parts: <mount_point>/<path>
        secret_path_re = r"^(?P<mount_point>[^/]+)/(?P<path>.+)$"
        m = re.fullmatch(secret_path_re, name)
        if m is None:
            raise KeyError(
                f'Invalid secret path: {name}.  Expected: "<mount_point>/<path>"'
            )

        vault_path = m.groupdict()
        value = ""
        try:
            vault_secret = client.secrets.kv.v2.read_secret_version(
                path=vault_path["path"], mount_point=vault_path["mount_point"]
            )
            value = vault_secret["data"]["data"]
        except KeyError as exc:
            raise KeyError(f"Secret not found: {vault_path['path']}") from exc
        except hvac.exceptions.Forbidden:
            raise PermissionError(f"Access forbidden: {vault_path['path']}")
        return value

    @defaults_from_attrs("name")
    def run(self, name: str = None):
        """
        The run method for VaultSecret Task.  Note that this method first checks context
        for the local secret value, and if not found either raises an error or queries
        the Vault service, depending on whether `config.cloud.use_local_secrets` is `True`
        or `False`.

        Args:
            - name (str, optional): The secret name defined by the Vault secret
                path "<mount-point>/<path>".  Defaults to the name provided at initialization.

        Returns:
            - Any: the underlying value of the Vault Secret
        """
        if isinstance(prefect.context.get("flow"), prefect.core.flow.Flow):
            raise ValueError(
                "Secrets should only be retrieved during a Flow run, "
                "not while building a Flow."
            )

        secrets = prefect.context.get("secrets", {})
        value = None
        try:
            value = secrets[name]
        except KeyError:
            if prefect.context.config.cloud.use_local_secrets is False:
                # lookup the secret value in Vault
                value = self._get_vault_secret(name)
            else:
                raise ValueError(f'Local secret "{name}" not found.') from None

        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

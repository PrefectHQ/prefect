import re
import json
import os

try:
    import hvac
except ImportError as err:
    raise ImportError(
        "Using `prefect.tasks.secrets.vault_secret` requires hvac to be installed."
    ) from err

import prefect
from prefect.tasks.secrets import SecretBase, PrefectSecret
from prefect.utilities.tasks import defaults_from_attrs
from prefect.exceptions import ClientError


class VaultSecret(SecretBase):
    """
    Vault Secrets Task.  This task retrieves a secret using the Hashicorp Vault service.
    Local secrets are checked before querying the Vault service.

    Client configuration:
        - vault_addr: set via env var.  Both VAULT_ADDR and vault_addr supported

    Args:
        - name (str): The secret name defined by the Vault secret path "<mount-point>/<path>"
        - vault_credentials_secret (str, optional): name of the PrefectSecret containing Vault
            credentials.
                Defaults to a PrefectSecret named `VAULT_CREDENTIALS`.
                Supported vault client authentication methods:
                * token { 'VAULT_TOKEN: '<token>' }
                * appRole: { 'VAULT_ROLE_ID': '<role-id>',
                             'VAULT_SECRET_ID': '<secret-id>' }
        - **kwargs (Any, optional): additional keyword args passed to the Task constructor

    Raises:
        - ValueError: if a `result` keyword is passed
    """

    def __init__(
        self, name: str, vault_credentials_secret: str = "VAULT_CREDENTIALS", **kwargs
    ):
        self.vault_credentials_secret = vault_credentials_secret
        kwargs["name"] = name
        super().__init__(**kwargs)

    def _get_vault_secret(self, name: str):
        """
        Connect to vault service and retrieve a secret value
        Arguments:
            - name (str): name of the secret to be retrieved using "<mount_point>/<path>"

        Returns:
            - secret (dict): a dict of the secret key/value items retrieved

        Raises:
            - ClientError: unable to configure the vault client
            - PermissionError: unable to authenticate or attempting an unsupported auth method
            - KeyError: unable to lookup secret in vault using the secret path
            - PermissionError: provided token/role not authorised to access the secret
        """
        self.logger.debug(f"looking up vault path: {name}")
        client = hvac.Client()
        # get vault address url
        vault_url = os.getenv("VAULT_ADDR", default=None)
        if vault_url is None:
            vault_url = os.getenv("vault_addr", default=None)
            if vault_url is None:
                raise ClientError(
                    "VAULT_ADDR url var not found. "
                    'Either "VAULT_ADDR" or "vault_addr" env var required.'
                )
        client.url = vault_url
        self.logger.debug(f"vault addr set to: {client.url}")

        # get vault auth credentials from the PrefectSecret
        vault_creds = PrefectSecret(self.vault_credentials_secret).run()
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
            raise ClientError(
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
        except hvac.exceptions.InvalidPath as exc:
            raise KeyError(f"Secret not found: {vault_path['path']}") from exc
        except hvac.exceptions.Forbidden as exc:
            raise PermissionError(f"Access forbidden: {vault_path['path']}") from exc
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

        Raises:
            - ValueError: if a `result` keyword is passed, or if called within a flow building context,
                or `use_local_secrets=True` and the Secret does not exist
            - KeyError: if `use_local_secrets=False` and the Client fails to retrieve the secret
            - PermissionError: if `use_local_secrets=False` and the Client is not authorised to read
                the secret
            - ClientError: if unable to find VAULT_ADDR or vault_addr environment variable
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

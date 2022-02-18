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


class VaultSecret(SecretBase):
    """
    Vault Secrets Task.  This task retrieves a secret using the Hashicorp Vault service.

    Client configuration:
        - vault_addr: set via env var.  Both `VAULT_ADDR` and `vault_addr` supported

    Args:
        - name (str): secret name defined by the Vault secret path "<mount-point>/<path>"
        - vault_credentials_secret (str, optional): name of the PrefectSecret containing Vault
          credentials.
            Defaults to a PrefectSecret named `VAULT_CREDENTIALS`.
            Supported vault client authentication methods:
            * token:
            {
                'VAULT_TOKEN: '<token>'
            }
            * appRole:
            {
                'VAULT_ROLE_ID': '<role-id>',
                'VAULT_SECRET_ID': '<secret-id>'
            }
            * kubernetesRole:
            {
                'VAULT_KUBE_AUTH_ROLE': '<kube-role>',
                'VAULT_KUBE_AUTH_PATH': '<vault-kube-path>',
                'VAULT_KUBE_TOKEN_FILE': '/var/run/secrets/kubernetes.io/serviceaccount/token' (default)
            }
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
            - ValueError: unable to configure the vault client or unable to parse the provided
                secret name into a "<mount_point>/<path>" pattern
            - RuntimeError: unable to authenticate or attempting an unsupported auth method or
                or provided token/role not authorised to access the the secret
            - KeyError: unable to lookup secret in vault using the secret path
        """
        self.logger.debug(f"Looking up vault path: {name}")
        client = hvac.Client()
        # get vault address url
        vault_url = os.getenv("VAULT_ADDR") or os.getenv("vault_addr")
        if not vault_url:
            raise ValueError(
                "VAULT_ADDR url var not found. "
                'Either "VAULT_ADDR" or "vault_addr" env var required.'
            )
        client.url = vault_url
        self.logger.debug(f"Vault addr set to: {client.url}")

        # get vault auth credentials from the PrefectSecret
        vault_creds = PrefectSecret(self.vault_credentials_secret).run()
        if "VAULT_TOKEN" in vault_creds.keys():
            client.token = vault_creds["VAULT_TOKEN"]
        elif (
            "VAULT_ROLE_ID" in vault_creds.keys()
            and "VAULT_SECRET_ID" in vault_creds.keys()
        ):
            client.auth.approle.login(
                vault_creds["VAULT_ROLE_ID"], vault_creds["VAULT_SECRET_ID"]
            )
        elif (
            "VAULT_KUBE_AUTH_ROLE" in vault_creds.keys()
            and "VAULT_KUBE_AUTH_PATH" in vault_creds.keys()
        ):
            token_file = vault_creds.get(
                "VAULT_KUBE_TOKEN_FILE",
                "/var/run/secrets/kubernetes.io/serviceaccount/token",
            )

            with open(token_file, "r") as f:
                jwt = f.read()

            client.auth.kubernetes.login(
                role=vault_creds["VAULT_KUBE_AUTH_ROLE"],
                jwt=jwt,
                mount_point=vault_creds["VAULT_KUBE_AUTH_PATH"],
            )
        else:
            raise ValueError(
                "Unable to authenticate with vault service.  "
                "Supported methods: token, appRole and kubernetesRole"
            )
        if not client.is_authenticated():
            raise RuntimeError(
                "Unable to autheticate with vault using supplied credentials"
            )
        self.logger.debug("Passed vault authentication check")
        # regex to parse path into 2 named parts: <mount_point>/<path>
        secret_path_re = r"^(?P<mount_point>[^/]+)/(?P<path>.+)$"
        m = re.fullmatch(secret_path_re, name)
        if m is None:
            raise ValueError(
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
            raise KeyError(f"Secret not found: {name}") from exc
        except hvac.exceptions.Forbidden as exc:
            raise RuntimeError(f"Access forbidden: {name}") from exc
        return value

    @defaults_from_attrs("name")
    def run(self, name: str = None):
        """
        The run method for VaultSecret Task.

        Args:
            - name (str, optional): The secret name defined by the Vault secret
                path "<mount-point>/<path>".  Defaults to the name provided at initialization.

        Returns:
            - Any: the underlying value of the Vault Secret

        Raises:
            - ValueError: if a `result` keyword is passed, or if called within a flow building context
                or if unable to find VAULT_ADDR or vault_addr environment variable
            - RuntimeError: if `use_local_secrets=False` and the Client is not authorised to read
                the secret
        """
        if isinstance(prefect.context.get("flow"), prefect.core.flow.Flow):
            raise ValueError(
                "Secrets should only be retrieved during a Flow run, "
                "not while building a Flow."
            )

        value = None
        try:
            # lookup the secret value in Vault
            value = self._get_vault_secret(name)
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

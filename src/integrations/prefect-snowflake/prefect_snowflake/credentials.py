"""Credentials block for authenticating with Snowflake."""

import re
import warnings
from pathlib import Path
from typing import Any, Optional, Union

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

import snowflake.connector
from pydantic import VERSION as PYDANTIC_VERSION

from prefect.blocks.abstract import CredentialsBlock

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, SecretBytes, SecretField, SecretStr, root_validator
else:
    from pydantic import Field, SecretBytes, SecretField, SecretStr, root_validator

# PEM certificates have the pattern:
#   -----BEGIN PRIVATE KEY-----
#   <- multiple lines of encoded data->
#   -----END PRIVATE KEY-----
#
# The regex captures the header and footer into groups 1 and 3, the body into group 2
# group 1: "header" captures series of hyphens followed by anything that is
#           not a hyphen followed by another string of hyphens
# group 2: "body" capture everything upto the next hyphen
# group 3: "footer" duplicates group 1
_SIMPLE_PEM_CERTIFICATE_REGEX = "^(-+[^-]+-+)([^-]+)(-+[^-]+-+)"


class InvalidPemFormat(Exception):
    """Invalid PEM Format Certificate"""


class SnowflakeCredentials(CredentialsBlock):
    """
    Block used to manage authentication with Snowflake.

    Args:
        account (str): The snowflake account name.
        user (str): The user name used to authenticate.
        password (SecretStr): The password used to authenticate.
        private_key (SecretStr): The PEM used to authenticate.
        authenticator (str): The type of authenticator to use for initializing
            connection (oauth, externalbrowser, etc); refer to
            [Snowflake documentation](https://docs.snowflake.com/en/user-guide/python-connector-api.html#connect)
            for details, and note that `externalbrowser` will only
            work in an environment where a browser is available.
        token (SecretStr): The OAuth or JWT Token to provide when
            authenticator is set to OAuth.
        endpoint (str): The Okta endpoint to use when authenticator is
            set to `okta_endpoint`, e.g. `https://<okta_account_name>.okta.com`.
        role (str): The name of the default role to use.
        autocommit (bool): Whether to automatically commit.

    Example:
        Load stored Snowflake credentials:
        ```python
        from prefect_snowflake import SnowflakeCredentials

        snowflake_credentials_block = SnowflakeCredentials.load("BLOCK_NAME")
        ```
    """  # noqa E501

    _block_type_name = "Snowflake Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/bd359de0b4be76c2254bd329fe3a267a1a3879c2-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-snowflake/credentials/#prefect_snowflake.credentials.SnowflakeCredentials"  # noqa

    account: str = Field(
        ..., description="The snowflake account name.", example="nh12345.us-east-2.aws"
    )
    user: str = Field(..., description="The user name used to authenticate.")
    password: Optional[SecretStr] = Field(
        default=None, description="The password used to authenticate."
    )
    private_key: Optional[SecretBytes] = Field(
        default=None, description="The PEM used to authenticate."
    )
    private_key_path: Optional[Path] = Field(
        default=None, description="The path to the private key."
    )
    private_key_passphrase: Optional[SecretStr] = Field(
        default=None, description="The password to use for the private key."
    )
    authenticator: Literal[
        "snowflake",
        "snowflake_jwt",
        "externalbrowser",
        "okta_endpoint",
        "oauth",
        "username_password_mfa",
    ] = Field(  # noqa
        default="snowflake",
        description=("The type of authenticator to use for initializing connection."),
    )
    token: Optional[SecretStr] = Field(
        default=None,
        description=(
            "The OAuth or JWT Token to provide when authenticator is set to `oauth`."
        ),
    )
    endpoint: Optional[str] = Field(
        default=None,
        description=(
            "The Okta endpoint to use when authenticator is set to `okta_endpoint`."
        ),
    )
    role: Optional[str] = Field(
        default=None, description="The name of the default role to use."
    )
    autocommit: Optional[bool] = Field(
        default=None, description="Whether to automatically commit."
    )

    @root_validator(pre=True)
    def _validate_auth_kwargs(cls, values):
        """
        Ensure an authorization value has been provided by the user.
        """
        auth_params = (
            "password",
            "private_key",
            "private_key_path",
            "authenticator",
            "token",
        )
        if not any(values.get(param) for param in auth_params):
            auth_str = ", ".join(auth_params)
            raise ValueError(
                f"One of the authentication keys must be provided: {auth_str}\n"
            )
        elif values.get("private_key") and values.get("private_key_path"):
            raise ValueError(
                "Do not provide both private_key and private_key_path; select one."
            )
        elif values.get("password") and values.get("private_key_passphrase"):
            raise ValueError(
                "Do not provide both password and private_key_passphrase; "
                "specify private_key_passphrase only instead."
            )
        return values

    @root_validator(pre=True)
    def _validate_token_kwargs(cls, values):
        """
        Ensure an authorization value has been provided by the user.
        """
        authenticator = values.get("authenticator")
        token = values.get("token")
        if authenticator == "oauth" and not token:
            raise ValueError(
                "If authenticator is set to `oauth`, `token` must be provided"
            )
        return values

    @root_validator(pre=True)
    def _validate_okta_kwargs(cls, values):
        """
        Ensure an authorization value has been provided by the user.
        """
        authenticator = values.get("authenticator")

        # did not want to make a breaking change so we will allow both
        # see https://github.com/PrefectHQ/prefect-snowflake/issues/44
        if "okta_endpoint" in values.keys():
            warnings.warn(
                "Please specify `endpoint` instead of `okta_endpoint`; "
                "`okta_endpoint` will be removed March 31, 2023.",
                DeprecationWarning,
                stacklevel=2,
            )
            # remove okta endpoint from fields
            okta_endpoint = values.pop("okta_endpoint")
            if "endpoint" not in values.keys():
                values["endpoint"] = okta_endpoint

        endpoint = values.get("endpoint")
        if authenticator == "okta_endpoint" and not endpoint:
            raise ValueError(
                "If authenticator is set to `okta_endpoint`, "
                "`endpoint` must be provided"
            )
        return values

    def resolve_private_key(self) -> Optional[bytes]:
        """
        Converts a PEM encoded private key into a DER binary key.

        Returns:
            DER encoded key if private_key has been provided otherwise returns None.

        Raises:
            InvalidPemFormat: If private key is not in PEM format.
        """
        if self.private_key_path is None and self.private_key is None:
            return None
        elif self.private_key_path:
            private_key = self.private_key_path.read_bytes()
        else:
            private_key = self._decode_secret(self.private_key)

        if self.private_key_passphrase is not None:
            password = self._decode_secret(self.private_key_passphrase)
        elif self.password is not None:
            warnings.warn(
                "Using the password field for private_key is deprecated "
                "and will not work after March 31, 2023; please use "
                "private_key_passphrase instead",
                DeprecationWarning,
                stacklevel=2,
            )
            password = self._decode_secret(self.password)
        else:
            password = None

        composed_private_key = self._compose_pem(private_key)
        return load_pem_private_key(
            data=composed_private_key,
            password=password,
            backend=default_backend(),
        ).private_bytes(
            encoding=Encoding.DER,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )

    @staticmethod
    def _decode_secret(secret: Union[SecretStr, SecretBytes]) -> Optional[bytes]:
        """
        Decode the provided secret into bytes. If the secret is not a
        string or bytes, or it is whitespace, then return None.

        Args:
            secret: The value to decode.

        Returns:
            The decoded secret as bytes.

        """
        if isinstance(secret, (SecretBytes, SecretStr)):
            secret = secret.get_secret_value()

        if not isinstance(secret, (bytes, str)) or len(secret) == 0 or secret.isspace():
            return None

        return secret if isinstance(secret, bytes) else secret.encode()

    @staticmethod
    def _compose_pem(private_key: bytes) -> bytes:
        """Validate structure of PEM certificate.

        The original key passed from Prefect is sometimes malformed.
        This function recomposes the key into a valid key that will
        pass the serialization step when resolving the key to a DER.

        Args:
            private_key: A valid PEM format byte encoded string.

        Returns:
            byte encoded certificate.

        Raises:
            InvalidPemFormat: if private key is an invalid format.
        """
        pem_parts = re.match(_SIMPLE_PEM_CERTIFICATE_REGEX, private_key.decode())
        if pem_parts is None:
            raise InvalidPemFormat()

        body = "\n".join(re.split(r"\s+", pem_parts[2].strip()))
        # reassemble header+body+footer
        return f"{pem_parts[1]}\n{body}\n{pem_parts[3]}".encode()

    def get_client(
        self, **connect_kwargs: Any
    ) -> snowflake.connector.SnowflakeConnection:
        """
        Returns an authenticated connection that can be used to query
        Snowflake databases.

        Any additional arguments passed to this method will be used to configure
        the SnowflakeConnection. For available parameters, please refer to the
        [Snowflake Python connector documentation](https://docs.snowflake.com/en/user-guide/python-connector-api.html#connect).

        Args:
            **connect_kwargs: Additional arguments to pass to
                `snowflake.connector.connect`.

        Returns:
            An authenticated Snowflake connection.

        Example:
            Get Snowflake connection with only block configuration:
            ```python
            from prefect_snowflake import SnowflakeCredentials

            snowflake_credentials_block = SnowflakeCredentials.load("BLOCK_NAME")

            connection = snowflake_credentials_block.get_client()
            ```

            Get Snowflake connector scoped to a specified database:
            ```python
            from prefect_snowflake import SnowflakeCredentials

            snowflake_credentials_block = SnowflakeCredentials.load("BLOCK_NAME")

            connection = snowflake_credentials_block.get_client(database="my_database")
            ```
        """  # noqa
        connect_params = {
            # required to track task's usage in the Snowflake Partner Network Portal
            "application": "Prefect_Snowflake_Collection",
            **self.dict(exclude_unset=True, exclude={"block_type_slug"}),
            **connect_kwargs,
        }

        for key, value in connect_params.items():
            if isinstance(value, SecretField):
                connect_params[key] = connect_params[key].get_secret_value()

        # set authenticator to the actual okta_endpoint
        if connect_params.get("authenticator") == "okta_endpoint":
            endpoint = connect_params.pop("endpoint", None) or connect_params.pop(
                "okta_endpoint", None
            )  # okta_endpoint is deprecated
            connect_params["authenticator"] = endpoint

        private_der_key = self.resolve_private_key()
        if private_der_key is not None:
            connect_params["private_key"] = private_der_key
            connect_params.pop("password", None)
            connect_params.pop("private_key_passphrase", None)

        return snowflake.connector.connect(**connect_params)

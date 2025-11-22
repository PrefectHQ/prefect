"""Module to enable authenticate interactions with BitBucket."""

import re
from enum import Enum
from typing import Optional, Union
from urllib.parse import quote, urlparse, urlunparse

from pydantic import Field, SecretStr, field_validator

from prefect.blocks.abstract import CredentialsBlock

try:
    from atlassian.bitbucket import Bitbucket, Cloud
except ImportError:
    pass


def _quote_credential(value: str) -> str:
    """URL-encode a credential value for use in git URLs.

    Uses safe='' to encode ALL special characters including forward slashes,
    which is required for tokens that may contain base64 characters (+, /, =).
    """
    return quote(value, safe="")


class ClientType(Enum):
    """The client type to use."""

    LOCAL = "local"
    CLOUD = "cloud"


class BitBucketCredentials(CredentialsBlock):
    """Store BitBucket credentials to interact with private BitBucket repositories.

    Attributes:
        token: An access token to authenticate with BitBucket. This is required
            for accessing private repositories.
        username: Identification name unique across entire BitBucket site.
        password: The password to authenticate to BitBucket.
        url: The base URL of your BitBucket instance.


    Examples:
        Load stored BitBucket credentials:
        ```python
        from prefect_bitbucket import BitBucketCredentials
        bitbucket_credentials_block = BitBucketCredentials.load("BLOCK_NAME")
        ```


    """

    _block_type_name = "BitBucket Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/5d729f7355fb6828c4b605268ded9cfafab3ae4f-250x250.png"  # noqa

    token: Optional[SecretStr] = Field(
        title="Personal Access Token",
        default=None,
        description=(
            "A BitBucket Personal Access Token - required for private repositories."
        ),
        examples=["x-token-auth:my-token"],
    )
    username: Optional[str] = Field(
        default=None,
        description="Identification name unique across entire BitBucket site.",
    )
    password: Optional[SecretStr] = Field(
        default=None, description="The password to authenticate to BitBucket."
    )
    url: Optional[str] = Field(
        default=None,
        description="The base URL of a BitBucket instance. Leave blank for BitBucket Cloud.",
        examples=["https://api.bitbucket.org/"],
        title="URL",
    )

    @field_validator("username")
    def _validate_username(cls, value: str) -> str:
        """Allow common special characters used in Bitbucket usernames, such as email addresses."""
        pattern = r"^[A-Za-z0-9@._+-]+$"

        if not re.match(pattern, value):
            raise ValueError(
                "Username contains invalid characters. Allowed: letters, numbers, @ . _ + -"
            )
        if len(value) > 100:
            raise ValueError("Username cannot be longer than 100 characters.")
        return value

    def format_git_credentials(self, url: str) -> str:
        """
        Format and return the full git URL with BitBucket credentials embedded.

        BitBucket has different authentication formats:
        - BitBucket Server: username:token format required
        - BitBucket Cloud: x-token-auth:token prefix
        - Self-hosted instances: If username is provided, username:token format is used
          regardless of hostname (supports instances without 'bitbucketserver' in URL)

        Args:
            url: Repository URL (e.g., "https://bitbucket.org/org/repo.git")

        Returns:
            Complete URL with credentials embedded

        Raises:
            ValueError: If credentials are not properly configured
        """
        parsed = urlparse(url)

        # Get the token (prefer token field, fall back to password)
        token_value: Optional[str] = None
        if self.token:
            token_value = self.token.get_secret_value()
        elif self.password:
            token_value = self.password.get_secret_value()

        if not token_value:
            raise ValueError(
                "Token or password is required for BitBucket authentication"
            )

        # BitBucket Server requires username:token format
        if "bitbucketserver" in parsed.netloc:
            if not self.username:
                raise ValueError(
                    "Username is required for BitBucket Server authentication"
                )
            credentials = (
                f"{_quote_credential(self.username)}:{_quote_credential(token_value)}"
            )
        # If username is provided, use username:password auth
        # This supports self-hosted BitBucket Server instances that don't have
        # 'bitbucketserver' in their hostname
        elif self.username:
            credentials = (
                f"{_quote_credential(self.username)}:{_quote_credential(token_value)}"
            )
        # BitBucket Cloud uses x-token-auth: prefix
        # If token already has a colon or prefix, use as-is
        elif ":" in token_value:
            # Split and encode each part separately
            parts = token_value.split(":", 1)
            credentials = f"{_quote_credential(parts[0])}:{_quote_credential(parts[1])}"
        else:
            credentials = f"x-token-auth:{_quote_credential(token_value)}"

        # Insert credentials into URL
        return urlunparse(parsed._replace(netloc=f"{credentials}@{parsed.netloc}"))

    def get_client(
        self, client_type: Union[str, ClientType], **client_kwargs
    ) -> Union[Cloud, Bitbucket]:
        """Get an authenticated local or cloud Bitbucket client.

        Args:
            client_type: Whether to use a local or cloud client.

        Returns:
            An authenticated Bitbucket client.

        """
        # ref: https://atlassian-python-api.readthedocs.io/
        if isinstance(client_type, str):
            client_type = ClientType(client_type.lower())

        password = self.password.get_secret_value()
        input_client_kwargs = dict(
            url=self.url, username=self.username, password=password
        )
        input_client_kwargs.update(**client_kwargs)

        if client_type == ClientType.CLOUD:
            client = Cloud(**input_client_kwargs)
        else:
            client = Bitbucket(**input_client_kwargs)
        return client

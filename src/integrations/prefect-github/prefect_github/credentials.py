"""Credential classes used to perform authenticated interactions with GitHub"""

from typing import Optional

from pydantic import Field, SecretStr
from sgqlc.endpoint.http import HTTPEndpoint

from prefect.blocks.abstract import CredentialsBlock


class GitHubCredentials(CredentialsBlock):
    """
    Block used to manage GitHub authentication.

    Attributes:
        token: the token to authenticate into GitHub.

    Examples:
        Load stored GitHub credentials:
        ```python
        from prefect_github import GitHubCredentials
        github_credentials_block = GitHubCredentials.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "GitHub Credentials"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/41971cfecfea5f79ff334164f06ecb34d1038dd4-250x250.png"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-github/credentials/#prefect_github.credentials.GitHubCredentials"  # noqa

    token: Optional[SecretStr] = Field(
        default=None, description="A GitHub personal access token (PAT)."
    )

    def get_client(self) -> HTTPEndpoint:
        """
        Gets an authenticated GitHub GraphQL HTTPEndpoint client.

        Returns:
            An authenticated GitHub GraphQL HTTPEndpoint client.

        Example:
            Gets an authenticated GitHub GraphQL HTTPEndpoint client.
            ```python
            from prefect_github import GitHubCredentials

            github_credentials = GitHubCredentials(token=token)
            client = github_credentials.get_client()
            ```
        """

        if self.token is not None:
            base_headers = {"Authorization": f"Bearer {self.token.get_secret_value()}"}
        else:
            base_headers = None

        endpoint = HTTPEndpoint(
            "https://api.github.com/graphql", base_headers=base_headers
        )
        return endpoint

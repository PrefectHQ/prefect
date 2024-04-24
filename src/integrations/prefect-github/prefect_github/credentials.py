"""Credential classes used to perform authenticated interactions with GitHub"""

import warnings

from pydantic import VERSION as PYDANTIC_VERSION

from prefect.blocks.abstract import CredentialsBlock

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, SecretStr
else:
    from pydantic import Field, SecretStr

from sgqlc.endpoint.http import HTTPEndpoint


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

    token: SecretStr = Field(
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

    def get_endpoint(self) -> HTTPEndpoint:
        """
        Gets an authenticated GitHub GraphQL HTTPEndpoint.

        Returns:
            An authenticated GitHub GraphQL HTTPEndpoint

        Example:
            Gets an authenticated GitHub GraphQL HTTPEndpoint.
            ```python
            from prefect import flow
            from prefect_github import GitHubCredentials

            @flow
            def example_get_endpoint_flow():
                token = "token_xxxxxxx"
                github_credentials = GitHubCredentials(token=token)
                endpoint = github_credentials.get_endpoint()
                return endpoint

            example_get_endpoint_flow()
            ```
        """
        warnings.warn(
            "`get_endpoint` is deprecated and will be removed March 31st, 2023, "
            "use `get_client` instead.",
            DeprecationWarning,
        )
        return self.get_client()

"""Module used to enable authenticated interactions with GitLab"""

from typing import Optional

from gitlab import Gitlab
from pydantic import Field, SecretStr

from prefect.blocks.core import Block


class GitLabCredentials(Block):
    """
    Store a GitLab personal access token to interact with private GitLab
    repositories.

    Attributes:
        token: The personal access token to authenticate with GitLab.
        url: URL to self-hosted GitLab instances.

    Examples:
        Load stored GitLab credentials:
        ```python
        from prefect_gitlab import GitLabCredentials
        gitlab_credentials_block = GitLabCredentials.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "GitLab Credentials"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/55edIimT4g9gbjhkh5a3Sp/dfdb9391d8f45c2e93e72e3a4d350771/gitlab-logo-500.png?h=250"

    token: Optional[SecretStr] = Field(
        title="Personal Access Token",
        default=None,
        description="A GitLab Personal Access Token with read_repository scope.",
    )
    url: Optional[str] = Field(
        default=None, title="URL", description="URL to self-hosted GitLab instances."
    )

    def get_client(self) -> Gitlab:
        """
        Gets an authenticated GitLab client.

        Returns:
            An authenticated GitLab client.
        """
        # ref: https://python-gitlab.readthedocs.io/en/stable/
        gitlab = Gitlab(url=self.url, oauth_token=self.token.get_secret_value())
        gitlab.auth()
        return gitlab

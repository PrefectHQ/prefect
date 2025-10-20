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

    def format_git_credentials(self, url: str) -> str:
        """
        Format GitLab credentials for git URLs.

        Handles both personal access tokens and deploy tokens correctly:
        - Personal access tokens: prefixed with "oauth2:"
        - Deploy tokens (username:token format): used as-is
        - Already prefixed tokens: not double-prefixed

        Args:
            url: Repository URL (provided for context, not used by GitLab)

        Returns:
            Formatted credentials string

        Raises:
            ValueError: If token is not configured
        """
        if not self.token:
            raise ValueError("Token is required for GitLab authentication")

        token_value = self.token.get_secret_value()

        # Deploy token detection: contains ":" but not "oauth2:" prefix
        # Deploy tokens should not have oauth2: prefix (GitLab 16.3.4+ rejects them)
        # See: https://github.com/PrefectHQ/prefect/issues/10832
        if ":" in token_value and not token_value.startswith("oauth2:"):
            return token_value

        # Personal access token: add oauth2: prefix
        # See: https://github.com/PrefectHQ/prefect/issues/16836
        if not token_value.startswith("oauth2:"):
            return f"oauth2:{token_value}"

        # Already prefixed
        return token_value

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

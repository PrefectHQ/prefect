import pytest
from prefect_github import GitHubCredentials
from sgqlc.endpoint.http import HTTPEndpoint


@pytest.mark.parametrize("token", [None, "token_value"])
def test_github_credentials_get_client(token):
    endpoint = GitHubCredentials(token=token).get_client()
    assert isinstance(endpoint, HTTPEndpoint)
    if token is not None:
        assert endpoint.base_headers == {"Authorization": "Bearer token_value"}


def test_format_git_credentials():
    """Test that GitHub credentials return URL with token embedded."""
    credentials = GitHubCredentials(token="my-github-token")
    result = credentials.format_git_credentials("https://github.com/org/repo.git")
    assert result == "https://my-github-token@github.com/org/repo.git"


def test_format_git_credentials_no_token_raises():
    """Test that missing token raises ValueError."""
    credentials = GitHubCredentials()
    with pytest.raises(ValueError, match="Token is required for GitHub authentication"):
        credentials.format_git_credentials("https://github.com/org/repo.git")

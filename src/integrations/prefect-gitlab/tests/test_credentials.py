from unittest.mock import MagicMock

import pytest
from prefect_gitlab.credentials import GitLabCredentials


def test_gitlab_credentials_get_client(monkeypatch):
    mock_gitlab = MagicMock()
    monkeypatch.setattr("prefect_gitlab.credentials.Gitlab", mock_gitlab)
    gitlab_credentials = GitLabCredentials(
        url="https://gitlab.example.com", token="my-token"
    )
    gitlab_credentials.get_client()
    mock_gitlab.assert_called_once_with(
        url=gitlab_credentials.url,
        oauth_token=gitlab_credentials.token.get_secret_value(),
    )
    mock_gitlab.assert_called_once()


def test_format_git_credentials_personal_access_token():
    """Test that personal access tokens get oauth2: prefix and are embedded in URL."""
    credentials = GitLabCredentials(token="my-personal-token")
    result = credentials.format_git_credentials("https://gitlab.com/org/repo.git")
    assert result == "https://oauth2:my-personal-token@gitlab.com/org/repo.git"


def test_format_git_credentials_deploy_token():
    """Test that deploy tokens (username:token format) are used as-is in URL."""
    credentials = GitLabCredentials(token="deploy-user:deploy-token-value")
    result = credentials.format_git_credentials("https://gitlab.com/org/repo.git")
    assert result == "https://deploy-user:deploy-token-value@gitlab.com/org/repo.git"


def test_format_git_credentials_already_prefixed():
    """Test that already-prefixed tokens don't get double-prefixed in URL."""
    credentials = GitLabCredentials(token="oauth2:my-token")
    result = credentials.format_git_credentials("https://gitlab.com/org/repo.git")
    assert result == "https://oauth2:my-token@gitlab.com/org/repo.git"


def test_format_git_credentials_no_token_raises():
    """Test that missing token raises ValueError."""
    credentials = GitLabCredentials()
    with pytest.raises(ValueError, match="Token is required for GitLab authentication"):
        credentials.format_git_credentials("https://gitlab.com/org/repo.git")

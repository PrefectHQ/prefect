from unittest.mock import MagicMock

import pytest

try:
    from github import Github
except ImportError:
    Github = None

try:
    from gitlab import Gitlab
except ImportError:
    Gitlab = None


import prefect
from prefect.utilities.git import get_github_client, get_gitlab_client
from prefect.utilities.configuration import set_temporary_config


@pytest.mark.skipif(Github is None, reason="requires github extra")
class TestGetGitHubClient:
    def test_uses_context_secrets(self, monkeypatch):
        github = MagicMock()
        monkeypatch.setattr("prefect.utilities.git.Github", github)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GITHUB_ACCESS_TOKEN="ACCESS_TOKEN")):
                get_github_client()
        assert github.call_args[0][0] == "ACCESS_TOKEN"

    def test_prefers_passed_credentials_over_secrets(self, monkeypatch):
        github = MagicMock()
        monkeypatch.setattr("prefect.utilities.git.Github", github)
        desired_credentials = {"GITHUB_ACCESS_TOKEN": "PROVIDED_KEY"}
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GITHUB_ACCESS_TOKEN="ACCESS_TOKEN")):
                get_github_client(credentials=desired_credentials)
        assert github.call_args[0][0] == "PROVIDED_KEY"

    def test_creds_default_to_environment(self, monkeypatch):
        github = MagicMock()
        monkeypatch.setattr("prefect.utilities.git.Github", github)
        get_github_client()
        assert github.call_args[0][0] is None

        monkeypatch.setenv("GITHUB_ACCESS_TOKEN", "TOKEN")
        get_github_client()
        assert github.call_args[0][0] == "TOKEN"


@pytest.mark.skipif(Gitlab is None, reason="requires gitlab extra")
class TestGetGitLabClient:
    def test_uses_context_secrets(self, monkeypatch):
        gitlab = MagicMock()
        monkeypatch.setattr("prefect.utilities.git.Gitlab", gitlab)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GITLAB_ACCESS_TOKEN="ACCESS_TOKEN")):
                get_gitlab_client()
        assert gitlab.call_args.kwargs["private_token"] == "ACCESS_TOKEN"

    def test_prefers_passed_credentials_over_secrets(self, monkeypatch):
        gitlab = MagicMock()
        monkeypatch.setattr("prefect.utilities.git.Gitlab", gitlab)
        desired_credentials = {"GITLAB_ACCESS_TOKEN": "PROVIDED_KEY"}
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GITlab_ACCESS_TOKEN="ACCESS_TOKEN")):
                get_gitlab_client(credentials=desired_credentials)
        assert gitlab.call_args.kwargs["private_token"] == "PROVIDED_KEY"

    def test_creds_default_to_environment(self, monkeypatch):
        gitlab = MagicMock()
        monkeypatch.setattr("prefect.utilities.git.Gitlab", gitlab)
        get_gitlab_client()
        assert gitlab.call_args.kwargs["private_token"] is None

        monkeypatch.setenv("GITLAB_ACCESS_TOKEN", "TOKEN")
        get_gitlab_client()
        assert gitlab.call_args.kwargs["private_token"] == "TOKEN"

    def test_default_to_cloud(self, monkeypatch):
        gitlab = MagicMock()
        monkeypatch.setattr("prefect.utilities.git.Gitlab", gitlab)
        get_gitlab_client()
        assert gitlab.call_args.args[0] == "https://gitlab.com"

    def test_specify_host(self, monkeypatch):
        gitlab = MagicMock()
        monkeypatch.setattr("prefect.utilities.git.Gitlab", gitlab)
        get_gitlab_client(host="http://localhost:1234")
        assert gitlab.call_args.args[0] == "http://localhost:1234"

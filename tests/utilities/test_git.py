from unittest.mock import MagicMock

import pytest

pytest.importorskip("github")

import prefect
from prefect.utilities.git import get_github_client
from prefect.utilities.configuration import set_temporary_config


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
        assert github.call_args[0][0] == None

        monkeypatch.setenv("GITHUB_ACCESS_TOKEN", "TOKEN")
        get_github_client()
        assert github.call_args[0][0] == "TOKEN"

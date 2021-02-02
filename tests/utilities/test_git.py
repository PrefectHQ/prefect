import os
from unittest.mock import MagicMock

import pytest

import prefect
from prefect.utilities.git import (
    get_github_client,
    get_gitlab_client,
    get_bitbucket_client,
)
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture
def github(monkeypatch):
    pytest.importorskip("github")
    github = MagicMock()
    monkeypatch.setattr("github.Github", github)
    return github


def test_github_credentials_precedence(github, monkeypatch):
    key = "GITHUB_ACCESS_TOKEN"

    monkeypatch.delenv(key, raising=False)
    with prefect.context(secrets={}):
        # No token by default
        get_github_client()
        assert github.call_args[0][0] is None

        # Load from env if present
        monkeypatch.setenv(key, "from-env")
        get_github_client()
        assert github.call_args[0][0] == "from-env"

        # Load from local secrets if present
        prefect.context.secrets[key] = "from-secret"
        get_github_client()
        assert github.call_args[0][0] == "from-secret"

        # Load from credentials if present
        prefect.context.setdefault("credentials", {})[key] = "from-credentials"
        get_github_client()
        assert github.call_args[0][0] == "from-credentials"


@pytest.fixture
def gitlab(monkeypatch):
    pytest.importorskip("gitlab")
    gitlab = MagicMock()
    monkeypatch.setattr("gitlab.Gitlab", gitlab)
    return gitlab


def test_gitlab_credentials_precedence(gitlab, monkeypatch):
    key = "GITLAB_ACCESS_TOKEN"

    monkeypatch.delenv(key, raising=False)
    with prefect.context(secrets={}):
        # No token by default
        get_gitlab_client()
        assert gitlab.call_args[1]["private_token"] is None

        # Load from env if present
        monkeypatch.setenv(key, "from-env")
        get_gitlab_client()
        assert gitlab.call_args[1]["private_token"] == "from-env"

        # Load from local secrets if present
        prefect.context.secrets[key] = "from-secret"
        get_gitlab_client()
        assert gitlab.call_args[1]["private_token"] == "from-secret"

        # Load from credentials if present
        prefect.context.setdefault("credentials", {})[key] = "from-credentials"
        get_gitlab_client()
        assert gitlab.call_args[1]["private_token"] == "from-credentials"


@pytest.mark.parametrize("host", [None, "http://localhost:1234"])
def test_gitlab_hostname(gitlab, host):
    get_gitlab_client(host=host)
    expected = host or "https://gitlab.com"
    assert gitlab.call_args[0][0] == expected


@pytest.fixture
def bitbucket(monkeypatch):
    pytest.importorskip("atlassian")
    bitbucket = MagicMock()
    monkeypatch.setattr("atlassian.Bitbucket", bitbucket)
    return bitbucket


def test_bitbucket_credentials_precedence(bitbucket, monkeypatch):
    key = "BITBUCKET_ACCESS_TOKEN"

    def assert_token_used(token):
        header = bitbucket.call_args[1]["session"].headers["Authorization"]
        expected = f"Bearer {token or ''}"
        assert header == expected

    monkeypatch.delenv(key, raising=False)
    with prefect.context(secrets={}):
        # No token by default
        get_bitbucket_client()
        assert_token_used(None)

        # Load from env if present
        monkeypatch.setenv(key, "from-env")
        get_bitbucket_client()
        assert_token_used("from-env")

        # Load from local secrets if present
        prefect.context.secrets[key] = "from-secret"
        get_bitbucket_client()
        assert_token_used("from-secret")

        # Load from credentials if present
        prefect.context.setdefault("credentials", {})[key] = "from-credentials"
        get_bitbucket_client()
        assert_token_used("from-credentials")


@pytest.mark.parametrize("host", [None, "http://localhost:1234"])
def test_bitbucket_hostname(bitbucket, host):
    get_bitbucket_client(host=host)
    expected = host or "https://bitbucket.org"
    assert bitbucket.call_args[0][0] == expected

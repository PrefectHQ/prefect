from unittest.mock import MagicMock

import pytest

import prefect
from prefect.utilities.git import get_bitbucket_client


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

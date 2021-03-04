from unittest.mock import MagicMock

import pytest

pytest.importorskip("boto3")

import prefect
from prefect.utilities.aws import get_boto_client, _CLIENT_CACHE as CACHE
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture(autouse=True)
def clear_boto3_cache():
    CACHE.clear()


@pytest.fixture
def mock_boto3(monkeypatch):
    boto3 = MagicMock()
    monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
    return boto3


class TestGetBotoClient:
    def test_uses_context_secrets(self, mock_boto3):
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={
                        "ACCESS_KEY": "42",
                        "SECRET_ACCESS_KEY": "99",
                        "SESSION_TOKEN": "1",
                    }
                )
            ):
                get_boto_client(resource="myresource")
        kwargs = mock_boto3.client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
            "region_name": None,
        }

    def test_prefers_passed_credentials_over_secrets(self, mock_boto3):
        credentials = {
            "ACCESS_KEY": "pick",
            "SECRET_ACCESS_KEY": "these",
            "SESSION_TOKEN": "please",
        }
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={
                        "ACCESS_KEY": "dont",
                        "SECRET_ACCESS_KEY": "pick",
                        "SESSION_TOKEN": "these",
                    }
                )
            ):
                get_boto_client(resource="myresource", credentials=credentials)
        kwargs = mock_boto3.client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "pick",
            "aws_secret_access_key": "these",
            "aws_session_token": "please",
            "region_name": None,
        }

    def test_creds_default_to_environment(self, mock_boto3):
        get_boto_client(resource="myresource")
        kwargs = mock_boto3.client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": None,
            "aws_secret_access_key": None,
            "aws_session_token": None,
            "region_name": None,
        }

    def test_credentials_provided_in_kwargs(self, mock_boto3):
        get_boto_client(
            resource="myresource",
            aws_access_key_id="id",
            aws_secret_access_key="secret",
            aws_session_token="session",
        )
        kwargs = mock_boto3.client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "id",
            "aws_secret_access_key": "secret",
            "aws_session_token": "session",
            "region_name": None,
        }

    def test_credentials_does_not_duplicate_kwargs(self, mock_boto3):
        get_boto_client(
            resource="myresource",
            credentials={"ACCESS_KEY": "true_key", "SECRET_ACCESS_KEY": "true_secret"},
            aws_access_key_id="id",
            aws_secret_access_key="secret",
            aws_session_token="session",
        )
        kwargs = mock_boto3.client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "true_key",
            "aws_secret_access_key": "true_secret",
            "aws_session_token": "session",
            "region_name": None,
        }

    def test_session_used_if_profile_name_provided(self, mock_boto3):
        get_boto_client(resource="myresource", profile_name="TestProfile")
        session_kwargs = mock_boto3.session.Session.call_args[1]
        assert session_kwargs == {
            "botocore_session": None,
            "profile_name": "TestProfile",
            "region_name": None,
        }
        client = mock_boto3.session.Session.return_value.client

        args = client.call_args[0]
        assert args == ("myresource",)
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": None,
            "aws_secret_access_key": None,
            "aws_session_token": None,
            "region_name": None,
        }

    def test_client_cache(self, mock_boto3):
        class Client:
            pass

        mock_boto3.client.side_effect = lambda *a, **kw: Client()

        c1 = get_boto_client("myresource")
        assert len(CACHE) == 1

        # Cached if same parameters used
        c2 = get_boto_client("myresource")
        assert c2 is c1

        # Different parameters lead to unique client
        c3 = get_boto_client("myresource", region_name="a new region")
        assert c3 is not c1

        assert len(CACHE) == 2

        del c1, c2, c3
        assert len(CACHE) == 0

    def test_client_cache_not_used_extra_kwargs(self, mock_boto3):
        """If extra kwargs are passed to boto3, we skip the cache since we
        don't know how to interpret them"""
        mock_boto3.client.side_effect = lambda *args, **kws: MagicMock()

        c1 = get_boto_client("myresource", extra_kwarg="stuff")
        c2 = get_boto_client("myresource", extra_kwarg="stuff")
        assert len(CACHE) == 0
        assert c1 is not c2

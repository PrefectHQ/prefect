from unittest.mock import MagicMock

import pytest

pytest.importorskip("boto3")

import prefect
from prefect.utilities.aws import get_boto_client
from prefect.utilities.configuration import set_temporary_config


class TestGetBotoClient:
    def test_uses_context_secrets(self, monkeypatch):
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
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
                get_boto_client(resource="not a real resource")
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }

    def test_prefers_passed_credentials_over_secrets(self, monkeypatch):
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        desired_credentials = {
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
                get_boto_client(
                    resource="not a real resource", credentials=desired_credentials
                )
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "pick",
            "aws_secret_access_key": "these",
            "aws_session_token": "please",
        }

    def test_creds_default_to_environment(self, monkeypatch):
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        get_boto_client(resource="not a real resource")
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": None,
            "aws_secret_access_key": None,
            "aws_session_token": None,
        }

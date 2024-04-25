from unittest.mock import MagicMock

import pytest
from moto import mock_ec2
from prefect_aws.client_waiter import client_waiter

from prefect import flow


@pytest.fixture
def mock_waiter(monkeypatch):
    waiter = MagicMock(name="mock_waiter")
    monkeypatch.setattr(
        "prefect_aws.client_waiter.create_waiter_with_client",
        waiter,
    )
    return waiter


@pytest.fixture
def mock_client(monkeypatch, mock_waiter):
    client_mock = MagicMock(
        waiter_names=["instance_exists"], get_waiter=lambda waiter_name: mock_waiter
    )
    client_creator_mock = MagicMock(
        ClientCreator=lambda *args, **kwargs: MagicMock(
            create_client=lambda *args, **kwargs: client_mock
        )
    )
    monkeypatch.setattr("botocore.client", client_creator_mock)
    return client_creator_mock


@mock_ec2
def test_client_waiter_custom(mock_waiter, aws_credentials):
    @flow
    def test_flow():
        waiter = client_waiter(
            "batch",
            "JobExists",
            aws_credentials,
            waiter_definition={"waiters": {"JobExists": ["definition"]}, "version": 2},
        )
        return waiter

    test_flow()
    mock_waiter().wait.assert_called_once_with()


@mock_ec2
def test_client_waiter_custom_no_definition(mock_waiter, aws_credentials):
    @flow
    def test_flow():
        waiter = client_waiter("batch", "JobExists", aws_credentials)
        return waiter

    with pytest.raises(ValueError, match="The waiter name, JobExists"):
        test_flow()


@mock_ec2
def test_client_waiter_boto(mock_waiter, mock_client, aws_credentials):
    @flow
    def test_flow():
        waiter = client_waiter("ec2", "instance_exists", aws_credentials)
        return waiter

    test_flow()
    mock_waiter.wait.assert_called_once_with()

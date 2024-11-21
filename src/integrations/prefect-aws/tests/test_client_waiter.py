from unittest.mock import MagicMock

import pytest
from moto import mock_ec2
from prefect_aws.client_waiter import aclient_waiter, client_waiter

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


class TestClientWaiter:
    @mock_ec2
    def test_client_waiter_custom(self, mock_waiter, aws_credentials):
        @flow
        def test_flow():
            return client_waiter(
                "batch",
                "JobExists",
                aws_credentials,
                waiter_definition={
                    "waiters": {"JobExists": ["definition"]},
                    "version": 2,
                },
            )

        test_flow()
        mock_waiter().wait.assert_called_once_with()

    @mock_ec2
    def test_client_waiter_custom_no_definition(self, mock_waiter, aws_credentials):
        @flow
        def test_flow():
            return client_waiter("batch", "JobExists", aws_credentials)

        with pytest.raises(ValueError, match="The waiter name, JobExists"):
            test_flow()

    @mock_ec2
    def test_client_waiter_boto(self, mock_waiter, mock_client, aws_credentials):
        @flow
        def test_flow():
            return client_waiter("ec2", "instance_exists", aws_credentials)

        test_flow()
        mock_waiter.wait.assert_called_once_with()

    async def test_client_waiter_async_dispatch(
        self, mock_waiter, mock_client, aws_credentials
    ):
        @flow
        async def test_flow():
            return await client_waiter("ec2", "instance_exists", aws_credentials)

        await test_flow()
        mock_waiter.wait.assert_called_once_with()

    async def test_client_waiter_force_sync_from_async(
        self, mock_waiter, mock_client, aws_credentials
    ):
        client_waiter("ec2", "instance_exists", aws_credentials, _sync=True)
        mock_waiter.wait.assert_called_once_with()


class TestClientWaiterAsync:
    async def test_client_waiter_explicit_async(
        self, mock_waiter, mock_client, aws_credentials
    ):
        @flow
        async def test_flow():
            return await aclient_waiter("ec2", "instance_exists", aws_credentials)

        await test_flow()
        mock_waiter.wait.assert_called_once_with()

    async def test_aclient_waiter_custom(self, mock_waiter, aws_credentials):
        @flow
        async def test_flow():
            return await aclient_waiter(
                "batch",
                "JobExists",
                aws_credentials,
                waiter_definition={
                    "waiters": {"JobExists": ["definition"]},
                    "version": 2,
                },
            )

        await test_flow()
        mock_waiter().wait.assert_called_once_with()

    async def test_aclient_waiter_custom_no_definition(
        self, mock_waiter, aws_credentials
    ):
        @flow
        async def test_flow():
            return await aclient_waiter("batch", "JobExists", aws_credentials)

        with pytest.raises(ValueError, match="The waiter name, JobExists"):
            await test_flow()

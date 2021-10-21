import pytest

pytest.importorskip("boto3")

from unittest.mock import MagicMock

from botocore.waiter import WaiterModel
from prefect.tasks.aws import AWSClientWait


TEST_WAITERS = {
    "version": 2,
    "waiters": {
        "TestWaiter": {
            "delay": 5,
            "operation": "DescribeJobs",
            "maxAttempts": 100,
            "acceptors": [
                {
                    "argument": "jobs[].status",
                    "expected": "FAILED",
                    "matcher": "pathAll",
                    "state": "success",
                },
                {
                    "argument": "jobs[].status",
                    "expected": "SUCCEEDED",
                    "matcher": "pathAll",
                    "state": "success",
                },
            ],
        }
    },
}


@pytest.fixture
def boto_client(monkeypatch):
    boto_client = MagicMock()
    boto3 = MagicMock(client=MagicMock(return_value=boto_client))
    monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
    yield boto_client


def test_required_args():
    waiter = AWSClientWait(waiter_name="JobRunning")
    with pytest.raises(ValueError, match="An AWS client string"):
        waiter.run()

    waiter = AWSClientWait(client="batch")
    with pytest.raises(ValueError, match="A waiter name"):
        waiter.run()


def test_waiter_custom_definition(monkeypatch, boto_client):
    waiter = MagicMock()
    monkeypatch.setattr(
        "prefect.tasks.aws.client_waiter.create_waiter_with_client",
        MagicMock(return_value=waiter),
    )
    batch_wait_task = AWSClientWait(client="batch", waiter_definition=TEST_WAITERS)
    batch_wait_task.run(waiter_name="TestWaiter")

    assert waiter.wait.called

    batch_wait_task.run(
        waiter_name="TestWaiter",
        waiter_kwargs={"WaiterConfig": {"Delay": 20, "MaxAttempts": 300}},
    )
    _, kwargs = waiter.wait.call_args_list[1]
    assert kwargs["WaiterConfig"] == {"Delay": 20, "MaxAttempts": 300}


def test_boto_waiter(boto_client):
    boto_client.waiter_names = ["BotoWaiter"]
    waiter = MagicMock()
    boto_client.get_waiter = MagicMock(return_value=waiter)
    batch_wait_task = AWSClientWait(client="batch")
    batch_wait_task.run(
        waiter_name="BotoWaiter",
        waiter_kwargs={"WaiterConfig": {"Delay": 20, "MaxAttempts": 300}},
    )

    # Check waiter fetched from boto client
    args, _ = boto_client.get_waiter.call_args_list[0]
    assert args[0] == "BotoWaiter"

    # Check
    _, kwargs = waiter.wait.call_args_list[0]
    assert kwargs["WaiterConfig"] == {"Delay": 20, "MaxAttempts": 300}


def test_prefect_waiter_fail(boto_client):
    batch_wait_task = AWSClientWait(client="batch")

    with pytest.raises(ValueError, match="Unable to load waiter 'UnknownWaiter'"):
        batch_wait_task.run(waiter_name="UnknownWaiter")


def test_prefect_batch_waiters_success(monkeypatch, boto_client):
    batch_wait_task = AWSClientWait(client="batch")
    create_waiter_mock = MagicMock()
    monkeypatch.setattr(
        "prefect.tasks.aws.client_waiter.create_waiter_with_client", create_waiter_mock
    )

    for i, waiter_name in enumerate(["JobExists", "JobComplete", "JobRunning"]):
        batch_wait_task.run(waiter_name=waiter_name)
        args, _ = create_waiter_mock.call_args_list[i]
        assert args[0] == waiter_name
        assert isinstance(args[1], WaiterModel)
        assert len(args[1].waiter_names) == 3
        assert args[1].version == 2

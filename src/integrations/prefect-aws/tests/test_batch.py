from typing import Optional
from uuid import UUID

import boto3
import pytest
from moto import mock_batch, mock_iam
from prefect_aws.batch import abatch_submit, batch_submit

from prefect import flow


def assert_valid_job_id(job_id: Optional[str]):
    assert job_id is not None, "job_id is None"
    try:
        UUID(str(job_id))
        assert True, f"{job_id} is a valid UUID"
    except ValueError:
        assert False, f"{job_id} is not a valid UUID"


@pytest.fixture(scope="function")
def batch_client(aws_credentials):
    with mock_batch():
        yield boto3.client("batch", region_name="us-east-1")


@pytest.fixture(scope="function")
def iam_client(aws_credentials):
    with mock_iam():
        yield boto3.client("iam", region_name="us-east-1")


@pytest.fixture()
def job_queue_arn(iam_client, batch_client):
    iam_role = iam_client.create_role(
        RoleName="test_batch_client",
        AssumeRolePolicyDocument="string",
    )
    iam_arn = iam_role.get("Role").get("Arn")

    compute_environment = batch_client.create_compute_environment(
        computeEnvironmentName="test_batch_ce", type="UNMANAGED", serviceRole=iam_arn
    )

    compute_environment_arn = compute_environment.get("computeEnvironmentArn")

    created_queue = batch_client.create_job_queue(
        jobQueueName="test_batch_queue",
        state="ENABLED",
        priority=1,
        computeEnvironmentOrder=[
            {"order": 1, "computeEnvironment": compute_environment_arn},
        ],
    )
    job_queue_arn = created_queue.get("jobQueueArn")
    return job_queue_arn


@pytest.fixture
def job_definition_arn(batch_client):
    job_definition = batch_client.register_job_definition(
        jobDefinitionName="test_batch_jobdef",
        type="container",
        containerProperties={
            "image": "busybox",
            "vcpus": 1,
            "memory": 128,
            "command": ["sleep", "2"],
        },
    )
    job_definition_arn = job_definition.get("jobDefinitionArn")
    return job_definition_arn


class TestBatchSubmit:
    def test_batch_submit(self, job_queue_arn, job_definition_arn, aws_credentials):
        @flow
        def test_flow():
            return batch_submit(
                "batch_test_job",
                job_queue_arn,
                job_definition_arn,
                aws_credentials,
            )

        job_id = test_flow()

        assert_valid_job_id(job_id)

    async def test_batch_submit_async_dispatch(
        self, job_queue_arn, job_definition_arn, aws_credentials
    ):
        @flow
        async def test_flow():
            return await batch_submit(
                "batch_test_job",
                job_queue_arn,
                job_definition_arn,
                aws_credentials,
            )

        job_id = await test_flow()
        assert_valid_job_id(job_id)

    async def test_batch_submit_force_sync_from_async(
        self, job_queue_arn, job_definition_arn, aws_credentials
    ):
        job_id = batch_submit(
            "batch_test_job",
            job_queue_arn,
            job_definition_arn,
            aws_credentials,
            _sync=True,
        )
        assert_valid_job_id(job_id)


class TestBatchSubmitAsync:
    async def test_batch_submit_explicit_async(
        self, job_queue_arn, job_definition_arn, aws_credentials
    ):
        job_id = await abatch_submit(
            "batch_test_job",
            job_queue_arn,
            job_definition_arn,
            aws_credentials,
        )
        assert_valid_job_id(job_id)

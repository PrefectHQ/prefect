import pytest
from unittest.mock import MagicMock

pytest.importorskip("boto3")

from prefect.engine.signals import FAIL
from prefect.tasks.aws import BatchSubmit


@pytest.fixture
def batch_client(monkeypatch):
    batch_client = MagicMock()
    boto3 = MagicMock(client=MagicMock(return_value=batch_client))
    monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
    yield batch_client


class TestBatchSubmit:
    def test_initialization(self):
        task = BatchSubmit()

    def test_required_arguments(self):
        task = BatchSubmit(job_definition="job_def", job_queue="queue123")
        with pytest.raises(ValueError, match="A job name"):
            task.run()

        task = BatchSubmit(job_name="job_name", job_queue="queue123")
        with pytest.raises(ValueError, match="A job definition"):
            task.run()

        task = BatchSubmit(job_definition="job_def", job_name="job_name")
        with pytest.raises(ValueError, match="A job queue"):
            task.run()

    def test_submission_fail(self, batch_client):
        batch_client.submit_job = MagicMock(side_effect=RuntimeError("AWS issue"))

        task = BatchSubmit(
            job_definition="job_def", job_name="job_name", job_queue="queue123"
        )
        with pytest.raises(FAIL, match="Failed to submit job 'job_name'"):
            task.run()

    def test_invalid_response(self, batch_client):
        batch_client.submit_job = MagicMock(return_value={})

        task = BatchSubmit(
            job_definition="job_def", job_name="job_name", job_queue="queue123"
        )
        with pytest.raises(FAIL, match="no job ID"):
            task.run()

    def test_submit_success(self, batch_client):
        batch_client.submit_job = MagicMock(return_value={"jobId": "job123"})

        task = BatchSubmit(
            job_definition="job_def", job_name="job_name", job_queue="queue123"
        )
        task.run(batch_kwargs=dict(arrayProperties={"size": 123}))

        _, kwargs = batch_client.submit_job.call_args_list[0]
        assert kwargs["jobName"] == "job_name"
        assert kwargs["jobQueue"] == "queue123"
        assert kwargs["jobDefinition"] == "job_def"
        assert kwargs["arrayProperties"] == {"size": 123}

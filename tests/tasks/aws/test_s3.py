import pytest

from prefect.tasks.aws import S3DownloadTask, S3UploadTask


class TestS3DownloadTask:
    def test_initialization(self):
        task = S3DownloadTask()
        assert task.aws_credentials_secret == "AWS_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = S3DownloadTask(name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_raises_if_bucket_not_eventually_provided(self):
        task = S3DownloadTask()
        with pytest.raises(ValueError) as exc:
            task.run(key="")
        assert "bucket" in str(exc.value)


class TestS3UploadTask:
    def test_initialization(self):
        task = S3UploadTask()
        assert task.aws_credentials_secret == "AWS_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = S3UploadTask(name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_raises_if_bucket_not_eventually_provided(self):
        task = S3UploadTask()
        with pytest.raises(ValueError) as exc:
            task.run(data="")
        assert "bucket" in str(exc.value)

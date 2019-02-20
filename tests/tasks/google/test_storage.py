from prefect.tasks.google import GoogleCloudStorageTask


def test_initializes_with_bucket_and_sets_defaults():
    task = GoogleCloudStorageTask(bucket="")
    assert task.bucket == ""
    assert task.blob is None
    assert task.encryption_key_secret is None
    assert task.credentials_secret == "GOOGLE_APPLICATION_CREDENTIALS"
    assert task.project is None
    assert task.create_bucket is False

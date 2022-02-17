import json
from unittest.mock import MagicMock

import pytest

pytest.importorskip("boto3")

import prefect
from prefect.tasks.aws import AWSSecretsManager
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture
def mocked_boto_client(monkeypatch):
    boto3 = MagicMock()
    client = boto3.session.Session().client()
    boto3.client = MagicMock(return_value=client)
    monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
    return client


class TestAWSSecretsManager:
    def test_initialization(self):
        task = AWSSecretsManager("test")

    def test_initialization_passes_to_task_constructor(self):
        task = AWSSecretsManager(name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_raises_if_secret_not_eventually_provided(self):
        task = AWSSecretsManager()

        with pytest.raises(ValueError, match="secret"):
            task.run()

    def test_retrieve_plaintext_secret(self, mocked_boto_client):
        secret_value = "top-secret-string"

        def mocked_response(*args, **kwargs):
            return {
                "SecretString": f"{secret_value}",
            }

        task = AWSSecretsManager(secret="test")
        mocked_boto_client.get_secret_value.side_effect = mocked_response
        returned_data = task.run()

        assert returned_data == secret_value

    def test_retrieve_key_value_secret(self, mocked_boto_client):
        def mocked_response(*args, **kwargs):
            return {
                "SecretString": '{"Key":"top-secret-value"}',
            }

        task = AWSSecretsManager(secret="test")
        mocked_boto_client.get_secret_value.side_effect = mocked_response
        returned_data = task.run()
        expected_response = json.loads(mocked_response()["SecretString"])

        assert returned_data == expected_response

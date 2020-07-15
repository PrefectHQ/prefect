from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.aws import AWSSecretsManager
from prefect.utilities.configuration import set_temporary_config


class TestAWSSecretsManager:
    def test_initialization(self):
        task = AWSSecretsManager("test")

    def test_initialization_passes_to_task_constructor(self):
        task = AWSSecretsManager(secret_name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_raises_if_secret_not_eventually_provided(self):
        task = AWSSecretsManager(secret_name="test", tags=["AWS"])

        # TODO: I did not understand what this test tests (copied from S3Download)
        with pytest.raises(ValueError, match="secret_name"):
            task.run(name="")

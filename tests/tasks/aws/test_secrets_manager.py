from unittest.mock import MagicMock

import pytest

pytest.importorskip("boto3")

import prefect
from prefect.tasks.aws import AWSSecretsManager
from prefect.utilities.configuration import set_temporary_config


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

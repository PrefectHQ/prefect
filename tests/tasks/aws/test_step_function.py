from unittest.mock import MagicMock

import pytest

pytest.importorskip("boto3")

import prefect
from prefect.tasks.aws import StepActivate
from prefect.utilities.configuration import set_temporary_config


class TestStepActivate:
    def test_initialization(self):
        task = StepActivate(state_machine_arn="arn", execution_name="name")

    def test_initialization_passes_to_task_constructor(self):
        task = StepActivate(
            state_machine_arn="arn", execution_name="name", name="test", tags=["AWS"]
        )
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_exposes_boto3_start_execution_api(self, monkeypatch):
        task = StepActivate(state_machine_arn="arn", execution_name="name")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run()

        called_method = client.mock_calls[1]
        assert called_method[0] == "().start_execution"
        called_method.assert_called_once_with(
            {"stateMachineArn": "arn", "name": "name", "input": {}}
        )

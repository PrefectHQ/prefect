from unittest.mock import MagicMock

import pytest

pytest.importorskip("boto3")

from prefect.tasks.aws import StepActivate


class TestStepActivate:
    def test_initialization(self):
        task = StepActivate(state_machine_arn="arn")

    def test_initialization_passes_to_task_constructor(self):
        task = StepActivate(state_machine_arn="arn", name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_exposes_boto3_start_execution_api(self, monkeypatch):
        task = StepActivate(state_machine_arn="arn")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run(execution_name="name")

        called_method = client.mock_calls[1]
        assert called_method[0] == "().start_execution"
        assert called_method[2] == {
            "stateMachineArn": "arn",
            "name": "name",
            "input": "{}",
        }

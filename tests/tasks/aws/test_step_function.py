from unittest.mock import MagicMock

import pytest

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

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = StepActivate(state_machine_arn="arn", execution_name="name")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={
                        "ACCESS_KEY": "42",
                        "SECRET_ACCESS_KEY": "99",
                        "SESSION_TOKEN": "1",
                    }
                )
            ):
                task.run()
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }

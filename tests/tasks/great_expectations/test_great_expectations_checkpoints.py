from unittest.mock import MagicMock
import prefect
from prefect import context
from prefect.tasks.great_expectations import RunGreatExpectationsCheckpoint
from prefect.utilities.configuration import set_temporary_config
import pytest
import os


class TestInitialization:
    def test_inits_with_no_args(self):
        t = RunGreatExpectationsCheckpoint()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = RunGreatExpectationsCheckpoint(
            checkpoint_name="checkpoint",
            context_root_dir="/path/to/somewhere",
            runtime_environment={
                "plugins_directory": "/path/to/plugins/somewhere/else"
            },
        )
        assert t.checkpoint_name == "checkpoint"
        assert t.context_root_dir == "/path/to/somewhere"
        assert t.runtime_environment == {
            "plugins_directory": "/path/to/plugins/somewhere/else"
        }

    def test_raises_if_checkpoint_not_provided(self, monkeypatch):
        task = RunGreatExpectationsCheckpoint()
        client = MagicMock()
        jira = MagicMock(client=client)
        monkeypatch.setattr(
            "prefect.tasks.great_expectations.checkpoints", great_expectations
        )
        with pytest.raises(ValueError, match="checkpoint"):
            task.run()


@pytest.fixture
def example_context_root_dir():
    """
    Forwards the root dir for a great expectations configuration directory in the examples.
    """
    return os.path.abspath(
        "examples/task_library/great_expectations/great_expectations/"
    )


class TestIntegrationWithLocalConfig:
    def test_runs_with_different_context_root_dir(self, example_context_root_dir):
        t = RunGreatExpectationsCheckpoint(
            "warning_npi_checkpoint", context_root_dir=example_context_root_dir
        )

        with prefect.context(task_id="random"):
            result = t.run()

        assert result["success"]

    def test_raises_if_validation_fails(self, example_context_root_dir):
        t = RunGreatExpectationsCheckpoint(
            "guaranteed_failure_npi_checkpoint",
            context_root_dir=example_context_root_dir,
        )

        with pytest.raises(prefect.engine.signals.VALIDATIONFAIL):
            result = t.run()

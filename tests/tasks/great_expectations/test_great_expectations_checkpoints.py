from unittest.mock import MagicMock
import prefect
from prefect import context
from prefect.tasks.great_expectations import RunGreatExpectationsCheckpoint
from prefect.utilities.configuration import set_temporary_config
import pytest
import os
import shutil
import tempfile


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
            run_name="woooo",
        )
        assert t.checkpoint_name == "checkpoint"
        assert t.context_root_dir == "/path/to/somewhere"
        assert t.runtime_environment == {
            "plugins_directory": "/path/to/plugins/somewhere/else"
        }
        assert t.run_name == "woooo"

    def test_raises_if_checkpoint_not_provided(self, monkeypatch):
        task = RunGreatExpectationsCheckpoint()
        client = MagicMock()
        great_expectations = MagicMock(client=client)
        monkeypatch.setattr("prefect.tasks.great_expectations", great_expectations)
        with pytest.raises(ValueError, match="checkpoint"):
            task.run()


@pytest.fixture(scope="session")
def example_context_root_dir():
    """
    Copies the examples configuration directory to the proper location for the test and exposes its path for the test.
    """
    with tempfile.TemporaryDirectory() as tmp:
        examples_path = os.path.abspath(
            "examples/task_library/great_expectations/great_expectations/"
        )
        shutil.copytree(examples_path, tmp, dirs_exist_ok=True)
        yield tmp


@pytest.mark.skipif("sys.version_info <= (3,8)")
class TestIntegrationWithLocalConfig:
    """
    Integration test to check the task library task still integrates with how Great Expectations checkpoints are configured.
    This only runs on 3.8 since it uses a shutil kwarg (dirs_exist_ok) only available in 3.8+ for the purposes of the test.
    """

    def test_runs_with_different_context_root_dir(self, example_context_root_dir):
        t = RunGreatExpectationsCheckpoint(
            "warning_npi_checkpoint_circle", context_root_dir=example_context_root_dir
        )

        result = t.run()

        assert result["success"]

    def test_raises_if_validation_fails(self, example_context_root_dir):
        t = RunGreatExpectationsCheckpoint(
            "guaranteed_failure_npi_checkpoint_circle",
            context_root_dir=example_context_root_dir,
        )

        with pytest.raises(prefect.engine.signals.VALIDATIONFAIL):
            result = t.run()

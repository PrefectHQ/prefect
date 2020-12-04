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
            context=1234,
            assets_to_validate=["assets"],
            batch_kwargs={"kwargs": "here"},
            expectation_suite_name="name",
            get_checkpoint_from_context=True,
            context_root_dir="/path/to/somewhere",
            runtime_environment={
                "plugins_directory": "/path/to/plugins/somewhere/else"
            },
            run_name="1234",
            run_info_at_end=False,
            disable_markdown_artifact=True,
        )
        assert t.checkpoint_name == "checkpoint"
        assert t.context == 1234
        assert t.assets_to_validate == ["assets"]
        assert t.batch_kwargs == {"kwargs": "here"}
        assert t.expectation_suite_name == "name"
        assert t.get_checkpoint_from_context == True
        assert t.context_root_dir == "/path/to/somewhere"
        assert t.runtime_environment == {
            "plugins_directory": "/path/to/plugins/somewhere/else"
        }
        assert t.run_name == "1234"
        assert t.run_info_at_end == False
        assert t.disable_markdown_artifact == True

    def test_raises_if_checkpoint_not_provided(self, monkeypatch):
        task = RunGreatExpectationsCheckpoint()
        client = MagicMock()
        great_expectations = MagicMock(client=client)
        monkeypatch.setattr("prefect.tasks.great_expectations", great_expectations)
        with pytest.raises(ValueError, match="checkpoint"):
            task.run()

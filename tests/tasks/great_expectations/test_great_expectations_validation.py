from unittest.mock import MagicMock
import prefect
from prefect import context
from prefect.tasks.great_expectations import RunGreatExpectationsValidation
from prefect.utilities.configuration import set_temporary_config
import pytest
import os
import shutil
import tempfile


class TestInitialization:
    def test_inits_with_no_args(self):
        t = RunGreatExpectationsValidation()
        assert t

    def test_kwargs_get_passed_to_task_init(self):
        t = RunGreatExpectationsValidation(
            checkpoint_name="checkpoint",
            context=1234,
            assets_to_validate=["assets"],
            batch_kwargs={"kwargs": "here"},
            expectation_suite_name="name",
            context_root_dir="/path/to/somewhere",
            runtime_environment={
                "plugins_directory": "/path/to/plugins/somewhere/else"
            },
            run_name="1234",
            run_info_at_end=False,
            disable_markdown_artifact=True,
            evaluation_parameters=dict(prev_run_row_count=100),
        )
        assert t.checkpoint_name == "checkpoint"
        assert t.context == 1234
        assert t.assets_to_validate == ["assets"]
        assert t.batch_kwargs == {"kwargs": "here"}
        assert t.expectation_suite_name == "name"
        assert t.context_root_dir == "/path/to/somewhere"
        assert t.runtime_environment == {
            "plugins_directory": "/path/to/plugins/somewhere/else"
        }
        assert t.run_name == "1234"
        assert t.run_info_at_end == False
        assert t.disable_markdown_artifact == True
        assert t.evaluation_parameters == dict(prev_run_row_count=100)

    def test_raises_if_params_not_mutually_exclusive(self):
        task = RunGreatExpectationsValidation(context="test")
        with pytest.raises(ValueError, match="Exactly"):
            task.run()

        with pytest.raises(ValueError, match="Exactly"):
            task.run(expectation_suite_name="name")

        with pytest.raises(ValueError, match="Exactly"):
            task.run(batch_kwargs={"here"})

        with pytest.raises(ValueError, match="Exactly"):
            task.run(
                expectation_suite_name="name",
                batch_kwargs={"here"},
                assets_to_validate=["val"],
            )

        with pytest.raises(ValueError, match="Exactly"):
            task.run(assets_to_validate=["val"], checkpoint_name="name")

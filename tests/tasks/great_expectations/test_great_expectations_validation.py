from great_expectations.validation_operators.types.validation_operator_result import (
    ValidationOperatorResult,
)
from great_expectations.checkpoint.checkpoint import CheckpointResult
from prefect.tasks.great_expectations import RunGreatExpectationsValidation
import pytest
from pathlib import Path
from prefect.engine import signals
import great_expectations as ge


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

    def test_assets_to_validate(self):
        context = ge.DataContext(
            context_root_dir=str(Path(__file__).parent.resolve() / "v2_api")
        )
        task = RunGreatExpectationsValidation(
            context=context,
            assets_to_validate=[
                context.get_batch(
                    {
                        "path": "tests/tasks/great_expectations/data/yellow_tripdata_sample_2019-01.csv",
                        "datasource": "data__dir",
                        "data_asset_name": "yellow_tripdata_sample_2019-01",
                    },
                    "taxi.demo",
                )
            ],
        )
        results = task.run()
        assert type(results) is ValidationOperatorResult

    def test_suite_name_with_batch_kwargs(self):
        task = RunGreatExpectationsValidation(
            context_root_dir=str(Path(__file__).parent.resolve() / "v2_api"),
            batch_kwargs={
                "path": "tests/tasks/great_expectations/data/yellow_tripdata_sample_2019-01.csv",
                "datasource": "data__dir",
                "data_asset_name": "yellow_tripdata_sample_2019-01",
            },
            expectation_suite_name="taxi.demo",
        )
        results = task.run()
        assert type(results) is ValidationOperatorResult

    def test_v2_checkpoint_api(self):
        task = RunGreatExpectationsValidation(
            context_root_dir=str(Path(__file__).parent.resolve() / "v2_api"),
            checkpoint_name="my_chk",
        )
        results = task.run()
        assert type(results) is ValidationOperatorResult

    def test_v3_checkpoint_api_pass(self):
        task = RunGreatExpectationsValidation(
            context_root_dir=str(Path(__file__).parent.resolve() / "v3_api"),
            checkpoint_name="my_checkpoint_pass",
        )
        results = task.run()
        assert type(results) is CheckpointResult

    def test_v3_checkpoint_api_fail(self):
        task = RunGreatExpectationsValidation(
            context_root_dir=str(Path(__file__).parent.resolve() / "v3_api"),
            checkpoint_name="my_checkpoint_fail",
        )
        with pytest.raises(signals.FAIL):
            task.run()

import os
from pathlib import Path

import great_expectations as ge
import pandas as pd
import pytest
from great_expectations.checkpoint.checkpoint import CheckpointResult
from great_expectations.core.batch import RuntimeBatchRequest
from great_expectations.data_context import BaseDataContext
from great_expectations.data_context.types.base import (
    CheckpointConfig,
    DataContextConfig,
)
from great_expectations.data_context.util import instantiate_class_from_config
from great_expectations.validation_operators.types.validation_operator_result import (
    ValidationOperatorResult,
)

from prefect.engine import signals
from prefect.tasks.great_expectations import RunGreatExpectationsValidation

PARENT_PATH = Path(__file__).parent.resolve()
DATA_PATH = PARENT_PATH / "data"
V2_API_PATH = PARENT_PATH / "v2_api"
V3_API_PATH = PARENT_PATH / "v3_api"


@pytest.fixture(autouse=True)
def disable_usage_stats(monkeypatch):
    monkeypatch.setenv("GE_USAGE_STATS", "FALSE")


@pytest.fixture()
def in_memory_data_context():
    data_context = BaseDataContext(
        project_config=DataContextConfig(
            **{
                "config_version": 3.0,
                "datasources": {
                    "data__dir": {
                        "module_name": "great_expectations.datasource",
                        "data_connectors": {
                            "data__dir_example_data_connector": {
                                "default_regex": {
                                    "group_names": ["data_asset_name"],
                                    "pattern": "(.*)",
                                },
                                "base_directory": str(DATA_PATH),
                                "module_name": "great_expectations.datasource.data_connector",
                                "class_name": "InferredAssetFilesystemDataConnector",
                            },
                            "default_runtime_data_connector_name": {
                                "batch_identifiers": ["default_identifier_name"],
                                "module_name": "great_expectations.datasource.data_connector",
                                "class_name": "RuntimeDataConnector",
                            },
                        },
                        "execution_engine": {
                            "module_name": "great_expectations.execution_engine",
                            "class_name": "PandasExecutionEngine",
                        },
                        "class_name": "Datasource",
                    }
                },
                "config_variables_file_path": os.path.join(
                    str(V3_API_PATH), "uncommitted", "config_variables.yml"
                ),
                "stores": {
                    "expectations_store": {
                        "class_name": "ExpectationsStore",
                        "store_backend": {
                            "class_name": "TupleFilesystemStoreBackend",
                            "base_directory": os.path.join(
                                str(V3_API_PATH), "expectations"
                            ),
                        },
                    },
                    "validations_store": {
                        "class_name": "ValidationsStore",
                        "store_backend": {
                            "class_name": "TupleFilesystemStoreBackend",
                            "base_directory": os.path.join(
                                str(V3_API_PATH), "uncommitted", "validations"
                            ),
                        },
                    },
                    "evaluation_parameter_store": {
                        "class_name": "EvaluationParameterStore"
                    },
                    "checkpoint_store": {
                        "class_name": "CheckpointStore",
                        "store_backend": {
                            "class_name": "TupleFilesystemStoreBackend",
                            "suppress_store_backend_id": True,
                            "base_directory": os.path.join(
                                str(V3_API_PATH), "checkpoints"
                            ),
                        },
                    },
                },
                "expectations_store_name": "expectations_store",
                "validations_store_name": "validations_store",
                "evaluation_parameter_store_name": "evaluation_parameter_store",
                "checkpoint_store_name": "checkpoint_store",
                "data_docs_sites": {
                    "local_site": {
                        "class_name": "SiteBuilder",
                        "show_how_to_buttons": True,
                        "store_backend": {
                            "class_name": "TupleFilesystemStoreBackend",
                            "base_directory": os.path.join(
                                str(V3_API_PATH),
                                "uncommitted",
                                "data_docs",
                                "local_site",
                            ),
                        },
                        "site_index_builder": {"class_name": "DefaultSiteIndexBuilder"},
                    }
                },
                "anonymous_usage_statistics": {
                    "data_context_id": "abcdabcd-1111-2222-3333-abcdabcdabcd",
                    "enabled": False,
                },
                "notebooks": None,
                "concurrency": {"enabled": False},
            }
        )
    )

    return data_context


@pytest.fixture
def in_memory_checkpoint():
    checkpoint = instantiate_class_from_config(
        config=CheckpointConfig(
            **{
                "name": "taxi.pass.from_config",
                "config_version": 1.0,
                "template_name": None,
                "module_name": "great_expectations.checkpoint",
                "class_name": "Checkpoint",
                "run_name_template": "%Y%m%d-%H%M%S-my-run-name-template",
                "expectation_suite_name": None,
                "batch_request": None,
                "action_list": [
                    {
                        "name": "store_validation_result",
                        "action": {"class_name": "StoreValidationResultAction"},
                    },
                    {
                        "name": "store_evaluation_params",
                        "action": {"class_name": "StoreEvaluationParametersAction"},
                    },
                    {
                        "name": "update_data_docs",
                        "action": {
                            "class_name": "UpdateDataDocsAction",
                            "site_names": [],
                        },
                    },
                ],
                "evaluation_parameters": {},
                "runtime_configuration": {},
                "validations": [
                    {
                        "batch_request": {
                            "datasource_name": "data__dir",
                            "data_connector_name": "data__dir_example_data_connector",
                            "data_asset_name": "yellow_tripdata_sample_2019-01.csv",
                            "data_connector_query": {"index": -1},
                        },
                        "expectation_suite_name": "taxi.demo_pass",
                    }
                ],
                "profilers": [],
                "ge_cloud_id": None,
                "expectation_suite_ge_cloud_id": None,
            }
        ).to_json_dict(),
        runtime_environment={
            "data_context": ge.DataContext(
                context_root_dir=str(V3_API_PATH),
            )
        },
        config_defaults={"module_name": "great_expectations.checkpoint"},
    )
    return checkpoint


@pytest.fixture
def in_memory_runtime_batch_request():
    df = pd.read_csv(DATA_PATH / "yellow_tripdata_sample_2019-02.csv")
    return RuntimeBatchRequest(
        datasource_name="data__dir",
        data_connector_name="default_runtime_data_connector_name",
        data_asset_name="yellow_tripdata_sample_2019-02_df",
        runtime_parameters={"batch_data": df},
        batch_identifiers={
            "default_identifier_name": "ingestion step 1",
        },
    )


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
        context = ge.DataContext(context_root_dir=str(V2_API_PATH))
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
            context_root_dir=str(V2_API_PATH),
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
            context_root_dir=str(V2_API_PATH),
            checkpoint_name="my_chk",
        )
        results = task.run()
        assert type(results) is ValidationOperatorResult

    def test_v3_checkpoint_api_pass(self):
        task = RunGreatExpectationsValidation(
            context_root_dir=str(V3_API_PATH),
            checkpoint_name="my_checkpoint_pass",
        )
        results = task.run()
        assert type(results) is CheckpointResult

    def test_v3_checkpoint_api_fail(self):
        task = RunGreatExpectationsValidation(
            context_root_dir=str(V3_API_PATH),
            checkpoint_name="my_checkpoint_fail",
        )
        with pytest.raises(signals.FAIL):
            task.run()

    def test_v3_with_checkpoint_config(self, in_memory_checkpoint):
        task = RunGreatExpectationsValidation(
            ge_checkpoint=in_memory_checkpoint,
            context_root_dir=str(V3_API_PATH),
        )
        results = task.run()
        assert type(results) is CheckpointResult

    def test_v3_with_runtime_data_frame(
        self, in_memory_runtime_batch_request, in_memory_data_context
    ):
        task = RunGreatExpectationsValidation(
            checkpoint_name="my_checkpoint_pass",
            context=in_memory_data_context,
            checkpoint_kwargs={
                "validations": [
                    {
                        "batch_request": in_memory_runtime_batch_request,
                        "expectation_suite_name": "taxi.demo_pass",
                    }
                ]
            },
        )
        results = task.run()
        assert type(results) is CheckpointResult

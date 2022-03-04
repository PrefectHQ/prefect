import pytest

from prefect.tasks.transform import TrasformCreateMaterialization


class TestTransformCreateMaterialization:
    def test_construction_without_values(self):
        transform_task = TrasformCreateMaterialization()

        assert transform_task.api_key is None
        assert transform_task.api_key_env_var is None
        assert transform_task.mql_server_url is None
        assert transform_task.mql_server_url_env_var is None
        assert transform_task.model_key_id is None
        assert transform_task.materialization_name is None
        assert transform_task.start_time is None
        assert transform_task.end_time is None
        assert transform_task.output_table is None
        assert transform_task.force is False
        assert transform_task.use_async is False

    def test_construction_with_values(self):
        transform_task = TrasformCreateMaterialization(
            api_key="key",
            api_key_env_var="key_env_var",
            mql_server_url="url",
            mql_server_url_env_var="url_env_var",
            model_key_id=1,
            materialization_name="mt_name",
            start_time="1900-01-01",
            end_time="1900-01-01",
            output_table="out_table",
            force=True,
            use_async=True
        )

        assert transform_task.api_key == "key"
        assert transform_task.api_key_env_var == "key_env_var"
        assert transform_task.mql_server_url == "url"
        assert transform_task.mql_server_url_env_var == "url_env_var"
        assert transform_task.model_key_id == 1
        assert transform_task.materialization_name == "mt_name"
        assert transform_task.start_time == "1900-01-01"
        assert transform_task.end_time == "1900-01-01"
        assert transform_task.output_table == "out_table"
        assert transform_task.force is True
        assert transform_task.use_async is True
import pytest

from prefect.tasks.transform import TrasformCreateMaterialization


class TestTransformCreateMaterialization:
    def test_construction_no_args(self):
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

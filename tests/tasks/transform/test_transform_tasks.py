import pytest

from prefect.tasks.transform import TransformCreateMaterialization


class TestTransformCreateMaterialization:
    def test_construction_without_values(self):
        transform_task = TransformCreateMaterialization()

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
        transform_task = TransformCreateMaterialization(
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
            use_async=True,
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

    def test_run_raises_with_missing_api_key_and_env_var(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "Both `api_key` and `api_key_env_var` are missing."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run()

    def test_run_raises_with_missing_api_key_and_env_var_not_found(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "`api_key` is missing and `api_key_env_var` was not found in environment variables."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run(api_key_env_var="key_env_var")

    def test_run_raises_with_missing_mql_server_url_and_env_var(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "Both `mql_server_url` and `mql_server_url_env_var` are missing."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run(api_key="key")

    def test_run_raises_with_missing_mql_server_url_and_env_var_not_found(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "`mql_server_url` is missing and `mql_server_url_env_var` was not found in environment variables."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run(
                api_key="key", mql_server_url_env_var="mql_server_url_env_var"
            )

    def test_run_raises_with_missing_materialization_name(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "`materialization_name` is missing."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run(api_key="key", mql_server_url="url")

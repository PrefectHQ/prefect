import pytest
from unittest import mock
from typing import Optional
from transform.models import MqlQueryStatusResp, MqlQueryStatus, MqlMaterializeResp
from transform.exceptions import QueryRuntimeException

from prefect.engine.signals import FAIL
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
        assert transform_task.wait_for_creation is True

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
            wait_for_creation=False,
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
        assert transform_task.wait_for_creation is False

    def test_run_raises_with_missing_api_key_and_env_var(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "Both `api_key` and `api_key_env_var` are missing."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run()

    def test_run_raises_with_missing_api_key_and_env_var_not_found(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "`api_key` is missing and `api_key_env_var` not found in env vars."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run(api_key_env_var="key_env_var")

    def test_run_raises_with_missing_mql_server_url_and_env_var(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "Both `mql_server_url` and `mql_server_url_env_var` are missing."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run(api_key="key")

    def test_run_raises_with_missing_mql_server_url_and_env_var_not_found(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "`mql_server_url` is missing and `mql_server_url_env_var` not found in env vars."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run(
                api_key="key", mql_server_url_env_var="mql_server_url_env_var"
            )

    def test_run_raises_with_missing_materialization_name(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "`materialization_name` is missing."
        with pytest.raises(ValueError, match=msg_match):
            transform_task.run(api_key="key", mql_server_url="url")

    def test_run_raises_on_connection_exception(self):
        transform_task = TransformCreateMaterialization()

        msg_match = "Cannot connect to Transform server!"
        with pytest.raises(FAIL, match=msg_match):
            transform_task.run(
                api_key="key", mql_server_url="url", materialization_name="mt_name"
            )

    @mock.patch("prefect.tasks.transform.transform_tasks.MQLClient")
    def test_run_raises_on_create_materialization_async(self, mock_mql_client):
        error_msg = "Error while creating async materialization!"

        class MockMQLClient:
            def create_materialization(
                materialization_name: str,
                start_time: Optional[str] = None,
                end_time: Optional[str] = None,
                model_key_id: Optional[int] = None,
                output_table: Optional[str] = None,
                force: bool = False,
            ):
                return MqlQueryStatusResp(
                    query_id="xyz",
                    status=MqlQueryStatus.FAILED,
                    sql="sql_query",
                    error=error_msg,
                    chart_value_max=None,
                    chart_value_min=None,
                    result=None,
                    result_primary_time_granularity=None,
                    result_source=None,
                )

        mock_mql_client.return_value = MockMQLClient
        transform_task = TransformCreateMaterialization()

        msg_match = (
            f"Transform materialization async creation failed! Error is: {error_msg}"
        )
        with pytest.raises(FAIL, match=msg_match):
            transform_task.run(
                api_key="key",
                mql_server_url="url",
                materialization_name="mt_name",
                wait_for_creation=False,
            )

    @mock.patch("prefect.tasks.transform.transform_tasks.MQLClient")
    def test_run_raises_on_create_materialization_sync(self, mock_mql_client):
        error_msg = "Error while creating sync materialization!"

        class MockMQLClient:
            def materialize(
                materialization_name: str,
                start_time: Optional[str] = None,
                end_time: Optional[str] = None,
                model_key_id: Optional[int] = None,
                output_table: Optional[str] = None,
                force: bool = False,
                timeout: Optional[int] = None,
            ):
                raise QueryRuntimeException(query_id="xyz", msg=error_msg)

        mock_mql_client.return_value = MockMQLClient
        transform_task = TransformCreateMaterialization()

        msg_match = (
            f"Transform materialization sync creation failed! Error is: {error_msg}"
        )
        with pytest.raises(FAIL, match=msg_match):
            transform_task.run(
                api_key="key", mql_server_url="url", materialization_name="mt_name"
            )

    @mock.patch("prefect.tasks.transform.transform_tasks.MQLClient")
    def test_run_on_create_materialization_async_successful_status(
        self, mock_mql_client
    ):
        class MockMQLClient:
            def create_materialization(
                materialization_name: str,
                start_time: Optional[str] = None,
                end_time: Optional[str] = None,
                model_key_id: Optional[int] = None,
                output_table: Optional[str] = None,
                force: bool = False,
            ):
                return MqlQueryStatusResp(
                    query_id="xyz",
                    status=MqlQueryStatus.SUCCESSFUL,
                    sql="sql_query",
                    error=None,
                    chart_value_max=None,
                    chart_value_min=None,
                    result=None,
                    result_primary_time_granularity=None,
                    result_source=None,
                )

        mock_mql_client.return_value = MockMQLClient
        transform_task = TransformCreateMaterialization()

        response = transform_task.run(
            api_key="key",
            mql_server_url="url",
            materialization_name="mt_name",
            wait_for_creation=False,
        )

        assert response.is_complete is True
        assert response.is_successful is True
        assert response.is_failed is False

    @mock.patch("prefect.tasks.transform.transform_tasks.MQLClient")
    def test_run_on_create_materialization_async_pending_status(self, mock_mql_client):
        class MockMQLClient:
            def create_materialization(
                materialization_name: str,
                start_time: Optional[str] = None,
                end_time: Optional[str] = None,
                model_key_id: Optional[int] = None,
                output_table: Optional[str] = None,
                force: bool = False,
            ):
                return MqlQueryStatusResp(
                    query_id="xyz",
                    status=MqlQueryStatus.PENDING,
                    sql="sql_query",
                    error=None,
                    chart_value_max=None,
                    chart_value_min=None,
                    result=None,
                    result_primary_time_granularity=None,
                    result_source=None,
                )

        mock_mql_client.return_value = MockMQLClient
        transform_task = TransformCreateMaterialization()

        response = transform_task.run(
            api_key="key",
            mql_server_url="url",
            materialization_name="mt_name",
            wait_for_creation=False,
        )

        assert response.is_complete is False
        assert response.is_successful is False
        assert response.is_failed is False

    @mock.patch("prefect.tasks.transform.transform_tasks.MQLClient")
    def test_run_on_create_materialization_async_running_status(self, mock_mql_client):
        class MockMQLClient:
            def create_materialization(
                materialization_name: str,
                start_time: Optional[str] = None,
                end_time: Optional[str] = None,
                model_key_id: Optional[int] = None,
                output_table: Optional[str] = None,
                force: bool = False,
            ):
                return MqlQueryStatusResp(
                    query_id="xyz",
                    status=MqlQueryStatus.RUNNING,
                    sql="sql_query",
                    error=None,
                    chart_value_max=None,
                    chart_value_min=None,
                    result=None,
                    result_primary_time_granularity=None,
                    result_source=None,
                )

        mock_mql_client.return_value = MockMQLClient
        transform_task = TransformCreateMaterialization()

        response = transform_task.run(
            api_key="key",
            mql_server_url="url",
            materialization_name="mt_name",
            wait_for_creation=False,
        )

        assert response.is_complete is False
        assert response.is_successful is False
        assert response.is_failed is False

    @mock.patch("prefect.tasks.transform.transform_tasks.MQLClient")
    def test_run_on_create_materialization_sync(self, mock_mql_client):
        class MockMQLClient:
            def materialize(
                materialization_name: str,
                start_time: Optional[str] = None,
                end_time: Optional[str] = None,
                model_key_id: Optional[int] = None,
                output_table: Optional[str] = None,
                force: bool = False,
                timeout: Optional[int] = None,
            ):
                return MqlMaterializeResp(
                    schema="schema", table="table", query_id="xyz"
                )

        mock_mql_client.return_value = MockMQLClient
        transform_task = TransformCreateMaterialization()

        response = transform_task.run(
            api_key="key", mql_server_url="url", materialization_name="mt_name"
        )

        assert response.fully_qualified_name == "schema.table"

import json
import os
from unittest.mock import patch

import pytest
import respx
from httpx import Response
from prefect_dbt.cloud.credentials import DbtCloudCredentials
from prefect_dbt.cloud.exceptions import (
    DbtCloudCreateJobFailed,
    DbtCloudDeleteJobFailed,
    DbtCloudJobRunIncomplete,
    DbtCloudJobRunTimedOut,
)
from prefect_dbt.cloud.jobs import (
    DbtCloudJob,
    DbtCloudJobRunCancelled,
    DbtCloudJobRunFailed,
    DbtCloudJobRunTriggerFailed,
    _build_nodes_from_manifest,
    _emit_asset_materialization,
    _format_create_assets_error,
    _select_successful_asset_nodes,
    create_dbt_cloud_job,
    delete_dbt_cloud_job,
    get_dbt_cloud_job_info,
    get_run_id,
    retry_dbt_cloud_job_run_subset_and_wait_for_completion,
    run_dbt_cloud_job,
    trigger_dbt_cloud_job_run,
    trigger_dbt_cloud_job_run_and_wait_for_completion,
)
from prefect_dbt.cloud.models import TriggerJobRunOptions
from prefect_dbt.core._artifacts import (
    create_asset_for_node,
    get_upstream_assets_for_node,
)

import prefect
from prefect import flow
from prefect.assets import Asset, AssetProperties
from prefect.context import AssetContext
from prefect.logging.loggers import disable_run_logger


@pytest.fixture
def dbt_cloud_credentials():
    return DbtCloudCredentials(api_key="my_api_key", account_id=123456789)


@pytest.fixture
def dbt_cloud_job(dbt_cloud_credentials):
    return DbtCloudJob(job_id=10000, dbt_cloud_credentials=dbt_cloud_credentials)


HEADERS = {
    "Authorization": "Bearer my_api_key",
    "x-dbt-partner-source": "prefect",
    "user-agent": f"prefect-{prefect.__version__}",
}


def _manifest_response():
    return {
        "metadata": {"adapter_type": "postgres"},
        "nodes": {
            "model.jaffle_shop.stg_customers": {
                "unique_id": "model.jaffle_shop.stg_customers",
                "resource_type": "model",
                "name": "stg_customers",
                "relation_name": '"analytics"."stg_customers"',
                "description": "Customer staging model",
                "config": {"materialized": "view", "meta": {"owner": "data-team"}},
                "depends_on": {"nodes": ["source.jaffle_shop.raw_customers"]},
            },
            "model.jaffle_shop.ephemeral_customers": {
                "unique_id": "model.jaffle_shop.ephemeral_customers",
                "resource_type": "model",
                "name": "ephemeral_customers",
                "description": "Ephemeral model",
                "config": {"materialized": "ephemeral"},
                "depends_on": {"nodes": ["source.jaffle_shop.raw_customers"]},
            },
            "model.jaffle_shop.unselected_orders": {
                "unique_id": "model.jaffle_shop.unselected_orders",
                "resource_type": "model",
                "name": "unselected_orders",
                "relation_name": '"analytics"."unselected_orders"',
                "config": {"materialized": "table"},
                "depends_on": {"nodes": []},
            },
            "seed.jaffle_shop.seed_customers": {
                "unique_id": "seed.jaffle_shop.seed_customers",
                "resource_type": "seed",
                "name": "seed_customers",
                "relation_name": '"analytics"."seed_customers"',
                "config": {},
                "depends_on": {"nodes": []},
            },
            "test.jaffle_shop.stg_customers_not_null": {
                "unique_id": "test.jaffle_shop.stg_customers_not_null",
                "resource_type": "test",
                "name": "stg_customers_not_null",
                "config": {},
                "depends_on": {"nodes": ["model.jaffle_shop.stg_customers"]},
            },
        },
        "sources": {
            "source.jaffle_shop.raw_customers": {
                "unique_id": "source.jaffle_shop.raw_customers",
                "resource_type": "source",
                "name": "raw_customers",
                "relation_name": '"raw"."customers"',
                "config": {},
            }
        },
    }


def _run_results_response():
    return {
        "results": [
            {"unique_id": "model.jaffle_shop.stg_customers", "status": "success"},
            {
                "unique_id": "model.jaffle_shop.unselected_orders",
                "status": "skipped",
            },
            {"unique_id": "seed.jaffle_shop.seed_customers", "status": "success"},
            {
                "unique_id": "test.jaffle_shop.stg_customers_not_null",
                "status": "success",
            },
            {
                "unique_id": "model.jaffle_shop.ephemeral_customers",
                "status": "success",
            },
        ]
    }


class TestDbtCloudAssetCreation:
    def test_select_successful_asset_nodes_filters_manifest_and_run_results(self):
        all_nodes = _build_nodes_from_manifest(_manifest_response())
        selected_nodes = _select_successful_asset_nodes(
            all_nodes, _run_results_response()
        )

        assert set(selected_nodes) == {
            "model.jaffle_shop.stg_customers",
            "seed.jaffle_shop.seed_customers",
        }

    def test_create_asset_for_cloud_manifest_node(self):
        all_nodes = _build_nodes_from_manifest(_manifest_response())
        asset = create_asset_for_node(
            all_nodes["model.jaffle_shop.stg_customers"], "postgres"
        )

        assert asset.key == "postgres://analytics/stg_customers"
        assert asset.properties == AssetProperties(
            name="analytics.stg_customers",
            description="Customer staging model",
            owners=["data-team"],
        )

    def test_get_upstream_assets_for_cloud_manifest_node(self):
        all_nodes = _build_nodes_from_manifest(_manifest_response())
        upstream_assets = get_upstream_assets_for_node(
            all_nodes["model.jaffle_shop.stg_customers"], all_nodes, "postgres"
        )

        assert upstream_assets == [
            Asset(
                key="postgres://raw/customers",
                properties=AssetProperties(name="raw_customers"),
            )
        ]

    @patch("prefect_dbt.cloud.jobs.emit_event")
    def test_emit_asset_materialization(self, emit_event_mock):
        asset = Asset(
            key="postgres://analytics/stg_customers",
            properties=AssetProperties(name="analytics.stg_customers"),
        )
        upstream_asset = Asset(
            key="postgres://raw/customers",
            properties=AssetProperties(name="raw_customers"),
        )

        _emit_asset_materialization(asset, [upstream_asset])

        emit_event_mock.assert_called_once_with(
            event="prefect.asset.materialization.succeeded",
            resource=AssetContext.asset_as_resource(asset),
            related=[
                AssetContext.asset_as_related(upstream_asset),
                AssetContext.related_materialized_by("dbt"),
            ],
        )

    def test_format_create_assets_error(self):
        assert _format_create_assets_error(10000, ValueError("bad manifest")) == (
            "Failed to create assets for dbt Cloud job run 10000: bad manifest"
        )


class TestTriggerDbtCloudJobRun:
    async def test_get_dbt_cloud_job_info(self, dbt_cloud_credentials):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/12/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": {"id": 10000}}))

            response = await get_dbt_cloud_job_info.fn(
                dbt_cloud_credentials=dbt_cloud_credentials,
                job_id=12,
                order_by="id",
            )

            assert response == {"id": 10000}

    async def test_trigger_job_with_no_options(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )

            with disable_run_logger():
                result = await trigger_dbt_cloud_job_run.fn(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=1,
                )

            assert result == {"id": 10000, "project_id": 12345}

            request_body = json.loads(respx_mock.calls.last.request.content.decode())
            assert "Triggered via Prefect" in request_body["cause"]

    async def test_trigger_with_custom_options(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
                json={
                    "cause": "This is a custom cause",
                    "git_branch": "staging",
                    "schema_override": "dbt_cloud_pr_123",
                    "dbt_version_override": "0.18.0",
                    "threads_override": 8,
                    "target_name_override": "staging",
                    "generate_docs_override": True,
                    "timeout_seconds_override": 3000,
                    "steps_override": [
                        "dbt seed",
                        "dbt run --fail-fast",
                        "dbt test --fail fast",
                    ],
                },
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )

            @flow
            async def test_trigger_with_custom_options():
                return await trigger_dbt_cloud_job_run(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=1,
                    options=TriggerJobRunOptions(
                        cause="This is a custom cause",
                        git_branch="staging",
                        schema_override="dbt_cloud_pr_123",
                        dbt_version_override="0.18.0",
                        target_name_override="staging",
                        timeout_seconds_override=3000,
                        generate_docs_override=True,
                        threads_override=8,
                        steps_override=[
                            "dbt seed",
                            "dbt run --fail-fast",
                            "dbt test --fail fast",
                        ],
                    ),
                )

            result = await test_trigger_with_custom_options()
            assert result == {"id": 10000, "project_id": 12345}

    async def test_trigger_nonexistent_job(self, dbt_cloud_credentials):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    404, json={"status": {"user_message": "Not found!"}}
                )
            )

            @flow
            async def test_trigger_nonexistent_job():
                task_shorter_retry = trigger_dbt_cloud_job_run.with_options(
                    retries=1, retry_delay_seconds=1
                )
                await task_shorter_retry(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=1,
                )

            with pytest.raises(DbtCloudJobRunTriggerFailed, match="Not found!"):
                await test_trigger_nonexistent_job()

    async def test_trigger_nonexistent_run_id_no_logs(
        self, dbt_cloud_credentials, caplog
    ):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": {"project_id": 12345}}))

            @flow
            async def trigger_nonexistent_run_id():
                task_shorter_retry = trigger_dbt_cloud_job_run.with_options(
                    retries=1, retry_delay_seconds=1
                )
                await task_shorter_retry(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=1,
                )

            await trigger_nonexistent_run_id()


class TestTriggerDbtCloudJobRunAndWaitForCompletion:
    async def test_run_success(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(
                        200,
                        json={
                            "data": {
                                "id": 10000,
                                "status": 10,
                                "run_steps": [
                                    {
                                        "index": 4,
                                        "name": "Invoke dbt with `dbt run`",
                                        "status_humanized": "Success",
                                    }
                                ],
                            }
                        },
                    ),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": ["manifest.json"]}))

            result = await trigger_dbt_cloud_job_run_and_wait_for_completion(
                dbt_cloud_credentials=dbt_cloud_credentials, job_id=1
            )
            assert result == {
                "id": 10000,
                "status": 10,
                "artifact_paths": ["manifest.json"],
            }

    async def test_run_success_with_wait(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 1}}),
                    Response(200, json={"data": {"id": 10000, "status": 3}}),
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": ["manifest.json"]}))

            result = await trigger_dbt_cloud_job_run_and_wait_for_completion(
                dbt_cloud_credentials=dbt_cloud_credentials,
                job_id=1,
                poll_frequency_seconds=1,
            )
            assert result == {
                "id": 10000,
                "status": 10,
                "artifact_paths": ["manifest.json"],
            }

    async def test_run_failure_with_wait_and_retry(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 1}}),
                    Response(200, json={"data": {"id": 10000, "status": 3}}),
                    Response(
                        200, json={"data": {"id": 10000, "status": 20}}
                    ),  # failed status
                ]
            )

            with pytest.raises(DbtCloudJobRunFailed):
                await trigger_dbt_cloud_job_run_and_wait_for_completion(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=1,
                    poll_frequency_seconds=1,
                    retry_filtered_models_attempts=1,
                )

    async def test_run_with_unexpected_status(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 1}}),
                    Response(200, json={"data": {"id": 10000, "status": 3}}),
                    Response(
                        200, json={"data": {"id": 10000, "status": 42}}
                    ),  # unknown status
                ]
            )

            with pytest.raises(
                ValueError, match="42 is not a valid DbtCloudJobRunStatus"
            ):
                await trigger_dbt_cloud_job_run_and_wait_for_completion(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=1,
                    poll_frequency_seconds=1,
                    retry_filtered_models_attempts=0,
                )

    async def test_run_failure_no_run_id(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": {"project_id": 12345}}))

            with pytest.raises(RuntimeError, match="Unable to determine run ID"):
                await trigger_dbt_cloud_job_run_and_wait_for_completion(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=1,
                    poll_frequency_seconds=1,
                )

    async def test_run_cancelled_with_wait(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 1}}),
                    Response(200, json={"data": {"id": 10000, "status": 3}}),
                    Response(200, json={"data": {"id": 10000, "status": 30}}),
                ]
            )

            with pytest.raises(DbtCloudJobRunCancelled):
                await trigger_dbt_cloud_job_run_and_wait_for_completion(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=1,
                    poll_frequency_seconds=1,
                    retry_filtered_models_attempts=0,
                )

    async def test_run_timed_out(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 1}}),
                    Response(200, json={"data": {"id": 10000, "status": 3}}),
                    Response(200, json={"data": {"id": 10000, "status": 3}}),
                    Response(200, json={"data": {"id": 10000, "status": 3}}),
                ]
            )

            with pytest.raises(DbtCloudJobRunTimedOut):
                await trigger_dbt_cloud_job_run_and_wait_for_completion(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=1,
                    poll_frequency_seconds=1,
                    max_wait_seconds=3,
                    retry_filtered_models_attempts=0,
                )

    async def test_timeout_seconds_override_extends_max_wait(
        self, dbt_cloud_credentials
    ):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 1}}),
                    Response(200, json={"data": {"id": 10000, "status": 3}}),
                    Response(200, json={"data": {"id": 10000, "status": 3}}),
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": ["manifest.json"]}))

            result = await trigger_dbt_cloud_job_run_and_wait_for_completion(
                dbt_cloud_credentials=dbt_cloud_credentials,
                job_id=1,
                trigger_job_run_options=TriggerJobRunOptions(
                    timeout_seconds_override=5,
                ),
                poll_frequency_seconds=1,
                max_wait_seconds=2,
                retry_filtered_models_attempts=0,
            )
            assert result == {
                "id": 10000,
                "status": 10,
                "artifact_paths": ["manifest.json"],
            }

    async def test_run_success_failed_artifacts(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(
                        200,
                        json={
                            "data": {
                                "id": 10000,
                                "status": 10,
                                "run_steps": [
                                    {
                                        "index": 4,
                                        "name": "Invoke dbt with `dbt run`",
                                        "status_humanized": "Success",
                                    }
                                ],
                            }
                        },
                    ),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    500, json={"status": {"user_message": "This is what went wrong"}}
                )
            )

            result = await trigger_dbt_cloud_job_run_and_wait_for_completion(
                dbt_cloud_credentials=dbt_cloud_credentials, job_id=1
            )
            assert result == {"id": 10000, "status": 10}


class TestRetryDbtCloudRunJobSubsetAndWaitForCompletion:
    async def test_run_steps_override_error(self, dbt_cloud_credentials):
        with pytest.raises(ValueError, match="Do not set `steps_override"):
            await retry_dbt_cloud_job_run_subset_and_wait_for_completion(
                dbt_cloud_credentials=dbt_cloud_credentials,
                trigger_job_run_options=TriggerJobRunOptions(steps_override=["step"]),
                run_id=12,
            )

    @pytest.mark.parametrize(
        "trigger_job_run_options",
        [TriggerJobRunOptions(timeout_seconds_override=42), None],
    )
    @pytest.mark.parametrize(
        "exe_command",
        ["run", "run-operation"],
    )
    async def test_retry_run(
        self,
        trigger_job_run_options,
        exe_command,
        dbt_cloud_credentials,
    ):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "data": {
                            "id": 10000,
                            "generate_docs": False,
                            "generate_sources": False,
                        }
                    },
                )
            )

            # mock get_dbt_cloud_run_info
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "data": {
                            "id": 10000,
                            "status": 20,  # failed status
                            "run_steps": [
                                {
                                    "id": 432100123,
                                    "run_id": 10000,
                                    "account_id": 123456789,
                                    "index": 1,
                                    "name": "Clone Git Repository",
                                    "status_humanized": "Success",
                                },
                                {
                                    "id": 432100124,
                                    "run_id": 10000,
                                    "account_id": 123456789,
                                    "index": 2,
                                    "name": "Create Profile from Connection Snowflake ",
                                    "status_humanized": "Success",
                                },
                                {
                                    "id": 432100125,
                                    "run_id": 10000,
                                    "account_id": 123456789,
                                    "index": 3,
                                    "name": "Invoke dbt with `dbt deps`",
                                    "status_humanized": "Success",
                                },
                                {
                                    "run_id": 10000,
                                    "account_id": 123456789,
                                    "index": 4,
                                    "name": f"Invoke dbt with `dbt {exe_command}`",
                                    "status_humanized": "Error",
                                },
                            ],
                            "job_id": "1",
                        }
                    },
                )
            )

            # mock list_dbt_cloud_run_artifacts
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": ["run_results.json"]}))

            # mock get_dbt_cloud_run_artifact
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/run_results.json",  # noqa
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "metadata": {"env": {"DBT_CLOUD_JOB_ID": "1"}},
                        "results": [
                            {
                                "status": "fail",
                                "message": "FAIL 1",
                                "failures": None,
                                "unique_id": "model.jaffle_shop.stg_customers",
                            },
                        ],
                    },
                )
            )
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/1/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )

            with pytest.raises(DbtCloudJobRunFailed, match="Triggered job run with"):
                await retry_dbt_cloud_job_run_subset_and_wait_for_completion(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    run_id=10000,
                    trigger_job_run_options=trigger_job_run_options,
                )


@pytest.fixture
def real_dbt_cloud_job_id():
    job_id = os.environ.get("DBT_CLOUD_JOB_ID")
    if not job_id:
        pytest.skip("DBT_CLOUD_JOB_ID not set")
    return job_id


@pytest.fixture
def real_dbt_cloud_api_key():
    api_key = os.environ.get("DBT_CLOUD_API_KEY")
    if not api_key:
        pytest.skip("DBT_CLOUD_API_KEY not set")
    return api_key


@pytest.fixture
def real_dbt_cloud_account_id():
    account_id = os.environ.get("DBT_CLOUD_ACCOUNT_ID")
    if not account_id:
        pytest.skip("DBT_CLOUD_ACCOUNT_ID not set")
    return account_id


@pytest.mark.integration
async def test_run_real_dbt_cloud_job(
    real_dbt_cloud_job_id, real_dbt_cloud_api_key, real_dbt_cloud_account_id
):
    result = await trigger_dbt_cloud_job_run_and_wait_for_completion(
        dbt_cloud_credentials=DbtCloudCredentials(
            api_key=real_dbt_cloud_api_key, account_id=real_dbt_cloud_account_id
        ),
        job_id=real_dbt_cloud_job_id,
        poll_frequency_seconds=1,
    )
    assert result.get("status") == 10


class TestGetRunId:
    def test_run(self):
        assert get_run_id.fn({"id": 42}) == 42

    def test_fail(self):
        with pytest.raises(RuntimeError, match="Unable to determine run"):
            get_run_id.fn({})


class TestTriggerWaitRetryDbtCloudJobRun:
    async def test_run_success(self, dbt_cloud_job):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(200, json={"data": {"id": 10000, "status": 10}})
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": ["manifest.json"]}))

            result = await run_dbt_cloud_job(dbt_cloud_job=dbt_cloud_job)
            assert result == {
                "id": 10000,
                "status": 10,
                "artifact_paths": ["manifest.json"],
            }

    @patch("prefect_dbt.cloud.jobs.emit_event")
    async def test_run_success_with_create_assets(self, emit_event_mock, dbt_cloud_job):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(
                        200,
                        json={
                            "data": {
                                "id": 10000,
                                "status": 10,
                                "run_steps": [
                                    {
                                        "index": 4,
                                        "name": "Invoke dbt with `dbt run`",
                                        "status_humanized": "Success",
                                    }
                                ],
                            }
                        },
                    ),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "data": [
                            "manifest.json",
                            "run_results.json",
                        ]
                    },
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/manifest.json?step=4",
                headers=HEADERS,
            ).mock(return_value=Response(200, json=_manifest_response()))
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/run_results.json?step=4",
                headers=HEADERS,
            ).mock(return_value=Response(200, json=_run_results_response()))

            result = await run_dbt_cloud_job(
                dbt_cloud_job=dbt_cloud_job, create_assets=True
            )

            assert result == {
                "id": 10000,
                "status": 10,
                "artifact_paths": ["manifest.json", "run_results.json"],
            }
            assert emit_event_mock.call_count == 2
            first_call = emit_event_mock.call_args_list[0].kwargs
            assert first_call["event"] == "prefect.asset.materialization.succeeded"
            assert first_call["resource"] == {
                "prefect.resource.id": "postgres://analytics/stg_customers",
                "prefect.resource.name": "analytics.stg_customers",
                "prefect.asset.description": "Customer staging model",
                "prefect.asset.owners": '["data-team"]',
            }
            assert first_call["related"] == [
                {
                    "prefect.resource.id": "postgres://raw/customers",
                    "prefect.resource.role": "asset",
                },
                {
                    "prefect.resource.id": "dbt",
                    "prefect.resource.role": "asset-materialized-by",
                },
            ]
            emitted_asset_keys = {
                call.kwargs["resource"]["prefect.resource.id"]
                for call in emit_event_mock.call_args_list
            }
            assert emitted_asset_keys == {
                "postgres://analytics/stg_customers",
                "postgres://analytics/seed_customers",
            }

    @patch("prefect_dbt.cloud.jobs.emit_event")
    async def test_run_success_with_create_assets_uses_asset_steps(
        self, emit_event_mock, dbt_cloud_job
    ):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(
                        200,
                        json={
                            "data": {
                                "id": 10000,
                                "status": 10,
                                "run_steps": [
                                    {
                                        "index": 4,
                                        "name": "Invoke dbt with `dbt run`",
                                        "status_humanized": "Success",
                                    },
                                    {
                                        "index": 5,
                                        "name": "Invoke dbt with `dbt test`",
                                        "status_humanized": "Success",
                                    },
                                ],
                            }
                        },
                    ),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "data": [
                            "manifest.json",
                            "run_results.json",
                        ]
                    },
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/manifest.json?step=4",
                headers=HEADERS,
            ).mock(return_value=Response(200, json=_manifest_response()))
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/run_results.json?step=4",
                headers=HEADERS,
            ).mock(return_value=Response(200, json=_run_results_response()))

            result = await run_dbt_cloud_job(
                dbt_cloud_job=dbt_cloud_job, create_assets=True
            )

            assert result == {
                "id": 10000,
                "status": 10,
                "artifact_paths": ["manifest.json", "run_results.json"],
            }
            assert emit_event_mock.call_count == 2
            emitted_asset_keys = {
                call.kwargs["resource"]["prefect.resource.id"]
                for call in emit_event_mock.call_args_list
            }
            assert emitted_asset_keys == {
                "postgres://analytics/stg_customers",
                "postgres://analytics/seed_customers",
            }

    @patch("prefect_dbt.cloud.jobs.emit_event")
    async def test_run_retry_with_create_assets_materializes_each_attempt(
        self, emit_event_mock, dbt_cloud_job
    ):
        initial_run_results = {
            "results": [
                {"unique_id": "model.jaffle_shop.stg_customers", "status": "success"},
                {"unique_id": "seed.jaffle_shop.seed_customers", "status": "fail"},
            ]
        }
        retry_run_results = {
            "results": [
                {"unique_id": "seed.jaffle_shop.seed_customers", "status": "success"},
            ]
        }

        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "project_id": 12345}}),
                    Response(200, json={"data": {"id": 10001, "project_id": 12345}}),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 20}}),
                    Response(200, json={"data": {"id": 10000, "status": 20}}),
                    Response(
                        200,
                        json={
                            "data": {
                                "id": 10000,
                                "status": 20,
                                "run_steps": [
                                    {
                                        "index": 1,
                                        "name": "Clone",
                                        "status_humanized": "Success",
                                    },
                                    {
                                        "index": 2,
                                        "name": "Profile",
                                        "status_humanized": "Success",
                                    },
                                    {
                                        "index": 3,
                                        "name": "Invoke dbt with `dbt deps`",
                                        "status_humanized": "Success",
                                    },
                                    {
                                        "index": 4,
                                        "name": "Invoke dbt with `dbt seed`",
                                        "status_humanized": "Error",
                                    },
                                ],
                            }
                        },
                    ),
                    Response(
                        200,
                        json={
                            "data": {
                                "id": 10000,
                                "status": 20,
                                "run_steps": [
                                    {
                                        "index": 4,
                                        "name": "Invoke dbt with `dbt seed`",
                                        "status_humanized": "Error",
                                    }
                                ],
                            }
                        },
                    ),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "data": {
                            "id": 10000,
                            "generate_docs": False,
                            "generate_sources": False,
                        }
                    },
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/run_results.json?step=4",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json=initial_run_results),
                    Response(200, json=initial_run_results),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/manifest.json?step=4",
                headers=HEADERS,
            ).mock(return_value=Response(200, json=_manifest_response()))
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10001/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10001, "status": 10}}),
                    Response(200, json={"data": {"id": 10001, "status": 10}}),
                    Response(
                        200,
                        json={
                            "data": {
                                "id": 10001,
                                "status": 10,
                                "run_steps": [
                                    {
                                        "index": 4,
                                        "name": "Invoke dbt with `dbt seed`",
                                        "status_humanized": "Success",
                                    }
                                ],
                            }
                        },
                    ),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10001/artifacts/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": ["manifest.json", "run_results.json"]}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10001/artifacts/manifest.json?step=4",
                headers=HEADERS,
            ).mock(return_value=Response(200, json=_manifest_response()))
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10001/artifacts/run_results.json?step=4",
                headers=HEADERS,
            ).mock(return_value=Response(200, json=retry_run_results))

            result = await run_dbt_cloud_job(
                dbt_cloud_job=dbt_cloud_job, create_assets=True
            )

            assert result == {
                "id": 10001,
                "status": 10,
                "artifact_paths": ["manifest.json", "run_results.json"],
            }
            assert [
                call.kwargs["resource"]["prefect.resource.id"]
                for call in emit_event_mock.call_args_list
            ] == [
                "postgres://analytics/stg_customers",
                "postgres://analytics/seed_customers",
            ]

    @patch("prefect_dbt.cloud.jobs.emit_event")
    async def test_run_success_with_create_assets_skips_on_artifact_error(
        self, emit_event_mock, dbt_cloud_job, caplog
    ):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                side_effect=[
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(200, json={"data": {"id": 10000, "status": 10}}),
                    Response(
                        200,
                        json={
                            "data": {
                                "id": 10000,
                                "status": 10,
                                "run_steps": [
                                    {
                                        "index": 4,
                                        "name": "Invoke dbt with `dbt run`",
                                        "status_humanized": "Success",
                                    }
                                ],
                            }
                        },
                    ),
                ]
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": ["manifest.json"]}))
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/manifest.json?step=4",
                headers=HEADERS,
            ).mock(return_value=Response(404, json={"status": {"user_message": "No"}}))

            result = await run_dbt_cloud_job(
                dbt_cloud_job=dbt_cloud_job, create_assets=True
            )

            assert result == {
                "id": 10000,
                "status": 10,
                "artifact_paths": ["manifest.json"],
            }
            emit_event_mock.assert_not_called()
            assert (
                "Failed to create assets for dbt Cloud job run 10000: No" in caplog.text
            )

    async def test_run_timeout(self, dbt_cloud_job):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(200, json={"data": {"id": 10000, "status": 3}})
            )

            dbt_cloud_job.timeout_seconds = 1
            with pytest.raises(DbtCloudJobRunTimedOut, match="Max wait time of 1"):
                await run_dbt_cloud_job(dbt_cloud_job=dbt_cloud_job)

    @pytest.mark.parametrize(
        "exe_command",
        ["run", "run-operation"],
    )
    async def test_fail(self, dbt_cloud_job, exe_command):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "data": {"id": 10000, "project_id": 12345, "run_steps": [""]}
                    },
                )
            )
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(200, json={"data": {"id": 10000, "status": 20}})
            )

            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/100000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "data": {
                            "id": 10000,
                            "generate_docs": False,
                            "generate_sources": False,
                        }
                    },
                )
            )

            # mock get_dbt_cloud_run_info
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "data": {
                            "id": 10000,
                            "status": 20,  # failed status
                            "run_steps": [
                                {
                                    "id": 432100123,
                                    "run_id": 10000,
                                    "account_id": 123456789,
                                    "index": 1,
                                    "name": "Clone Git Repository",
                                    "status_humanized": "Success",
                                },
                                {
                                    "id": 432100124,
                                    "run_id": 10000,
                                    "account_id": 123456789,
                                    "index": 2,
                                    "name": "Create Profile from Connection Snowflake ",
                                    "status_humanized": "Success",
                                },
                                {
                                    "id": 432100125,
                                    "run_id": 10000,
                                    "account_id": 123456789,
                                    "index": 3,
                                    "name": "Invoke dbt with `dbt deps`",
                                    "status_humanized": "Success",
                                },
                                {
                                    "run_id": 10000,
                                    "account_id": 123456789,
                                    "index": 4,
                                    "name": f"Invoke dbt with `dbt {exe_command}`",
                                    "status_humanized": "Error",
                                },
                            ],
                            "job_id": "1",
                        }
                    },
                )
            )

            # mock list_dbt_cloud_run_artifacts
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": ["run_results.json"]}))

            # mock get_dbt_cloud_run_artifact
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/run_results.json",  # noqa
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "metadata": {"env": {"DBT_CLOUD_JOB_ID": "1"}},
                        "results": [
                            {
                                "status": "fail",
                                "message": "FAIL 1",
                                "failures": None,
                                "unique_id": "model.jaffle_shop.stg_customers",
                            },
                        ],
                    },
                )
            )

            with pytest.raises(DbtCloudJobRunFailed, match="dbt Cloud job 10000"):
                await run_dbt_cloud_job(dbt_cloud_job=dbt_cloud_job)

    async def test_cancel(self, dbt_cloud_job):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(200, json={"data": {"id": 10000, "status": 30}})
            )

            with pytest.raises(DbtCloudJobRunCancelled, match="dbt Cloud job 10000"):
                await run_dbt_cloud_job(dbt_cloud_job=dbt_cloud_job)

    async def test_fetch_result_running(self, dbt_cloud_job):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(200, json={"data": {"id": 10000, "status": 3}})
            )

            with pytest.raises(DbtCloudJobRunIncomplete, match="dbt Cloud job 10000"):
                run = await dbt_cloud_job.trigger()
                await run.fetch_result()

    async def test_fail_auth(self, dbt_cloud_job):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    404, json={"status": {"user_message": "Not found"}}
                )
            )
            with pytest.raises(DbtCloudJobRunTriggerFailed, match="Not found"):
                await run_dbt_cloud_job(dbt_cloud_job=dbt_cloud_job, targeted_retries=0)

    async def test_zero_targeted_retries_success(self, dbt_cloud_job):
        """
        Regression test for issue #17634:
        When targeted_retries=0, the function should still wait for job completion
        and return results on success rather than immediately failing.
        """
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(200, json={"data": {"id": 10000, "status": 10}})
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/artifacts/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": ["manifest.json"]}))

            # This should succeed even with targeted_retries=0
            result = await run_dbt_cloud_job(
                dbt_cloud_job=dbt_cloud_job, targeted_retries=0
            )
            assert result == {
                "id": 10000,
                "status": 10,
                "artifact_paths": ["manifest.json"],
            }

    async def test_zero_targeted_retries_failure(self, dbt_cloud_job):
        """
        Regression test for issue #17634:
        When targeted_retries=0 and the job fails, the function should wait for job completion
        before raising the error, rather than failing immediately.
        """
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "project_id": 12345}}
                )
            )
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/10000/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200, json={"data": {"id": 10000, "status": 20}}
                )  # Failed status
            )

            # Should raise an error after waiting for completion, with targeted_retries=0 in the message
            with pytest.raises(
                DbtCloudJobRunFailed, match="dbt Cloud job 10000 failed after 0 retries"
            ):
                await run_dbt_cloud_job(dbt_cloud_job=dbt_cloud_job, targeted_retries=0)


def test_get_job(dbt_cloud_job):
    with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
        respx_mock.route(host="127.0.0.1").pass_through()
        respx_mock.get(
            "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/",
            headers=HEADERS,
        ).mock(
            return_value=Response(
                200, json={"data": {"id": 10000, "project_id": 12345}}
            )
        )
        assert dbt_cloud_job.get_job()["id"] == 10000


class TestCreateDbtCloudJob:
    async def test_create_job_success(self, dbt_cloud_credentials):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "data": {
                            "id": 99999,
                            "project_id": 12345,
                            "environment_id": 67890,
                            "name": "Test Job",
                        }
                    },
                )
            )

            with disable_run_logger():
                result = await create_dbt_cloud_job.fn(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    project_id=12345,
                    environment_id=67890,
                    name="Test Job",
                    execute_steps=["dbt run -s my_model"],
                )

            assert result["id"] == 99999
            assert result["name"] == "Test Job"

            request_body = json.loads(respx_mock.calls.last.request.content.decode())
            assert request_body["project_id"] == 12345
            assert request_body["environment_id"] == 67890
            assert request_body["name"] == "Test Job"
            assert request_body["execute_steps"] == ["dbt run -s my_model"]

    async def test_create_job_with_default_steps(self, dbt_cloud_credentials):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    200,
                    json={"data": {"id": 99999, "name": "Test Job"}},
                )
            )

            with disable_run_logger():
                await create_dbt_cloud_job.fn(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    project_id=12345,
                    environment_id=67890,
                    name="Test Job",
                )

            request_body = json.loads(respx_mock.calls.last.request.content.decode())
            assert request_body["execute_steps"] == ["dbt build"]

    async def test_create_job_failure(self, dbt_cloud_credentials):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.post(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    400, json={"status": {"user_message": "Invalid project ID"}}
                )
            )

            @flow
            async def test_create_job_failure_flow():
                task_shorter_retry = create_dbt_cloud_job.with_options(
                    retries=1, retry_delay_seconds=1
                )
                await task_shorter_retry(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    project_id=12345,
                    environment_id=67890,
                    name="Test Job",
                )

            with pytest.raises(DbtCloudCreateJobFailed, match="Invalid project ID"):
                await test_create_job_failure_flow()


class TestDeleteDbtCloudJob:
    async def test_delete_job_success(self, dbt_cloud_credentials):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.delete(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/99999/",
                headers=HEADERS,
            ).mock(return_value=Response(200, json={"data": {"id": 99999}}))

            with disable_run_logger():
                await delete_dbt_cloud_job.fn(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=99999,
                )

    async def test_delete_job_not_found(self, dbt_cloud_credentials):
        with respx.mock(using="httpx", assert_all_called=False) as respx_mock:
            respx_mock.route(host="127.0.0.1").pass_through()
            respx_mock.delete(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/99999/",
                headers=HEADERS,
            ).mock(
                return_value=Response(
                    404, json={"status": {"user_message": "Job not found"}}
                )
            )

            @flow
            async def test_delete_job_not_found_flow():
                task_shorter_retry = delete_dbt_cloud_job.with_options(
                    retries=1, retry_delay_seconds=1
                )
                await task_shorter_retry(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    job_id=99999,
                )

            with pytest.raises(DbtCloudDeleteJobFailed, match="Job not found"):
                await test_delete_job_not_found_flow()

import json
import os

import pytest
import respx
from httpx import Response
from prefect_dbt.cloud.credentials import DbtCloudCredentials
from prefect_dbt.cloud.exceptions import (
    DbtCloudJobRunIncomplete,
    DbtCloudJobRunTimedOut,
)
from prefect_dbt.cloud.jobs import (
    DbtCloudJob,
    DbtCloudJobRunCancelled,
    DbtCloudJobRunFailed,
    DbtCloudJobRunTriggerFailed,
    get_dbt_cloud_job_info,
    get_run_id,
    retry_dbt_cloud_job_run_subset_and_wait_for_completion,
    run_dbt_cloud_job,
    trigger_dbt_cloud_job_run,
    trigger_dbt_cloud_job_run_and_wait_for_completion,
)
from prefect_dbt.cloud.models import TriggerJobRunOptions

import prefect
from prefect import flow
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
                return_value=Response(200, json={"data": {"id": 10000, "status": 10}})
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
                return_value=Response(200, json={"data": {"id": 10000, "status": 10}})
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

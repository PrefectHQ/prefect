"""Tests for the async_dispatch migration in prefect-dbt cloud jobs.

These tests verify the critical behavior from issue #15008 where
@sync_compatible would incorrectly return coroutines in sync context.
"""

from typing import Coroutine

import pytest
import respx
from httpx import Response
from prefect_dbt.cloud.credentials import DbtCloudCredentials
from prefect_dbt.cloud.jobs import DbtCloudJob, DbtCloudJobRun

from prefect import flow

HEADERS = {"Authorization": "Bearer my_api_key"}


@pytest.fixture
def dbt_cloud_credentials():
    return DbtCloudCredentials(api_key="my_api_key", account_id=123456789)


@pytest.fixture
def dbt_cloud_job(dbt_cloud_credentials):
    return DbtCloudJob(job_id=10000, dbt_cloud_credentials=dbt_cloud_credentials)


def _mock_trigger(respx_mock):
    # let calls to the local Prefect API server through
    respx_mock.route(host="127.0.0.1").pass_through()
    respx_mock.post(
        "https://cloud.getdbt.com/api/v2/accounts/123456789/jobs/10000/run/",
    ).mock(return_value=Response(200, json={"data": {"id": 500, "project_id": 12345}}))


def _mock_get_run(respx_mock, status=10):
    # let calls to the local Prefect API server through
    respx_mock.route(host="127.0.0.1").pass_through()
    respx_mock.get(
        "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/500/",
    ).mock(return_value=Response(200, json={"data": {"id": 500, "status": status}}))


class TestDbtCloudJobTriggerAsyncDispatch:
    def test_trigger_sync_context_returns_job_run_not_coroutine(self, dbt_cloud_job):
        """trigger must return a DbtCloudJobRun (not a coroutine) in sync context."""
        with respx.mock(using="httpx") as respx_mock:
            _mock_trigger(respx_mock)

            @flow
            def test_flow():
                result = dbt_cloud_job.trigger()
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

            run = test_flow()
            assert isinstance(run, DbtCloudJobRun)
            assert run.run_id == 500

    async def test_atrigger_async_context_works(self, dbt_cloud_job):
        with respx.mock(using="httpx") as respx_mock:
            _mock_trigger(respx_mock)

            @flow
            async def test_flow():
                return await dbt_cloud_job.atrigger()

            run = await test_flow()
            assert isinstance(run, DbtCloudJobRun)
            assert run.run_id == 500

    def test_aget_job_is_available(self, dbt_cloud_job):
        assert hasattr(dbt_cloud_job, "aget_job")
        assert hasattr(dbt_cloud_job, "atrigger")
        assert callable(dbt_cloud_job.aget_job)
        assert callable(dbt_cloud_job.atrigger)


class TestDbtCloudJobRunAsyncDispatch:
    def test_get_run_sync_context_returns_dict_not_coroutine(self, dbt_cloud_job):
        run = DbtCloudJobRun(run_id=500, dbt_cloud_job=dbt_cloud_job)
        with respx.mock(using="httpx") as respx_mock:
            _mock_get_run(respx_mock)

            @flow
            def test_flow():
                result = run.get_run()
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

            data = test_flow()
            assert data == {"id": 500, "status": 10}

    async def test_aget_run_async_context_works(self, dbt_cloud_job):
        run = DbtCloudJobRun(run_id=500, dbt_cloud_job=dbt_cloud_job)
        with respx.mock(using="httpx") as respx_mock:
            _mock_get_run(respx_mock)

            @flow
            async def test_flow():
                return await run.aget_run()

            assert await test_flow() == {"id": 500, "status": 10}

    def test_get_status_code_sync_context_returns_int_not_coroutine(
        self, dbt_cloud_job
    ):
        run = DbtCloudJobRun(run_id=500, dbt_cloud_job=dbt_cloud_job)
        with respx.mock(using="httpx") as respx_mock:
            _mock_get_run(respx_mock, status=10)

            @flow
            def test_flow():
                result = run.get_status_code()
                assert not isinstance(result, Coroutine), (
                    "sync context returned coroutine"
                )
                return result

            assert test_flow() == 10

    def test_async_methods_are_available(self, dbt_cloud_job):
        run = DbtCloudJobRun(run_id=500, dbt_cloud_job=dbt_cloud_job)
        for name in (
            "get_run",
            "get_status_code",
            "wait_for_completion",
            "fetch_result",
            "get_run_artifacts",
            "retry_failed_steps",
        ):
            # async counterpart exists (wait_for_completion -> await_for_completion)
            async_name = (
                "await_for_completion" if name == "wait_for_completion" else f"a{name}"
            )
            assert hasattr(run, async_name), f"missing {async_name}"
            assert callable(getattr(run, async_name))
            # the sync wrapper keeps `.aio` for backwards compatibility
            assert hasattr(getattr(run, name), "aio")

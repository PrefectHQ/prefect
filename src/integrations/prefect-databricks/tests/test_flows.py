import re

import pytest
from httpx import Response
from prefect_databricks.credentials import DatabricksCredentials
from prefect_databricks.flows import (
    DatabricksJobInternalError,
    DatabricksJobRunTimedOut,
    DatabricksJobSkipped,
    DatabricksJobTerminated,
    jobs_runs_submit_and_wait_for_completion,
)

from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    with prefect_test_harness():
        yield


@pytest.fixture
def databricks_credentials():
    return DatabricksCredentials(
        databricks_instance="dbc-abcdefgh-123d.cloud.databricks.com",
        token="testing_token",
    )


@pytest.fixture
def common_mocks(respx_mock):
    respx_mock.post(
        "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/submit",
        headers={"Authorization": "Bearer testing_token"},
    ).mock(return_value=Response(200, json={"run_id": 36108}))


def successful_job_path(request, route):
    if route.call_count == 0:
        return Response(
            200,
            json={
                "run_id": 36108,
                "state": {
                    "life_cycle_state": "RUNNING",
                    "state_message": "",
                    "result_state": "",
                },
                "tasks": [
                    {
                        "run_id": 36260,
                        "task_key": "prefect-task",
                        "state": {
                            "life_cycle_state": "PENDING",
                            "result_state": "",
                            "state_message": "",
                        },
                    }
                ],
            },
        )
    elif route.call_count == 1:
        return Response(
            200,
            json={
                "run_id": 36108,
                "state": {
                    "life_cycle_state": "RUNNING",
                    "state_message": "",
                    "result_state": "",
                },
                "tasks": [
                    {
                        "run_id": 36260,
                        "task_key": "prefect-task",
                        "state": {
                            "life_cycle_state": "RUNNING",
                            "result_state": "",
                            "state_message": "In run",
                        },
                    }
                ],
            },
        )
    else:
        return Response(
            200,
            json={
                "run_id": 36108,
                "state": {
                    "life_cycle_state": "TERMINATED",
                    "state_message": "",
                    "result_state": "SUCCESS",
                },
                "tasks": [
                    {
                        "run_id": 36260,
                        "task_key": "prefect-task",
                        "state": {
                            "life_cycle_state": "TERMINATED",
                            "result_state": "",
                            "state_message": "SUCCESS",
                        },
                    }
                ],
            },
        )


class TestJobsRunsSubmitAndWaitForCompletion:
    @pytest.mark.respx(assert_all_called=True)
    async def test_run_success(self, common_mocks, respx_mock, databricks_credentials):
        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=36108",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200,
                json={
                    "state": {
                        "life_cycle_state": "TERMINATED",
                        "state_message": "",
                        "result_state": "SUCCESS",
                    },
                    "tasks": [{"run_id": 36260, "task_key": "prefect-task"}],
                },
            )
        )

        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get-output",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(return_value=Response(200, json={"notebook_output": {"cell": "output"}}))

        result = await jobs_runs_submit_and_wait_for_completion(
            databricks_credentials=databricks_credentials,
            run_name="prefect-job",
            tasks=[
                {
                    "notebook_task": {
                        "notebook_path": "path",
                        "base_parameters": {"param": "a"},
                    },
                    "task_key": "key",
                }
            ],
        )
        assert result == {"prefect-task": {"cell": "output"}}

    @pytest.mark.respx(assert_all_called=True)
    async def test_run_non_notebook_success(
        self, common_mocks, respx_mock, databricks_credentials
    ):
        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=36108",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(side_effect=successful_job_path)

        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get-output",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(return_value=Response(200, json={"metadata": {"cell": "output"}}))

        result = await jobs_runs_submit_and_wait_for_completion(
            databricks_credentials=databricks_credentials,
            run_name="prefect-job",
            tasks=[
                {
                    "task_key": "prefect-job",
                    "spark_python_task": {
                        "python_file": "test.py",
                        "parameters": ["test"],
                    },
                    "existing_cluster_id": "test-test-test",
                    "libraries": [{"whl": "test.whl"}],
                }
            ],
            poll_frequency_seconds=1,
        )
        assert result == {"prefect-task": {}}

    @pytest.mark.respx(assert_all_called=True)
    @pytest.mark.parametrize("result_state", ["FAILED", "TIMEDOUT", "CANCELED"])
    async def test_run_terminated(
        self, result_state, common_mocks, respx_mock, databricks_credentials
    ):
        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=36108",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200,
                json={
                    "state": {
                        "life_cycle_state": "TERMINATED",
                        "state_message": "testing",
                        "result_state": result_state,
                    },
                    "tasks": [{"run_id": 36260, "task_key": "prefect-task"}],
                },
            )
        )

        match = re.escape(  # escape to handle the parentheses
            f"Databricks Jobs Runs Submit (prefect-job ID 36108) "
            f"terminated with result state, {result_state}: testing"
        )
        with pytest.raises(DatabricksJobTerminated, match=match):
            await jobs_runs_submit_and_wait_for_completion(
                databricks_credentials=databricks_credentials,
                run_name="prefect-job",
                tasks=[
                    {
                        "notebook_task": {
                            "notebook_path": "path",
                            "base_parameters": {"param": "a"},
                        },
                        "task_key": "key",
                    }
                ],
            )

    @pytest.mark.respx(assert_all_called=True)
    async def test_run_skipped(self, common_mocks, respx_mock, databricks_credentials):
        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=36108",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200,
                json={
                    "state": {
                        "life_cycle_state": "SKIPPED",
                        "state_message": "testing",
                    },
                    "tasks": [{"run_id": 36260, "task_key": "prefect-task"}],
                },
            )
        )

        match = re.escape(  # escape to handle the parentheses
            "Databricks Jobs Runs Submit (prefect-job ID 36108) "
            "was skipped: testing."
        )
        with pytest.raises(DatabricksJobSkipped, match=match):
            await jobs_runs_submit_and_wait_for_completion(
                databricks_credentials=databricks_credentials,
                run_name="prefect-job",
                tasks=[
                    {
                        "notebook_task": {
                            "notebook_path": "path",
                            "base_parameters": {"param": "a"},
                        },
                        "task_key": "key",
                    }
                ],
            )

    @pytest.mark.respx(assert_all_called=True)
    async def test_run_internal_error(
        self, common_mocks, respx_mock, databricks_credentials
    ):
        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=36108",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200,
                json={
                    "state": {
                        "life_cycle_state": "INTERNAL_ERROR",
                        "state_message": "testing",
                    },
                    "tasks": [{"run_id": 36260, "task_key": "prefect-task"}],
                },
            )
        )

        match = re.escape(  # escape to handle the parentheses
            "Databricks Jobs Runs Submit (prefect-job ID 36108) "
            "encountered an internal error: testing."
        )
        with pytest.raises(DatabricksJobInternalError, match=match):
            await jobs_runs_submit_and_wait_for_completion(
                databricks_credentials=databricks_credentials,
                run_name="prefect-job",
                tasks=[
                    {
                        "notebook_task": {
                            "notebook_path": "path",
                            "base_parameters": {"param": "a"},
                        },
                        "task_key": "key",
                    }
                ],
            )

    @pytest.mark.respx(assert_all_called=True)
    async def test_run_timeout_error(
        self, common_mocks, respx_mock, databricks_credentials
    ):
        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=36108",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200,
                json={
                    "state": {
                        "life_cycle_state": "nothing",
                        "state_message": "",
                        "result_state": "abc",
                    },
                    "tasks": [{"run_id": 36260, "task_key": "prefect-task"}],
                },
            )
        )

        with pytest.raises(
            DatabricksJobRunTimedOut, match="Max wait time of 0 seconds"
        ):
            await jobs_runs_submit_and_wait_for_completion(
                databricks_credentials=databricks_credentials,
                run_name="prefect-job",
                max_wait_seconds=0,
                tasks=[
                    {
                        "notebook_task": {
                            "notebook_path": "path",
                            "base_parameters": {"param": "a"},
                        },
                        "task_key": "key",
                    }
                ],
            )

    @pytest.mark.respx(assert_all_called=True)
    async def test_run_success_missing_run_name(
        self, common_mocks, respx_mock, databricks_credentials
    ):
        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=36108",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200,
                json={
                    "state": {
                        "life_cycle_state": "TERMINATED",
                        "state_message": "",
                        "result_state": "SUCCESS",
                    },
                    "tasks": [{"run_id": 36260, "task_key": "prefect-task"}],
                },
            )
        )

        respx_mock.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get-output",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(return_value=Response(200, json={"notebook_output": {"cell": "output"}}))

        result = await jobs_runs_submit_and_wait_for_completion(
            databricks_credentials=databricks_credentials,
            tasks=[
                {
                    "notebook_task": {
                        "notebook_path": "path",
                        "base_parameters": {"param": "a"},
                    },
                    "task_key": "key",
                }
            ],
        )
        assert result == {"prefect-task": {"cell": "output"}}

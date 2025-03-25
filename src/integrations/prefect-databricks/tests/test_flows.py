import re
from functools import partial

import pytest
from httpx import Response
from prefect_databricks.credentials import DatabricksCredentials
from prefect_databricks.flows import (
    DatabricksJobInternalError,
    DatabricksJobRunTimedOut,
    DatabricksJobSkipped,
    DatabricksJobTerminated,
    jobs_runs_submit_and_wait_for_completion,
    jobs_runs_submit_by_id_and_wait_for_completion,
)

from prefect.testing.utilities import prefect_test_harness


def sync_handler(result, state):
    state["result"] = result


async def async_handler(result, state):
    state["result"] = result


@pytest.fixture
def respx_mock_with_pass_through(respx_mock):
    respx_mock.route(host="127.0.0.1").pass_through()
    yield respx_mock


@pytest.fixture
def run_now_mocks(respx_mock_with_pass_through):
    respx_mock_with_pass_through.post(
        "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/run-now",
        headers={"Authorization": "Bearer testing_token"},
    ).mock(
        return_value=Response(200, json={"run_id": 11223344, "number_in_job": 11223344})
    )


@pytest.fixture
def global_state():
    return {}


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
def common_mocks(respx_mock_with_pass_through):
    respx_mock_with_pass_through.post(
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
    async def test_run_success(
        self, common_mocks, respx_mock_with_pass_through, databricks_credentials
    ):
        json = {
            "state": {
                "life_cycle_state": "TERMINATED",
                "state_message": "",
                "result_state": "SUCCESS",
            },
            "tasks": [{"run_id": 36260, "task_key": "prefect-task"}],
        }
        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=36108",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(return_value=Response(200, json=json))

        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get-output",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(return_value=Response(200, json={"notebook_output": {"cell": "output"}}))

        result, jobs_runs_metadata = await jobs_runs_submit_and_wait_for_completion(
            databricks_credentials=databricks_credentials,
            run_name="prefect-job",
            return_metadata=True,
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
        assert jobs_runs_metadata == json

    @pytest.mark.respx(assert_all_called=True)
    async def test_run_non_notebook_success(
        self, common_mocks, respx_mock_with_pass_through, databricks_credentials
    ):
        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=36108",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(side_effect=successful_job_path)

        respx_mock_with_pass_through.get(
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
        self,
        result_state,
        common_mocks,
        respx_mock_with_pass_through,
        databricks_credentials,
    ):
        respx_mock_with_pass_through.get(
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
    async def test_run_skipped(
        self, common_mocks, respx_mock_with_pass_through, databricks_credentials
    ):
        respx_mock_with_pass_through.get(
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
            "Databricks Jobs Runs Submit (prefect-job ID 36108) was skipped: testing."
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
        self, common_mocks, respx_mock_with_pass_through, databricks_credentials
    ):
        respx_mock_with_pass_through.get(
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
        self, common_mocks, respx_mock_with_pass_through, databricks_credentials
    ):
        respx_mock_with_pass_through.get(
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
        self, common_mocks, respx_mock_with_pass_through, databricks_credentials
    ):
        respx_mock_with_pass_through.get(
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

        respx_mock_with_pass_through.get(
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

    @pytest.mark.parametrize(
        "handler",
        [
            sync_handler,
            async_handler,
        ],
    )
    async def test_handler_invoked(
        self,
        common_mocks,
        respx_mock_with_pass_through,
        databricks_credentials,
        handler,
        global_state,
    ):
        respx_mock_with_pass_through.get(
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

        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get-output",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(return_value=Response(200, json={"notebook_output": {"cell": "output"}}))

        result = await jobs_runs_submit_and_wait_for_completion(
            databricks_credentials=databricks_credentials,
            run_name="prefect-job",
            job_submission_handler=partial(handler, state=global_state),
        )
        assert result == {"prefect-task": {"cell": "output"}}
        assert "result" in global_state


class TestJobsRunsIdSubmitAndWaitForCompletion:
    @pytest.mark.respx(assert_all_called=False)
    async def test_run_now_success(
        self,
        common_mocks,
        run_now_mocks,
        respx_mock_with_pass_through,
        databricks_credentials,
    ):
        respx_mock_with_pass_through.post(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/run-now?job_id=11223344",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200, json={"run_id": 11223344, "number_in_job": 11223344}
            )
        )
        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=11223344",  # noqa
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
                    "tasks": [{"run_id": 11223344, "task_key": "prefect-task"}],
                },
            )
        )
        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get-output",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(return_value=Response(200, json={"notebook_output": {"cell": "output"}}))

        result = await jobs_runs_submit_by_id_and_wait_for_completion(
            databricks_credentials=databricks_credentials, job_id=11223344
        )
        assert result == {"prefect-task": {"cell": "output"}}

    @pytest.mark.respx(assert_all_called=False)
    @pytest.mark.parametrize("result_state", ["FAILED", "TIMEDOUT", "CANCELED"])
    async def test_run_now_terminated(
        self,
        result_state,
        common_mocks,
        run_now_mocks,
        respx_mock_with_pass_through,
        databricks_credentials,
    ):
        respx_mock_with_pass_through.post(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/run-now?job_id=11223344",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200, json={"run_id": 11223344, "number_in_job": 11223344}
            )
        )
        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=11223344",  # noqa
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
                    "tasks": [{"run_id": 11223344, "task_key": "prefect-task"}],
                },
            )
        )

        match = re.escape(  # escape to handle the parentheses
            f"Databricks Jobs Runs Submit ID 11223344 "
            f"terminated with result state, {result_state}: testing"
        )
        with pytest.raises(DatabricksJobTerminated, match=match):
            await jobs_runs_submit_by_id_and_wait_for_completion(
                databricks_credentials=databricks_credentials, job_id=11223344
            )

    @pytest.mark.respx(assert_all_called=False)
    async def test_run_now_skipped(
        self,
        common_mocks,
        run_now_mocks,
        respx_mock_with_pass_through,
        databricks_credentials,
    ):
        respx_mock_with_pass_through.post(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/run-now?job_id=11223344",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200, json={"run_id": 11223344, "number_in_job": 11223344}
            )
        )
        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=11223344",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200,
                json={
                    "state": {
                        "life_cycle_state": "SKIPPED",
                        "state_message": "testing",
                    },
                    "tasks": [{"run_id": 11223344, "task_key": "prefect-task"}],
                },
            )
        )

        match = re.escape(  # escape to handle the parentheses
            "Databricks Jobs Runs Submit ID 11223344 was skipped: testing."
        )
        with pytest.raises(DatabricksJobSkipped, match=match):
            await jobs_runs_submit_by_id_and_wait_for_completion(
                databricks_credentials=databricks_credentials,
                job_id=11223344,
            )

    @pytest.mark.respx(assert_all_called=False)
    async def test_run_now_timeout_error(
        self,
        common_mocks,
        run_now_mocks,
        respx_mock_with_pass_through,
        databricks_credentials,
    ):
        respx_mock_with_pass_through.post(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/run-now?job_id=11223344",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200, json={"run_id": 11223344, "number_in_job": 11223344}
            )
        )
        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=11223344",  # noqa
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
                    "tasks": [{"run_id": 11223344, "task_key": "prefect-task"}],
                },
            )
        )

        with pytest.raises(
            DatabricksJobRunTimedOut, match="Max wait time of 0 seconds"
        ):
            await jobs_runs_submit_by_id_and_wait_for_completion(
                databricks_credentials=databricks_credentials,
                job_id=11223344,
                max_wait_seconds=0,
            )

    @pytest.mark.parametrize(
        "handler",
        [
            sync_handler,
            async_handler,
        ],
    )
    @pytest.mark.respx(assert_all_called=False)
    async def test_handler_invoked(
        self,
        handler,
        common_mocks,
        run_now_mocks,
        respx_mock_with_pass_through,
        databricks_credentials,
        global_state,
    ):
        respx_mock_with_pass_through.post(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/run-now?job_id=11223344",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(
            return_value=Response(
                200, json={"run_id": 11223344, "number_in_job": 11223344}
            )
        )
        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get?run_id=11223344",  # noqa
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
                    "tasks": [{"run_id": 11223344, "task_key": "prefect-task"}],
                },
            )
        )
        respx_mock_with_pass_through.get(
            "https://dbc-abcdefgh-123d.cloud.databricks.com/api/2.1/jobs/runs/get-output",  # noqa
            headers={"Authorization": "Bearer testing_token"},
        ).mock(return_value=Response(200, json={"notebook_output": {"cell": "output"}}))

        result = await jobs_runs_submit_by_id_and_wait_for_completion(
            databricks_credentials=databricks_credentials,
            job_id=11223344,
            job_submission_handler=partial(handler, state=global_state),
        )
        assert result == {"prefect-task": {"cell": "output"}}
        assert "result" in global_state

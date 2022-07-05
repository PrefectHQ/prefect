import json
from typing import Any

import pytest
import responses
from requests import PreparedRequest

import prefect
pytest.importorskip("pydantic") # Required for databricks tasks

from tests.tasks.databricks.mocks import (
    DatabricksGetJobIDTestOverride,
    DatabricksRunNowTestOverride,
)


@pytest.fixture
def job_config():

    config = {
        "run_name": "Prefect Test",
        "new_cluster": {
            "spark_version": "6.6.x-scala2.11",
            "num_workers": 0,
            "node_type_id": "Standard_D3_v2",
        },
        "spark_python_task": {
            "python_file": f"dbfs:/FileStore/tables/runner.py",
            "parameters": [1],
        },
    }

    return config


@pytest.fixture
def notebook_job_config():

    config = {
        "job_id": 1,
        "notebook_params": {
            "dry-run": "true",
            "oldest-time-to-consider": "1457570074236",
        },
    }

    return config


@pytest.fixture
def notebook_job_config_full():

    config = {
        "job_id": 1,
        "notebook_params": {
            "dry-run": "true",
            "oldest-time-to-consider": "1457570074236",
        },
        "python_params": ["python-param1", "python-param2"],
        "spark_submit_params": ["spark-param1", "spark-param2"],
        "jar_params": ["jar-param1", "jar-param2"],
    }

    return config


@pytest.fixture
def databricks_run_api_response_success():

    response = {
        "run_id": "test-run-id",
        "run_page_url": "https://run_page_url",
        "state": {
            "life_cycle_state": "TERMINATED",
            "result_state": "SUCCESS",
            "state_message": "Completed",
        },
    }

    return response


@pytest.fixture
def databricks_list_api_response_success():
    response = {
        "jobs": [
            {
                "job_id": 76,
                "settings": {
                    "name": "job_name",
                    "email_notifications": {},
                    "max_concurrent_runs": 1,
                    "format": "MULTI_TASK",
                },
                "created_time": 1643102107360,
                "creator_user_name": "user",
            },
            {
                "job_id": 99,
                "settings": {
                    "name": "duplicate",
                    "email_notifications": {},
                    "max_concurrent_runs": 1,
                    "format": "MULTI_TASK",
                },
                "created_time": 1643102107360,
                "creator_user_name": "user",
            },
            {
                "job_id": 100,
                "settings": {
                    "name": "duplicate",
                    "email_notifications": {},
                    "max_concurrent_runs": 1,
                    "format": "MULTI_TASK",
                },
                "created_time": 1643102107360,
                "creator_user_name": "user",
            },
        ],
        "has_more": False,
    }
    return response


@pytest.fixture
def run_now_task_template(
    databricks_run_api_response_success, notebook_job_config_full
):

    return DatabricksRunNowTestOverride(
        mocked_response=databricks_run_api_response_success,
        databricks_conn_secret={
            "host": "https://cloud.databricks.com",
            "token": "databricks-token",
        },
        json=notebook_job_config_full,
    )


@pytest.fixture
def get_jobid_task_template(databricks_list_api_response_success):
    return DatabricksGetJobIDTestOverride(
        mocked_response=databricks_list_api_response_success,
        databricks_conn_secret={
            "host": "https://cloud.databricks.com",
            "token": "databricks-token",
        },
    )


@pytest.fixture
def flow_run_id():
    flow_run_id = "a1b2c3d4"
    prefect.context.flow_run_id = flow_run_id
    yield flow_run_id
    del prefect.context.flow_run_id


@pytest.fixture
def flow_run_name():
    flow_run_name = "angry_cat"
    prefect.context.flow_run_name = flow_run_name
    yield flow_run_name
    del prefect.context.flow_run_name


@pytest.fixture
def requests_mock():
    with responses.RequestsMock() as requests_mock:
        yield requests_mock


@pytest.fixture
def match_run_sumbission_on_idempotency_token(requests_mock, flow_run_id):
    requests_mock.add(
        method=responses.POST,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/submit",
        json={"run_id": "12345"},
        match=[body_entry_matcher("idempotency_token", flow_run_id)],
    )


@pytest.fixture
def match_run_sumbission_on_run_name(requests_mock, flow_run_name):
    requests_mock.add(
        method=responses.POST,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/submit",
        json={"run_id": "12345"},
        match=[
            body_entry_matcher(
                "run_name", f"Job run created by Prefect flow run {flow_run_name}"
            )
        ],
    )


@pytest.fixture
def successful_run_submission(requests_mock):
    requests_mock.add(
        method=responses.POST,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/submit",
        json={"run_id": "12345"},
    )


@pytest.fixture
def successful_run_completion(requests_mock):
    requests_mock.add(
        method=responses.GET,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/get",
        match=[responses.matchers.json_params_matcher({"run_id": "12345"})],
        json={
            "run_page_url": "https://my-workspace.cloud.databricks.com/#job/11223344/run/123",
            "state": {
                "life_cycle_state": "TERMINATED",
                "result_state": "SUCCESS",
                "user_cancelled_or_timedout": False,
                "state_message": "",
            },
        },
    )


@pytest.fixture
def failed_run(requests_mock):
    requests_mock.add(
        method=responses.GET,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/get",
        match=[responses.matchers.json_params_matcher({"run_id": "12345"})],
        json={
            "run_page_url": "https://my-workspace.cloud.databricks.com/#job/11223344/run/123",
            "state": {
                "life_cycle_state": "TERMINATED",
                "result_state": "FAILED",
                "user_cancelled_or_timedout": False,
                "state_message": "",
            },
        },
    )


def body_entry_matcher(key: str, value: Any):
    def matcher(req: PreparedRequest):
        if req.body:
            body = req.body
            if isinstance(body, bytes):
                body = body.decode()
            body_json = json.loads(body)
            if body_json.get(key) == value:
                return True, f"Key ${key} in request body equals ${value}"
            elif body_json.get(key) is None:
                return False, f"Key ${key} not in request body"
            else:
                return False, f"Key ${key} in request body does not equal ${value}"
        else:
            return False, "No body in request"

    return matcher

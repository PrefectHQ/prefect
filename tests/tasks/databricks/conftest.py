import json
from typing import Any

import pytest
import responses
from requests import PreparedRequest


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
                return False, "Key ${key} not in request body"
            else:
                return False, f"Key ${key} in request body does not equal ${value}"
        else:
            return False, "No body in request"

    return matcher


@pytest.fixture
def successful_run_submission(requests_mock):
    requests_mock.add(
        method=responses.POST,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/submit",
        json={"run_id": "12345"},
    )


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
